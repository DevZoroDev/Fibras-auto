"""Carga de configuración desde .env y constantes globales del proyecto."""

from __future__ import annotations

import json
import logging
import os
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


@dataclass
class AppConfig:
    """Configuración cargada desde el entorno."""

    credentials_path: Path  # client secret OAuth (credentials.json)
    token_path: Path        # token de usuario cacheado (token.json)
    sheet_id: str
    worksheet_name: str
    tesseract_cmd: str | None
    tienda: str
    ejecutivos: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> "AppConfig":
        credentials_path = _resolver(
            os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        token_path = _resolver(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))

        tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip() or None

        return cls(
            credentials_path=credentials_path,
            token_path=token_path,
            sheet_id=os.getenv("GOOGLE_SHEET_ID", "").strip(),
            worksheet_name=os.getenv("GOOGLE_WORKSHEET_NAME", "Solicitudes").strip(),
            tesseract_cmd=tesseract_cmd,
            tienda=os.getenv("TIENDA", "Iquique").strip() or "Iquique",
            ejecutivos=load_ejecutivos(),
        )


def _resolver(ruta: str) -> Path:
    """Convierte una ruta relativa en absoluta respecto a BASE_DIR."""
    p = Path(ruta)
    return p if p.is_absolute() else BASE_DIR / p


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
