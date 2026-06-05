"""Manejo de archivos: descubrimiento de imágenes y movimiento a /Procesadas."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

EXTENSIONES_IMAGEN = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
CARPETA_PROCESADAS = "Procesadas"


def listar_imagenes(carpeta: Path) -> list[Path]:
    """Lista las imágenes de una carpeta, ordenadas por nombre.

    Ignora la subcarpeta /Procesadas para no reprocesar.
    """
    if not carpeta.is_dir():
        raise NotADirectoryError(f"La carpeta no existe: {carpeta}")

    imagenes = [
        p
        for p in carpeta.iterdir()
        if p.is_file()
        and p.suffix.lower() in EXTENSIONES_IMAGEN
        and p.parent.name != CARPETA_PROCESADAS
    ]
    return sorted(imagenes, key=lambda p: p.name.lower())


def mover_a_procesadas(imagenes: list[Path], carpeta_origen: Path) -> list[Path]:
    """Mueve las imágenes a la subcarpeta /Procesadas, evitando duplicados.

    Si ya existe un archivo con el mismo nombre, agrega un sufijo numérico.
    Devuelve las rutas de destino.
    """
    destino_dir = carpeta_origen / CARPETA_PROCESADAS
    destino_dir.mkdir(exist_ok=True)

    movidas: list[Path] = []
    for img in imagenes:
        if not img.exists():
            logger.warning("No se pudo mover (ya no existe): %s", img)
            continue
        destino = _ruta_unica(destino_dir / img.name)
        try:
            shutil.move(str(img), str(destino))
            movidas.append(destino)
            logger.info("Movida %s -> %s", img.name, destino)
        except OSError as exc:
            logger.error("Error moviendo %s: %s", img.name, exc)
    return movidas


def _ruta_unica(destino: Path) -> Path:
    """Devuelve una ruta no usada agregando _1, _2, ... si es necesario."""
    if not destino.exists():
        return destino
    contador = 1
    while True:
        candidato = destino.with_stem(f"{destino.stem}_{contador}")
        if not candidato.exists():
            return candidato
        contador += 1
