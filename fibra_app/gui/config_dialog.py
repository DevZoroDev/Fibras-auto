"""Diálogo de configuración: planilla de Google y cuenta de usuario."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from .. import config


class ConfigDialog(ctk.CTkToplevel):
    """Permite enlazar/cambiar la planilla y cerrar la sesión de Google.

    Al cerrar, ``self.sheet_id`` tiene el ID vigente y ``self.cuenta_reiniciada``
    indica si se cerró la sesión (para forzar re-login en la próxima conexión).
    """

    def __init__(self, master: ctk.CTkBaseClass, sheet_id: str,
                 token_path: Path) -> None:
        super().__init__(master)
        self._token_path = token_path
        self.sheet_id = sheet_id
        self.cuenta_reiniciada = False

        self.title("Configuración")
        self.geometry("560x340")
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)

        # --- Planilla de Google ---
        marco_pl = ctk.CTkFrame(self)
        marco_pl.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        marco_pl.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            marco_pl, text="Planilla de Google Sheets",
            font=ctk.CTkFont(weight="bold"), anchor="w"
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 2), sticky="w")
        ctk.CTkLabel(
            marco_pl, anchor="w", justify="left", text=(
                "Pega el enlace completo de la planilla o solo su ID.\n"
                "Ej: https://docs.google.com/spreadsheets/d/<ID>/edit"),
        ).grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 6), sticky="w")
        self.entry_sheet = ctk.CTkEntry(
            marco_pl, placeholder_text="Enlace o ID de la planilla")
        self.entry_sheet.grid(row=2, column=0, padx=(12, 8), pady=(0, 12), sticky="ew")
        if sheet_id:
            self.entry_sheet.insert(0, sheet_id)
        ctk.CTkButton(marco_pl, text="Guardar", width=90,
                      command=self._guardar_sheet).grid(
            row=2, column=1, padx=(0, 12), pady=(0, 12))

        # --- Cuenta de Google ---
        marco_ac = ctk.CTkFrame(self)
        marco_ac.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        marco_ac.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            marco_ac, text="Cuenta de Google",
            font=ctk.CTkFont(weight="bold"), anchor="w"
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 2), sticky="w")
        estado = ("Hay una sesión iniciada." if token_path.exists()
                  else "No hay sesión iniciada.")
        self.lbl_cuenta = ctk.CTkLabel(marco_ac, text=estado, anchor="w")
        self.lbl_cuenta.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")
        ctk.CTkButton(
            marco_ac, text="Cambiar cuenta de Google", width=200,
            fg_color="#B5651D", hover_color="#94521A",
            command=self._cambiar_cuenta
        ).grid(row=1, column=1, padx=(0, 12), pady=(0, 10))

        # --- Cerrar ---
        ctk.CTkButton(self, text="Cerrar", width=120, command=self._cerrar).grid(
            row=2, column=0, padx=16, pady=(8, 16), sticky="e")

        self.transient(master)  # type: ignore[arg-type]
        self.after(100, self._grab)
        self.entry_sheet.focus()

    def _grab(self) -> None:
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass

    def _guardar_sheet(self) -> None:
        nuevo = config.extraer_sheet_id(self.entry_sheet.get())
        if not nuevo:
            messagebox.showwarning(
                "Falta el ID", "Ingresa el enlace o ID de la planilla.",
                parent=self)
            return
        config.save_user_settings(sheet_id=nuevo)
        self.sheet_id = nuevo
        self.entry_sheet.delete(0, "end")
        self.entry_sheet.insert(0, nuevo)
        messagebox.showinfo(
            "Planilla guardada",
            f"ID guardado:\n{nuevo}\n\nUsa 'Probar conexión' para verificar.",
            parent=self)

    def _cambiar_cuenta(self) -> None:
        if not messagebox.askyesno(
            "Cambiar cuenta",
            "Se cerrará la sesión actual de Google. La próxima vez que envíes o "
            "pruebes la conexión, se abrirá el navegador para iniciar sesión con "
            "otra cuenta.\n\n¿Continuar?", parent=self):
            return
        config.cerrar_sesion_google(self._token_path)
        self.cuenta_reiniciada = True
        self.lbl_cuenta.configure(text="Sesión cerrada. Se pedirá login al conectar.")
        messagebox.showinfo(
            "Sesión cerrada",
            "Listo. Al conectar de nuevo podrás elegir otra cuenta de Google.",
            parent=self)

    def _cerrar(self) -> None:
        self.destroy()
