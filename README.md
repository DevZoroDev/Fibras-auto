# Solicitudes de Fibra → Google Sheets

Aplicación de escritorio (Windows / macOS) que automatiza el registro de
solicitudes de instalación de fibra en una planilla de Google Sheets.

Los ejecutivos guardan **dos capturas de pantalla por venta** (vista de la orden
y vista del agendamiento) en una carpeta local. La app lee las imágenes con OCR,
las empareja, muestra una **vista previa editable** y escribe las filas en la
planilla.

---

## 1. Requisitos

- **Python 3.12+**
- **Tesseract OCR** (motor de OCR local, gratuito)
- Una **cuenta de servicio** de Google con acceso a la planilla

### Instalar Tesseract

**macOS** (Homebrew):
```bash
brew install tesseract tesseract-lang
```

**Windows**: descarga el instalador desde
<https://github.com/UB-Mannheim/tesseract/wiki> e instala incluyendo el idioma
español. Anota la ruta (ej. `C:\Program Files\Tesseract-OCR\tesseract.exe`) para
ponerla en `.env` → `TESSERACT_CMD`.

Verifica:
```bash
tesseract --version
```

---

## 2. Instalación del proyecto

```bash
# 1. Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar
cp .env.example .env             # y editar valores
```

---

## 3. Configurar Google Sheets API (OAuth de usuario)

La app inicia sesión con **tu propia cuenta de Gmail**, de modo que las
escrituras quedan registradas a tu nombre (no de una cuenta de servicio).

1. Entra a <https://console.cloud.google.com/> y crea (o elige) un proyecto.
2. Habilita la **Google Sheets API**.
3. Configura la **pantalla de consentimiento de OAuth**:
   *APIs y servicios → Pantalla de consentimiento de OAuth*. Tipo **Externo**,
   completa el nombre de la app y tu email. En **Usuarios de prueba**, agrega
   tu propio Gmail (mientras la app esté en modo *Testing*, solo esos usuarios
   pueden iniciar sesión).
4. Crea las credenciales: *Credenciales → Crear credenciales → ID de cliente
   de OAuth → Tipo de aplicación: **App de escritorio***. Descarga el JSON y
   guárdalo como **`credentials.json`** en la raíz del proyecto.
5. Copia el **ID de la planilla** desde su URL:
   `https://docs.google.com/spreadsheets/d/`**`<ID>`**`/edit`
   y pégalo en `.env` → `GOOGLE_SHEET_ID`.

La primera vez que pulses *Probar conexión* o *Enviar*, se abrirá el navegador
para que autorices el acceso con tu Gmail. El token queda cacheado en
`token.json` y se refresca solo; no tendrás que volver a iniciar sesión.

La hoja debe tener una pestaña con el nombre indicado en
`GOOGLE_WORKSHEET_NAME` (en este proyecto: `IQUIQUE`). Si está vacía, la app
escribe automáticamente la fila de encabezados.

### Columnas de la planilla

| Tienda | Fecha de Venta | Ejecutivo | Orden | Nombre | Rut | Dirección | Fecha Agenda | Contacto | Franja | Estado |
|--------|----------------|-----------|-------|--------|-----|-----------|--------------|----------|--------|--------|

- **Tienda** siempre = `Iquique` (configurable en `.env`).
- **Estado** siempre = `En Progreso`.
- **Franja** usa los valores `9:00-14:00` o `14:00-20:00` (coinciden con los
  desplegables de Sheets).

---

## 4. Configurar ejecutivos

Edita **`ejecutivos.json`** con la lista de ejecutivos. Aparecen en el
desplegable de la app:

```json
{
  "ejecutivos": ["Juan Pérez", "María González", "Pedro Soto"]
}
```

---

## 5. Uso

```bash
python run.py
```

1. **Selecciona la carpeta** donde descargaste las capturas de WhatsApp.
2. **Elige el ejecutivo** (se aplica a todas las filas del lote).
3. **Elige la ciudad** de destino (IQUIQUE, ARICA I, ALTO HOSPICIO, COPIAPÓ o
   VALLENAR). Cada ciudad escribe en su propia pestaña, respetando su orden de
   columnas particular.
4. Pulsa **Procesar Solicitudes**. La app hace OCR, empareja capturas por RUT y
   llena la tabla.
5. **Revisa y corrige** los campos en la vista previa. Los campos no detectados
   aparecen con borde rojo.
6. (Opcional) Pulsa **Probar conexión** para verificar el acceso a Sheets.
7. Pulsa **Enviar a Google Sheets**. Tras una carga exitosa, las imágenes se
   mueven a la subcarpeta **`/Procesadas`** para no reprocesarlas.

### Botón ⚙ Configuración
- **Enlazar planilla**: pega el enlace o ID de la planilla y guárdalo (queda en
  `config_local.json`, sin tocar el `.env`).
- **Cambiar cuenta de Google**: cierra la sesión actual; la próxima conexión
  abrirá el navegador para iniciar sesión con otra cuenta.

---

## 6. Empaquetado (PyInstaller)

> **Importante:** PyInstaller **no** compila para otra plataforma. El `.exe` de
> Windows debe generarse **en una máquina Windows**, y el `.app` de macOS en una
> Mac. No se puede crear el ejecutable de Windows desde macOS ni viceversa.

**Windows** (ejecutar en un PC con Windows y Python 3.12 instalado):
```bat
build_windows.bat
```
El script crea el entorno, empaqueta y copia los archivos de configuración
junto al `.exe` (queda en `dist\SolicitudesFibra\`).

**macOS:**
```bash
chmod +x build_macos.sh
./build_macos.sh
```

### Tesseract en el equipo de destino
PyInstaller **no empaqueta Tesseract**: debe estar instalado en el PC donde
corre la app.
- **Windows:** instala desde
  <https://github.com/UB-Mannheim/tesseract/wiki> (incluye el idioma *Spanish*)
  y define en `.env`:
  `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`
- **macOS:** `brew install tesseract tesseract-lang` (queda en el PATH).

### Archivos que deben acompañar al ejecutable
`.env`, `credentials.json`, `ejecutivos.json` y, si ya iniciaste sesión,
`token.json` (así no se vuelve a pedir login en el PC nuevo).

---

## 7. Estructura del proyecto

```
fibra_app/
├── config.py            # carga de .env, constantes, logging
├── main.py              # punto de entrada
├── core/
│   ├── models.py        # Solicitud (dataclass)
│   ├── processor.py     # OCR de carpeta + emparejamiento por RUT
│   └── files.py         # listar imágenes y mover a /Procesadas
├── ocr/
│   ├── engine.py        # Tesseract + preprocesamiento + auto-rotación
│   └── parsers.py       # extracción y normalización de campos
├── sheets/
│   └── client.py        # cliente de Google Sheets (cuenta de servicio)
└── gui/
    ├── app.py           # ventana principal (CustomTkinter)
    └── preview_table.py # tabla editable
```

---

## 8. Manejo de errores

La app detecta y muestra mensajes claros para:

- OCR fallido o imagen ilegible.
- RUT / Orden no encontrados (campo resaltado en rojo, editable).
- Fecha inválida (se intenta normalizar; si falla, queda vacía para corrección).
- Errores de conexión o escritura en Google Sheets.

Los detalles quedan registrados en `fibra_app.log`.

---

## 9. Pruebas

```bash
python -m pytest tests/ -v
```

Las pruebas validan los parsers de campos contra textos OCR de ejemplo (no
requieren Tesseract ni conexión a internet).
```
