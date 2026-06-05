#!/usr/bin/env bash
# ============================================================
#  Empaqueta la aplicación en un .app para macOS.
#  Requiere: Python 3.12+ y Tesseract (brew install tesseract).
# ============================================================
set -euo pipefail

echo "[1/3] Creando entorno virtual..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/3] Instalando dependencias..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "[3/3] Empaquetando con PyInstaller..."
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "SolicitudesFibra" \
  --collect-data customtkinter \
  run.py

cat <<'EOF'

============================================================
 Listo. La aplicación está en: dist/SolicitudesFibra.app

 IMPORTANTE: coloca junto a la app (o dentro de Contents/MacOS)
 los archivos de configuración:
   - .env
   - credentials.json
   - ejecutivos.json
============================================================
EOF
