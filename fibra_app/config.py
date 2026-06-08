"""Carga de configuración desde .env y constantes globales del proyecto."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def base_dir() -> Path:
    """Directorio base de la aplicación.

    Funciona tanto en desarrollo como dentro de un ejecutable PyInstaller.
    """
    if getattr(sys, "frozen", False):  # empaquetado con PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = base_dir()

# Cargar variables de entorno desde .env (si existe).
load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------------------------
# Constantes de negocio
# ---------------------------------------------------------------------------

# Columnas de la planilla real (hoja IQUIQUE), en orden exacto A..P.
# La app solo rellena de A a L; las columnas M..P las completan otros procesos.
SHEET_COLUMNS: list[str] = [
    "Tienda",            # A
    "Fecha Venta",       # B
    "Ejecutivo",         # C
    "Orden",             # D
    "Nombre",            # E
    "Rut",               # F
    "Dirección",         # G
    "Fecha Agenda",      # H
    "Contacto 1",        # I
    "Contacto 2",        # J  (no se extrae; queda vacío)
    "Franja",            # K
    "Estado",            # L
    "Motivo",            # M
    "Fecha Reagendada",  # N
    "Reingreso Orden",   # O
    "Validación Llamado al Cliente",  # P
]

# Valores fijos.
ESTADO_FIJO = "En Progreso"

# Franjas horarias válidas (deben coincidir con los desplegables de Sheets).
FRANJAS_VALIDAS: list[str] = ["9:00-14:00", "14:00-20:00"]


# ---------------------------------------------------------------------------
# Configuración por ciudad (cada pestaña tiene su propio orden de columnas)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CityConfig:
    """Mapeo de columnas de una pestaña de ciudad.

    ``columnas`` asocia cada campo lógico con su índice de columna (0 = A).
    Las columnas no mapeadas (PRODUCTO, SERIE, CONTACTO 2…) quedan vacías.
    """

    clave: str          # etiqueta para el selector
    worksheet: str      # nombre exacto de la pestaña en la planilla
    tienda: str         # valor de la columna TIENDA
    columnas: dict[str, int]


# Campos lógicos usados en el mapeo:
# tienda, fecha_venta, ejecutivo, orden, nombre, rut, direccion,
# fecha_agenda, contacto, franja, estado
_MAP_IQUIQUE = {
    "tienda": 0, "fecha_venta": 1, "ejecutivo": 2, "orden": 3, "nombre": 4,
    "rut": 5, "direccion": 6, "fecha_agenda": 7, "contacto": 8, "franja": 10,
    "estado": 11,
}
_MAP_ARICA = {
    "tienda": 0, "fecha_venta": 1, "ejecutivo": 2, "orden": 3, "nombre": 4,
    "rut": 5, "direccion": 6, "contacto": 7, "fecha_agenda": 9, "franja": 10,
    "estado": 11,
}
_MAP_COPIAPO = {
    "tienda": 0, "fecha_venta": 1, "ejecutivo": 2, "orden": 3, "nombre": 5,
    "rut": 6, "direccion": 8, "fecha_agenda": 9, "contacto": 10, "franja": 12,
    "estado": 13,
}
_MAP_VALLENAR = {
    "tienda": 0, "fecha_venta": 1, "ejecutivo": 2, "orden": 3, "nombre": 4,
    "rut": 5, "direccion": 7, "fecha_agenda": 8, "contacto": 9, "franja": 11,
    "estado": 12,
}

# Orden de aparición en el selector de ciudad.
CITIES: dict[str, CityConfig] = {
    "IQUIQUE":       CityConfig("IQUIQUE", "IQUIQUE", "IQUIQUE", _MAP_IQUIQUE),
    "ARICA I":       CityConfig("ARICA I", "ARICA I", "ARICA I", _MAP_ARICA),
    "ALTO HOSPICIO": CityConfig("ALTO HOSPICIO", "ALTO HOSPICIO", "ALTO HOSPICIO",
                                _MAP_IQUIQUE),
    "COPIAPÓ":       CityConfig("COPIAPÓ", "COPIAPÓ", "COPIAPO", _MAP_COPIAPO),
    "VALLENAR":      CityConfig("VALLENAR", "VALLENAR", "VALLENAR", _MAP_VALLENAR),
}


def extraer_sheet_id(texto: str) -> str:
    """Extrae el ID de una planilla desde una URL completa o lo devuelve tal cual."""
    texto = (texto or "").strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", texto)
    if m:
        return m.group(1)
    return texto


@dataclass
class AppConfig:
    """Configuración cargada desde el entorno y los ajustes locales."""

    credentials_path: Path  # client secret OAuth (credentials.json)
    token_path: Path        # token de usuario cacheado (token.json)
    sheet_id: str
    tesseract_cmd: str | None
    ciudad: str             # ciudad/pestaña por defecto
    ejecutivos: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> "AppConfig":
        credentials_path = _resolver(
            os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        token_path = _resolver(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))
        tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip() or None

        # Los ajustes locales (editables desde la app) tienen prioridad sobre .env.
        ajustes = load_user_settings()
        sheet_id = (ajustes.get("sheet_id")
                    or os.getenv("GOOGLE_SHEET_ID", "")).strip()
        ciudad = ajustes.get("ciudad") or next(iter(CITIES))
        if ciudad not in CITIES:
            ciudad = next(iter(CITIES))

        return cls(
            credentials_path=credentials_path,
            token_path=token_path,
            sheet_id=sheet_id,
            tesseract_cmd=tesseract_cmd,
            ciudad=ciudad,
            ejecutivos=load_ejecutivos(),
        )


def _resolver(ruta: str) -> Path:
    """Convierte una ruta relativa en absoluta respecto a BASE_DIR."""
    p = Path(ruta)
    return p if p.is_absolute() else BASE_DIR / p


# ---------------------------------------------------------------------------
# Ajustes locales editables desde la app (config_local.json)
# ---------------------------------------------------------------------------


def config_local_path() -> Path:
    return BASE_DIR / "config_local.json"


def load_user_settings() -> dict:
    """Lee los ajustes guardados por el usuario (sheet_id, ciudad)."""
    try:
        return json.loads(config_local_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        logger.error("config_local.json mal formado: %s", exc)
        return {}


def save_user_settings(**cambios) -> None:
    """Actualiza y guarda ajustes locales (solo las claves entregadas)."""
    data = load_user_settings()
    for k, v in cambios.items():
        if v is not None:
            data[k] = v
    config_local_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("Ajustes locales guardados: %s", list(cambios))


def cerrar_sesion_google(token_path: Path) -> bool:
    """Borra el token de usuario para forzar un nuevo inicio de sesión."""
    if token_path.exists():
        token_path.unlink()
        logger.info("Sesión de Google cerrada (token eliminado).")
        return True
    return False


def ejecutivos_path() -> Path:
    """Ruta del archivo de ejecutivos."""
    return BASE_DIR / "ejecutivos.json"


def load_ejecutivos() -> list[str]:
    """Lee la lista configurable de ejecutivos desde ejecutivos.json."""
    path = ejecutivos_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ejecutivos = data.get("ejecutivos", [])
        if isinstance(ejecutivos, list) and ejecutivos:
            return [str(e) for e in ejecutivos]
        logger.warning("ejecutivos.json no contiene una lista válida.")
    except FileNotFoundError:
        logger.warning("No se encontró ejecutivos.json en %s", path)
    except json.JSONDecodeError as exc:
        logger.error("ejecutivos.json mal formado: %s", exc)
    return ["(Sin ejecutivos configurados)"]


def save_ejecutivos(ejecutivos: list[str]) -> None:
    """Guarda la lista de ejecutivos en ejecutivos.json (sin duplicados)."""
    # Normaliza: quita espacios, descarta vacíos y duplicados conservando orden.
    vistos: set[str] = set()
    limpios: list[str] = []
    for e in ejecutivos:
        nombre = str(e).strip()
        if nombre and nombre not in vistos:
            vistos.add(nombre)
            limpios.append(nombre)

    path = ejecutivos_path()
    path.write_text(
        json.dumps({"ejecutivos": limpios}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Lista de ejecutivos guardada (%d).", len(limpios))


def setup_logging() -> None:
    """Configura logging a consola y a archivo."""
    log_file = BASE_DIR / "fibra_app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
