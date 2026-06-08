"""Ventana principal de la aplicación."""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import __version__
from .. import config
from ..config import CITIES, ESTADO_FIJO, AppConfig
from ..core import files, processor
from ..core.models import Solicitud
from ..ocr import engine
from ..sheets.client import SheetsClient, SheetsError
from .config_dialog import ConfigDialog
from .ejecutivos_dialog import EjecutivosDialog
from .preview_table import PreviewTable

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config_app = config
        self._cola: queue.Queue = queue.Queue()
        self._carpeta: Path | None = None
        self._ultimo_resultado: processor.ResultadoProceso | None = None

        engine.configure_tesseract(config.tesseract_cmd)

        self.title(f"Solicitudes de Fibra → Google Sheets  v{__version__}")
        self.geometry("1180x680")
        self.minsize(960, 560)

        self._construir_ui()
        self.after(120, self._procesar_cola)

    # ------------------------------------------------------------------ UI
    def _construir_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- Barra superior de controles ---
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Carpeta de imágenes:").grid(
            row=0, column=0, padx=(12, 8), pady=12, sticky="w"
        )
        self.entry_carpeta = ctk.CTkEntry(top, placeholder_text="Selecciona una carpeta…")
        self.entry_carpeta.grid(row=0, column=1, padx=8, pady=12, sticky="ew")
        ctk.CTkButton(top, text="Examinar…", width=110, command=self._elegir_carpeta).grid(
            row=0, column=2, padx=(8, 12), pady=12
        )

        ctk.CTkLabel(top, text="Ejecutivo:").grid(
            row=1, column=0, padx=(12, 8), pady=(0, 12), sticky="w"
        )
        ejecutivo_frame = ctk.CTkFrame(top, fg_color="transparent")
        ejecutivo_frame.grid(row=1, column=1, padx=8, pady=(0, 12), sticky="w")
        self.menu_ejecutivo = ctk.CTkOptionMenu(
            ejecutivo_frame, values=self.config_app.ejecutivos
        )
        self.menu_ejecutivo.grid(row=0, column=0)
        ctk.CTkButton(
            ejecutivo_frame, text="Gestionar…", width=100,
            command=self._gestionar_ejecutivos
        ).grid(row=0, column=1, padx=(8, 0))

        self.btn_procesar = ctk.CTkButton(
            top, text="Procesar Solicitudes", command=self._on_procesar, width=200
        )
        self.btn_procesar.grid(row=1, column=2, padx=(8, 12), pady=(0, 12))

        # Selector de ciudad (define a qué pestaña se escriben las solicitudes).
        ctk.CTkLabel(top, text="Ciudad:").grid(
            row=2, column=0, padx=(12, 8), pady=(0, 12), sticky="w"
        )
        self.menu_ciudad = ctk.CTkOptionMenu(
            top, values=list(CITIES.keys()), command=self._on_ciudad_cambiada
        )
        self.menu_ciudad.set(self.config_app.ciudad)
        self.menu_ciudad.grid(row=2, column=1, padx=8, pady=(0, 12), sticky="w")
        ctk.CTkButton(
            top, text="⚙ Configuración", width=150, command=self._abrir_configuracion
        ).grid(row=2, column=2, padx=(8, 12), pady=(0, 12))

        # --- Estado / progreso ---
        estado = ctk.CTkFrame(self, fg_color="transparent")
        estado.grid(row=1, column=0, padx=16, sticky="ew")
        estado.grid_columnconfigure(0, weight=1)
        self.lbl_estado = ctk.CTkLabel(estado, text="Listo.", anchor="w")
        self.lbl_estado.grid(row=0, column=0, sticky="ew")
        self.progress = ctk.CTkProgressBar(estado)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, padx=8, sticky="e")
        self.progress.grid_remove()

        # --- Tabla de vista previa ---
        self.tabla = PreviewTable(self, label_text="Vista previa (editable)")
        self.tabla.grid(row=2, column=0, padx=16, pady=8, sticky="nsew")

        # --- Barra inferior ---
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, padx=16, pady=(4, 16), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            bottom, text="Probar conexión", width=150, command=self._on_probar_conexion
        ).grid(row=0, column=0, sticky="w")

        self.btn_enviar = ctk.CTkButton(
            bottom,
            text="Enviar a Google Sheets",
            width=220,
            command=self._on_enviar,
            state="disabled",
        )
        self.btn_enviar.grid(row=0, column=1, sticky="e")

    # -------------------------------------------------------------- acciones
    def _elegir_carpeta(self) -> None:
        ruta = filedialog.askdirectory(title="Selecciona la carpeta de imágenes")
        if ruta:
            self._carpeta = Path(ruta)
            self.entry_carpeta.delete(0, "end")
            self.entry_carpeta.insert(0, ruta)

    def _gestionar_ejecutivos(self) -> None:
        seleccion_previa = self.menu_ejecutivo.get()
        dialog = EjecutivosDialog(self, self.config_app.ejecutivos)
        self.wait_window(dialog)
        if dialog.resultado is None:
            return  # se canceló

        self.config_app.ejecutivos = dialog.resultado
        self.menu_ejecutivo.configure(values=dialog.resultado)
        # Conservar la selección previa si sigue existiendo.
        if seleccion_previa in dialog.resultado:
            self.menu_ejecutivo.set(seleccion_previa)
        else:
            self.menu_ejecutivo.set(dialog.resultado[0])
        self.lbl_estado.configure(
            text=f"Lista de ejecutivos actualizada ({len(dialog.resultado)})."
        )

    def _on_ciudad_cambiada(self, ciudad: str) -> None:
        self.config_app.ciudad = ciudad
        config.save_user_settings(ciudad=ciudad)
        self.lbl_estado.configure(text=f"Ciudad de destino: {ciudad}")

    def _abrir_configuracion(self) -> None:
        dialog = ConfigDialog(
            self, self.config_app.sheet_id, self.config_app.token_path
        )
        self.wait_window(dialog)
        self.config_app.sheet_id = dialog.sheet_id
        if dialog.cuenta_reiniciada:
            self.lbl_estado.configure(
                text="Sesión de Google cerrada. Se pedirá login al conectar."
            )
        else:
            self.lbl_estado.configure(text="Configuración actualizada.")

    def _on_procesar(self) -> None:
        ruta_txt = self.entry_carpeta.get().strip()
        if not ruta_txt:
            messagebox.showwarning("Falta carpeta", "Selecciona una carpeta primero.")
            return
        carpeta = Path(ruta_txt)
        self._carpeta = carpeta

        try:
            imagenes = files.listar_imagenes(carpeta)
        except NotADirectoryError as exc:
            messagebox.showerror("Carpeta inválida", str(exc))
            return

        if not imagenes:
            messagebox.showinfo(
                "Sin imágenes", "No se encontraron imágenes en la carpeta."
            )
            return

        self._set_ocupado(True, "Procesando imágenes…")
        self.progress.grid()
        self.progress.set(0)
        self.btn_enviar.configure(state="disabled")

        threading.Thread(
            target=self._worker_procesar, args=(imagenes,), daemon=True
        ).start()

    def _worker_procesar(self, imagenes: list[Path]) -> None:
        def progreso(actual: int, total: int, msg: str) -> None:
            self._cola.put(("progreso", (actual, total, msg)))

        try:
            resultado = processor.procesar_carpeta(imagenes, progreso=progreso)
            self._cola.put(("procesado", resultado))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error inesperado al procesar")
            self._cola.put(("error", f"Error al procesar: {exc}"))

    def _aviso_login(self) -> None:
        """Avisa al usuario que se abrirá el navegador (solo si no hay sesión)."""
        if not self.config_app.token_path.exists():
            messagebox.showinfo(
                "Iniciar sesión con Google",
                "Se abrirá tu navegador para que inicies sesión con tu cuenta de "
                "Google y autorices el acceso a la planilla.\n\n"
                "• Elige tu cuenta de Gmail.\n"
                "• Si aparece 'Google no verificó esta app', pulsa "
                "\"Configuración avanzada\" → \"Ir a … (no seguro)\".\n"
                "• Acepta el acceso.\n\n"
                "Esto solo se pide la primera vez en este equipo.",
            )

    def _on_probar_conexion(self) -> None:
        self._aviso_login()
        self._set_ocupado(True, "Probando conexión con Google Sheets…")
        threading.Thread(target=self._worker_probar, daemon=True).start()

    def _worker_probar(self) -> None:
        try:
            cliente = self._crear_cliente()
            titulo = cliente.probar_conexion()
            self._cola.put(("conexion_ok", titulo))
        except SheetsError as exc:
            self._cola.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            self._cola.put(("error", f"Error de conexión: {exc}"))

    def _on_enviar(self) -> None:
        if self.tabla.vacia:
            messagebox.showinfo("Sin datos", "No hay solicitudes para enviar.")
            return

        solicitudes = self.tabla.obtener_solicitudes()
        faltantes = [s for s in solicitudes if s.campos_faltantes()]
        if faltantes:
            detalle = "\n".join(
                f"• Fila {i + 1}: faltan {', '.join(s.campos_faltantes())}"
                for i, s in enumerate(solicitudes)
                if s.campos_faltantes()
            )
            seguir = messagebox.askyesno(
                "Campos incompletos",
                f"Algunas filas tienen campos vacíos:\n\n{detalle}\n\n"
                "¿Deseas enviarlas de todas formas?",
            )
            if not seguir:
                return

        self._aviso_login()
        self._set_ocupado(True, "Enviando a Google Sheets…")
        threading.Thread(
            target=self._worker_enviar, args=(solicitudes,), daemon=True
        ).start()

    def _worker_enviar(self, solicitudes: list[Solicitud]) -> None:
        try:
            cliente = self._crear_cliente()
            ejecutivo = self.menu_ejecutivo.get()
            ciudad = CITIES[self.config_app.ciudad]
            filas = [
                s.to_row(ciudad, ejecutivo, ESTADO_FIJO)
                for s in solicitudes
            ]
            escritas = cliente.agregar_filas(filas, worksheet_name=ciudad.worksheet)

            # Mover imágenes procesadas tras escritura exitosa.
            movidas = 0
            if self._carpeta:
                imagenes: list[Path] = []
                for s in solicitudes:
                    imagenes.extend(s.imagenes)
                movidas = len(files.mover_a_procesadas(imagenes, self._carpeta))

            self._cola.put(("enviado", (escritas, movidas)))
        except SheetsError as exc:
            self._cola.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error inesperado al enviar")
            self._cola.put(("error", f"Error al enviar: {exc}"))

    # ---------------------------------------------------------------- helpers
    def _crear_cliente(self) -> SheetsClient:
        return SheetsClient(
            credentials_path=self.config_app.credentials_path,
            token_path=self.config_app.token_path,
            sheet_id=self.config_app.sheet_id,
        )

    def _set_ocupado(self, ocupado: bool, mensaje: str = "") -> None:
        estado = "disabled" if ocupado else "normal"
        self.btn_procesar.configure(state=estado)
        if mensaje:
            self.lbl_estado.configure(text=mensaje)

    def _procesar_cola(self) -> None:
        """Procesa mensajes de los hilos de trabajo en el hilo de la GUI."""
        try:
            while True:
                tipo, dato = self._cola.get_nowait()
                self._manejar_mensaje(tipo, dato)
        except queue.Empty:
            pass
        self.after(120, self._procesar_cola)

    def _manejar_mensaje(self, tipo: str, dato) -> None:  # noqa: ANN001
        if tipo == "progreso":
            actual, total, msg = dato
            self.progress.set(actual / total if total else 0)
            self.lbl_estado.configure(text=f"{msg}  ({actual}/{total})")
        elif tipo == "procesado":
            self._on_procesado(dato)
        elif tipo == "conexion_ok":
            self._set_ocupado(False)
            self.lbl_estado.configure(text=f"Conexión OK: '{dato}'")
            messagebox.showinfo("Conexión exitosa", f"Planilla: {dato}")
        elif tipo == "enviado":
            escritas, movidas = dato
            self._set_ocupado(False)
            self.lbl_estado.configure(
                text=f"Enviado: {escritas} fila(s), {movidas} imagen(es) movidas."
            )
            self.tabla.limpiar()
            self.btn_enviar.configure(state="disabled")
            messagebox.showinfo(
                "Carga exitosa",
                f"Se escribieron {escritas} solicitud(es) en Google Sheets.\n"
                f"{movidas} imagen(es) movidas a /Procesadas.",
            )
        elif tipo == "error":
            self._set_ocupado(False)
            self.progress.grid_remove()
            self.lbl_estado.configure(text="Error.")
            messagebox.showerror("Error", str(dato))

    def _on_procesado(self, resultado: processor.ResultadoProceso) -> None:
        self._ultimo_resultado = resultado
        self._set_ocupado(False)
        self.progress.grid_remove()

        if resultado.solicitudes:
            self.tabla.cargar(resultado.solicitudes)
            self.btn_enviar.configure(state="normal")
            self.lbl_estado.configure(
                text=f"{len(resultado.solicitudes)} solicitud(es) lista(s). "
                "Revisa y corrige antes de enviar."
            )
        else:
            self.lbl_estado.configure(text="No se pudieron armar solicitudes.")

        if resultado.errores:
            messagebox.showwarning(
                "Avisos durante el proceso",
                "\n".join(f"• {e}" for e in resultado.errores[:15]),
            )


def run(config: AppConfig) -> None:
    app = App(config)
    app.mainloop()
