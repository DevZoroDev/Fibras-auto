# Generar el .exe portable de Windows (GitHub Actions)

Como **PyInstaller no compila cross-platform**, no se puede crear un `.exe` de
Windows desde macOS. Esta guía configura un workflow gratis en GitHub Actions
que lo compila por ti en un runner Windows. Tú solo descargas el ZIP listo.

## Lo que obtendrás
Un ZIP que contiene una carpeta **portable** con:
- `SolicitudesFibra.exe` — la app.
- `tesseract/` — Tesseract OCR embebido con idioma español (no necesitas
  instalarlo en el PC destino).
- `ejecutivos.json`, `.env`, `LEEME.txt` — configuración.

Tamaño aproximado: **150–180 MB** comprimido.

## Pasos (una sola vez)

### 1. Crear repositorio privado en GitHub
1. Entra a <https://github.com/new>.
2. Nombre: `solicitudes-fibra` (o el que quieras).
3. Visibilidad: **Privado** (importante: aunque el `.gitignore` excluye los
   secretos, mejor mantener privado el repo de la empresa).
4. **No** marques "Add README" ni `.gitignore` (ya los tenemos).
5. **Create repository**.

### 2. Subir el código por primera vez
Desde la terminal en la carpeta del proyecto:

```bash
cd /Users/juansebastian/Proyecto_entel
git init
git add .
git commit -m "Versión inicial"
git branch -M main
git remote add origin https://github.com/<TU_USUARIO>/solicitudes-fibra.git
git push -u origin main
```

> En el push te pedirá usuario/contraseña. La "contraseña" debe ser un
> **Personal Access Token** (PAT) de GitHub (`https://github.com/settings/tokens`),
> con permiso `repo`. Lo creas, lo copias, y lo pegas como password.

**Importante:** revisa antes de subir que estos archivos **no** aparezcan
en el commit (deben estar ignorados):
```bash
git status --ignored
```
Deberías ver `.env`, `credentials.json`, `token.json` y `backup_*.json` en la
lista de "Ignored files".

### 3. Ejecutar el workflow
1. Entra al repositorio en github.com.
2. Pestaña **Actions** → si te pide habilitar workflows, **Enable**.
3. En la lista lateral, elige **Build Windows portable**.
4. Botón **Run workflow** (arriba a la derecha) → **Run workflow**.
5. Espera ~5–8 minutos a que termine (verás un ✅ verde).

### 4. Descargar el .exe
1. Click en la corrida verde recién terminada.
2. Al final de la página verás la sección **Artifacts**.
3. Descarga **`SolicitudesFibra-Windows`** (es un ZIP).
4. Descomprime; dentro tienes la carpeta portable.

## Primer uso en el PC con Windows
1. Copia la carpeta `SolicitudesFibra/` donde quieras.
2. Coloca tu **`credentials.json`** (OAuth de Google) dentro de la carpeta.
3. Edita **`.env`** y completa `GOOGLE_SHEET_ID`.
4. Edita **`ejecutivos.json`** con tu lista.
5. Doble clic en **`SolicitudesFibra.exe`**.
6. La primera vez se abrirá el navegador para iniciar sesión con tu Gmail.

> Si quieres saltarte el login del navegador (porque ya iniciaste sesión en el
> Mac), copia también tu `token.json` junto al `.exe`.

## Builds posteriores
Cada vez que cambies código y hagas `git push`, GitHub Actions lanza un build
nuevo automáticamente. También puedes lanzarlo manualmente con **Run workflow**
cuando quieras. Cada artefacto queda disponible 30 días.

## Solución de problemas

**"git push" pide credenciales y rechaza la contraseña.** GitHub no acepta
contraseña normal desde hace años; necesitas un Personal Access Token (ver
paso 2). Alternativa: usa GitHub Desktop (interfaz gráfica) o instala
`gh` (GitHub CLI) y haz `gh auth login`.

**El workflow falla con "Tesseract no está en PATH".** Los runners Windows
de GitHub Actions deberían traerlo. Si por alguna razón no, el workflow ya
está preparado para instalarlo vía Chocolatey automáticamente.

**El .exe abre y se cierra al instante en el PC destino.** Abre una consola
(`cmd.exe`) en esa carpeta y ejecuta `SolicitudesFibra.exe`; verás el error.
Lo más común: falta `credentials.json` en la misma carpeta.
