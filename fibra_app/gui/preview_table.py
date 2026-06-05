"""Tabla de vista previa editable para las solicitudes."""

from __future__ import annotations

import customtkinter as ctk

from ..config import FRANJAS_VALIDAS
from ..core.models import Solicitud

# (clave del campo, etiqueta visible, ancho px)
_COLUMNAS: list[tuple[str, str, int]] = [
    ("fecha_venta", "Fecha Venta", 110),
    ("orden", "Orden", 110),
    ("nombre", "Nombre", 190),
    ("rut", "Rut", 115),
    ("direccion", "Dirección", 240),
    ("fecha_agenda", "Fecha Agenda", 110),
    ("contacto", "Contacto", 125),
    ("franja", "Franja", 125),
]


class _Fila:
    """Mantiene las variables y widgets de una fila editable."""

    def __init__(self, master: ctk.CTkFrame, solicitud: Solicitud, row: int) -> None:
        self.solicitud = solicitud
        self.widgets: dict[str, ctk.CTkBaseClass] = {}
        self.vars: dict[str, ctk.StringVar] = {}

        faltantes = set(solicitud.campos_faltantes())

        for col, (clave, _label, ancho) in enumerate(_COLUMNAS):
            valor = getattr(solicitud, clave, "")
            var = ctk.StringVar(value=valor)
            self.vars[clave] = var

            if clave == "franja":
                opciones = FRANJAS_VALIDAS + ([valor] if valor and valor not in FRANJAS_VALIDAS else [])
                widget = ctk.CTkOptionMenu(
                    master, values=opciones or FRANJAS_VALIDAS, variable=var, width=ancho
                )
            else:
                widget = ctk.CTkEntry(master, textvariable=var, width=ancho)
                # Resaltar visualmente los campos no detectados.
                etiqueta = dict((c[0], c[1]) for c in _COLUMNAS)[clave]
                if etiqueta in faltantes or _label_faltante(clave, faltantes):
                    widget.configure(border_color="#E06C75", border_width=2)

            widget.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            self.widgets[clave] = widget

    def to_solicitud(self) -> Solicitud:
        """Devuelve la solicitud con los valores actuales (posiblemente editados)."""
        for clave, var in self.vars.items():
            setattr(self.solicitud, clave, var.get().strip())
        self.solicitud.advertencias = [
            f"Campo '{c}' vacío" for c in self.solicitud.campos_faltantes()
        ]
        return self.solicitud


def _label_faltante(clave: str, faltantes: set[str]) -> bool:
    mapa = {
        "fecha_venta": "Fecha de Venta",
        "orden": "Orden",
        "nombre": "Nombre",
        "rut": "Rut",
        "direccion": "Dirección",
        "fecha_agenda": "Fecha Agenda",
        "contacto": "Contacto",
        "franja": "Franja",
    }
    return mapa.get(clave, "") in faltantes


class PreviewTable(ctk.CTkScrollableFrame):
    """Tabla con encabezados fijos y filas editables."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._filas: list[_Fila] = []
        self._construir_encabezados()
        for _col, (_clave, _label, ancho) in enumerate(_COLUMNAS):
            self.grid_columnconfigure(_col, weight=1, minsize=ancho)

    def _construir_encabezados(self) -> None:
        for col, (_clave, label, ancho) in enumerate(_COLUMNAS):
            lbl = ctk.CTkLabel(
                self, text=label, font=ctk.CTkFont(weight="bold"), width=ancho
            )
            lbl.grid(row=0, column=col, padx=2, pady=(2, 6), sticky="ew")

    def cargar(self, solicitudes: list[Solicitud]) -> None:
        """Reemplaza el contenido de la tabla."""
        self.limpiar()
        for i, sol in enumerate(solicitudes, start=1):
            self._filas.append(_Fila(self, sol, row=i))

    def limpiar(self) -> None:
        for fila in self._filas:
            for w in fila.widgets.values():
                w.destroy()
        self._filas.clear()

    def obtener_solicitudes(self) -> list[Solicitud]:
        return [f.to_solicitud() for f in self._filas]

    @property
    def vacia(self) -> bool:
        return not self._filas
