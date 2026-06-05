"""Motor OCR basado en Tesseract (vía subprocess).

Se invoca el ejecutable de Tesseract directamente en lugar de usar
``pytesseract.image_to_string`` porque esa función falla con
``UnicodeDecodeError`` al intentar decodificar el ``stderr`` de Tesseract en
sistemas cuyo locale no es UTF-8.

Incluye:
- Preprocesamiento ligero (escala de grises).
- Corrección automática de orientación mediante OSD de Tesseract
  (la "Captura 2" llega a veces rotada 90°).
- Escritura del archivo temporal en una carpeta legible (no /tmp, que en
  macOS puede estar aislado para procesos hijos).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Error al ejecutar OCR sobre una imagen."""


# Palabras clave esperadas en una captura legible (para puntuar orientación).
_KEYWORDS = (
    "orden", "rut", "fecha", "direccion", "dirección", "agendamiento",
    "rango", "horario", "contacto", "solicitud",
)

_LANG_PREF = "spa"
_PSM = "6"

# Ruta al ejecutable de Tesseract. Por defecto: descubrimiento automático
# (binario embebido > PATH del sistema).
_TESSERACT_CMD = "tesseract"
_TESSDATA_DIR: str | None = None  # carpeta tessdata embebida, si existe


def _descubrir_tesseract_embebido() -> tuple[str | None, str | None]:
    """Busca Tesseract empaquetado junto al ejecutable o en _MEIPASS.

    Devuelve (tesseract_cmd, tessdata_dir) si encuentra una instalación
    embebida. Las rutas candidatas (en este orden):

    - ``sys._MEIPASS/tesseract/``    (PyInstaller --onefile)
    - ``<dir del .exe>/tesseract/``  (PyInstaller --onedir o portátil)
    - ``<raíz del proyecto>/tesseract/`` (desarrollo)
    """
    candidatas: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidatas.append(Path(meipass) / "tesseract")
    if getattr(sys, "frozen", False):
        candidatas.append(Path(sys.executable).resolve().parent / "tesseract")
    candidatas.append(Path(__file__).resolve().parent.parent.parent / "tesseract")

    exe_name = "tesseract.exe" if os.name == "nt" else "tesseract"
    for raiz in candidatas:
        exe = raiz / exe_name
        if exe.is_file():
            tessdata = raiz / "tessdata"
            return str(exe), (str(tessdata) if tessdata.is_dir() else None)
    return None, None


def configure_tesseract(tesseract_cmd: str | None) -> None:
    """Define la ruta a Tesseract. Si no se entrega, intenta autodescubrir."""
    global _TESSERACT_CMD, _TESSDATA_DIR

    if tesseract_cmd:
        _TESSERACT_CMD = tesseract_cmd
        logger.info("Usando tesseract configurado: %s", tesseract_cmd)
        return

    cmd, tessdata = _descubrir_tesseract_embebido()
    if cmd:
        _TESSERACT_CMD = cmd
        _TESSDATA_DIR = tessdata
        logger.info("Usando tesseract embebido: %s (tessdata=%s)", cmd, tessdata)
    else:
        logger.info("Tesseract no embebido; se buscará en PATH.")


def _tesseract_disponible() -> bool:
    return shutil.which(_TESSERACT_CMD) is not None or os.path.exists(_TESSERACT_CMD)


def _base_args() -> list[str]:
    """Argumentos base para invocar Tesseract (incluye --tessdata-dir si aplica)."""
    args = [_TESSERACT_CMD]
    if _TESSDATA_DIR:
        args += ["--tessdata-dir", _TESSDATA_DIR]
    return args


def _idioma() -> str:
    """Devuelve 'spa' si está instalado; si no, 'eng'."""
    try:
        out = subprocess.run(
            _base_args() + ["--list-langs"], capture_output=True
        ).stdout.decode("utf-8", "replace")
        return _LANG_PREF if _LANG_PREF in out.split() else "eng"
    except Exception:  # noqa: BLE001
        return "eng"


def _run_tesseract(image_path: Path, lang: str, psm: str = _PSM) -> str:
    """Ejecuta Tesseract sobre un archivo y devuelve el texto (stdout)."""
    proc = subprocess.run(
        _base_args() + [str(image_path), "stdout", "-l", lang, "--psm", psm],
        capture_output=True,
    )
    return proc.stdout.decode("utf-8", "replace")


def _detectar_rotacion(image_path: Path) -> int:
    """Devuelve los grados a rotar (0/90/180/270) según el OSD de Tesseract."""
    try:
        proc = subprocess.run(
            _base_args() + [str(image_path), "stdout", "--psm", "0"],
            capture_output=True,
        )
        out = proc.stdout.decode("utf-8", "replace")
        m = re.search(r"Rotate:\s*(\d+)", out)
        if m:
            return int(m.group(1)) % 360
    except Exception as exc:  # noqa: BLE001
        logger.debug("OSD falló para %s: %s", image_path.name, exc)
    return 0


def _read_gray(path: Path) -> np.ndarray:
    """Carga la imagen en escala de grises (tolerante a rutas con acentos)."""
    try:
        with Image.open(path) as img:
            return np.array(img.convert("L"))
    except Exception as exc:  # noqa: BLE001
        raise OCRError(f"No se pudo abrir la imagen {path.name}: {exc}") from exc


def _rotar(gray: np.ndarray, grados: int) -> np.ndarray:
    if grados == 90:
        return cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
    if grados == 180:
        return cv2.rotate(gray, cv2.ROTATE_180)
    if grados == 270:
        return cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return gray


def _score(text: str) -> int:
    low = text.lower()
    return sum(1 for kw in _KEYWORDS if kw in low)


def _carpetas_temp(source: Path) -> list[Path]:
    """Carpetas candidatas para el archivo temporal, en orden de preferencia.

    Se evita /tmp como primera opción porque en macOS puede quedar aislado
    para el proceso hijo de Tesseract. La carpeta de la imagen siempre es
    accesible (de ahí se acaba de leer).
    """
    candidatas = [source.parent, Path(tempfile.gettempdir())]
    return candidatas


def _ocr_array(gray: np.ndarray, source: Path, lang: str) -> str:
    """Escribe el arreglo a un archivo temporal legible y ejecuta OCR."""
    nombre = f".ocr_{uuid.uuid4().hex}.png"
    ultimo_error = ""
    for carpeta in _carpetas_temp(source):
        tmp = carpeta / nombre
        try:
            if not cv2.imwrite(str(tmp), gray):
                # cv2 falla con rutas no-ASCII en algunos sistemas: usar PIL.
                Image.fromarray(gray).save(str(tmp))
            texto = _run_tesseract(tmp, lang)
            if texto.strip():
                return texto
            ultimo_error = "Tesseract no devolvió texto."
        except Exception as exc:  # noqa: BLE001
            ultimo_error = str(exc)
            logger.debug("OCR temporal falló en %s: %s", carpeta, exc)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    logger.warning("OCR sin texto para %s (%s)", source.name, ultimo_error)
    return ""


def image_to_text(path: Path) -> str:
    """Extrae texto de una imagen, corrigiendo la orientación automáticamente."""
    if not _tesseract_disponible():
        raise OCRError(
            "Tesseract no está instalado o no se encuentra. Instálalo "
            "(macOS: 'brew install tesseract tesseract-lang') o configura "
            "TESSERACT_CMD en el archivo .env."
        )

    lang = _idioma()
    grados = _detectar_rotacion(path)
    gray = _read_gray(path)
    if grados:
        logger.info("Rotando %s %d° (OSD).", path.name, grados)
        gray = _rotar(gray, grados)

    texto = _ocr_array(gray, path, lang)

    # Si el resultado es pobre, probar las otras orientaciones como respaldo.
    if _score(texto) < 2:
        logger.info("OCR pobre en %s; probando otras rotaciones.", path.name)
        base = _read_gray(path)
        for g in (90, 180, 270):
            alt = _ocr_array(_rotar(base, g), path, lang)
            if _score(alt) > _score(texto):
                texto, grados = alt, g

    if not texto.strip():
        raise OCRError(
            f"OCR no devolvió texto legible para {path.name}. "
            "Revisa la calidad de la imagen."
        )
    return texto
