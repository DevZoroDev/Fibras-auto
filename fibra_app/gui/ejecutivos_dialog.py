"""Diálogo para agregar / quitar ejecutivos desde la app."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from .. import config


class EjecutivosDialog(ctk.CTkToplevel):
    """Ventana modal para editar la lista de ejecutivos.

    Al cerrarse con "Guardar", persiste en ejecutivos.json. La lista resultante
    queda disponible en ``self.resultado`` (o ``None`` si se canceló).
    """

    def __init__(self, master: ctk.CTkBaseClass, ejecutivos: list[str]) -> None:
        super().__init__(master)
        self.resultado: list[str] | None = None
        self._ejecutivos = [e for e in ejecutivos if e != "(Sin ejecutivos configurados)"]

        self.title("Gestionar ejecutivos")
        self.geometry("420x460")
        self.resizable(False, True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- Alta de nuevo ejecutivo ---
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        self.entry_nuevo = ctk.CTkEntry(top, placeholder_text="Nuevo ejecutivo (ej. ADS_XXXX)")
        self.entry_nuevo.grid(row=0, column=0, padx=(8, 8), pady=8, sticky="ew")
        self.entry_nuevo.bind("<Return>", lambda _e: self._agregar())
        ctk.CTkButton(top, text="Agregar", width=90, command=self._agregar).grid(
            row=0, column=1, padx=(0, 8), pady=8
        )

        ctk.CTkLabel(self, text="Ejecutivos:", anchor="w").grid(
            row=1, column=0, padx=20, pady=(4, 0), sticky="w"
        )

        # --- Lista con botón eliminar por fila ---
        self.lista = ctk.CTkScrollableFrame(self)
        self.lista.grid(row=2, column=0, padx=16, pady=8, sticky="nsew")
        self.lista.grid_columnconfigure(0, weight=1)

        # --- Botones inferiores ---
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, padx=16, pady=(4, 16), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            bottom, text="Cancelar", width=110, fg_color="gray40",
            hover_color="gray30", command=self._cancelar
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(bottom, text="Guardar", width=130, command=self._guardar).grid(
            row=0, column=1, sticky="e"
        )

        self._refrescar_lista()

        # Hacer modal.
        self.transient(master)  # type: ignore[arg-type]
        self.after(100, self._grab)
        self.entry_nuevo.focus()

    def _grab(self) -> None:
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001 - en algunos WM puede fallar el grab
            pass

    # ------------------------------------------------------------------ datos
    def _agregar(self) -> None:
        nombre = self.entry_nuevo.get().strip()
        if not nombre:
            return
        if nombre in self._ejecutivos:
            messagebox.showinfo("Duplicado", f"'{nombre}' ya está en la lista.", parent=self)
            return
        self._ejecutivos.append(nombre)
        self.entry_nuevo.delete(0, "end")
        self._refrescar_lista()

    def _eliminar(self, nombre: str) -> None:
        if nombre in self._ejecutivos:
            self._ejecutivos.remove(nombre)
            self._refrescar_lista()

    def _refrescar_lista(self) -> None:
        for widget in self.lista.winfo_children():
            widget.destroy()
        if not self._ejecutivos:
            ctk.CTkLabel(self.lista, text="(Sin ejecutivos)", text_color="gray").grid(
                row=0, column=0, padx=8, pady=8, sticky="w"
            )
            return
        for i, nombre in enumerate(self._ejecutivos):
            ctk.CTkLabel(self.lista, text=nombre, anchor="w").grid(
                row=i, column=0, padx=(8, 4), pady=3, sticky="ew"
            )
            ctk.CTkButton(
                self.lista, text="✕", width=32, fg_color="#E06C75",
                hover_color="#C75A63", command=lambda n=nombre: self._eliminar(n)
            ).grid(row=i, column=1, padx=(0, 8), pady=3)

    # --------------------------------------------------------------- acciones
    def _guardar(self) -> None:
        if not self._ejecutivos:
            messagebox.showwarning(
                "Lista vacía", "Agrega al menos un ejecutivo.", parent=self
            )
            return
        try:
            config.save_ejecutivos(self._ejecutivos)
        except OSError as exc:
            messagebox.showerror(
                "Error al guardar", f"No se pudo guardar: {exc}", parent=self
            )
            return
        self.resultado = list(self._ejecutivos)
        self.destroy()

    def _cancelar(self) -> None:
        self.resultado = None
        self.destroy()
