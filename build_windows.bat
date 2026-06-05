@echo off
REM ============================================================
REM  Empaqueta la aplicacion en un ejecutable para Windows.
REM  EJECUTAR EN UNA MAQUINA WINDOWS (no se puede desde Mac).
REM  Requiere: Python 3.12+ instalado.
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- Elegir interprete de Python (prefiere 3.12) ---
set "PY=python"
where py >nul 2>nul && set "PY=py -3.12"

echo [1/4] Creando entorno virtual...
%PY% -m venv .venv
if errorlevel 1 goto :error
call .venv\Scripts\activate.bat

echo [2/4] Instalando dependencias...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/4] Empaquetando con PyInstaller...
pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "SolicitudesFibra" ^
  --collect-data customtkinter ^
  --collect-submodules google ^
  run.py
if errorlevel 1 goto :error

echo [4/4] Copiando archivos de configuracion junto al .exe...
set "DEST=dist\SolicitudesFibra"
if exist "ejecutivos.json"   copy /Y "ejecutivos.json"   "%DEST%\" >nul
if exist ".env"              copy /Y ".env"               "%DEST%\" >nul
if exist ".env.example"      copy /Y ".env.example"       "%DEST%\" >nul
if exist "credentials.json"  copy /Y "credentials.json"   "%DEST%\" >nul
if exist "token.json"        copy /Y "token.json"         "%DEST%\" >nul

echo.
echo ============================================================
echo  LISTO. La aplicacion esta en: %DEST%\SolicitudesFibra.exe
echo.
echo  REQUISITO EN ESTE PC: instalar Tesseract OCR
echo    https://github.com/UB-Mannheim/tesseract/wiki
echo    (incluye el idioma Spanish). Luego, en el archivo .env,
echo    define TESSERACT_CMD con la ruta a tesseract.exe, p.ej:
echo    TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
echo.
echo  Junto al .exe deben quedar: .env, credentials.json,
echo  ejecutivos.json (y token.json si ya iniciaste sesion).
echo ============================================================
goto :end

:error
echo.
echo *** ERROR durante el build. Revisa el mensaje anterior. ***

:end
endlocal
pause
