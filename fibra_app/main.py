"""Punto de entrada de la aplicación."""

from __future__ import annotations

import logging

from .config import AppConfig, setup_logging
from .gui.app import run

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    logger.info("Iniciando aplicación de solicitudes de fibra.")
    config = AppConfig.load()
    run(config)


if __name__ == "__main__":
    main()
