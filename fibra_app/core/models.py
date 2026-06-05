"""Modelos de datos del dominio."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Solicitud:
    """Una solicitud de instalación de fibra (un par de capturas).

    Los campos opcionales pueden quedar vacíos si el OCR no los detectó;
    el usuario los completa en la vista previa editable.
    """

    # Datos extraídos / editables
    fecha_venta: str = ""
    orden: str = ""
    nombre: str = ""
    rut: str = ""
    direccion: str = ""
    fecha_agenda: str = ""
    contacto: str = ""
    franja: str = ""

    # Trazabilidad (no se escribe en Sheets)
    imagenes: list[Path] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    def to_row(self, tienda: str, ejecutivo: str, estado: str) -> list[str]:
        """Convierte la solicitud en una fila alineada a las columnas A..L.

        Las columnas M..P (Motivo, Fecha Reagendada, etc.) no se escriben: la
        fila tiene 12 valores y se inserta desde la columna A, dejando intactas
        las columnas posteriores.
        """
        return [
            tienda,             # A  Tienda
            self.fecha_venta,   # B  Fecha Venta
            ejecutivo,          # C  Ejecutivo
            self.orden,         # D  Orden
            self.nombre,        # E  Nombre
            self.rut,           # F  Rut
            self.direccion,     # G  Dirección
            self.fecha_agenda,  # H  Fecha Agenda
            self.contacto,      # I  Contacto 1
            "",                 # J  Contacto 2 (no se extrae)
            self.franja,        # K  Franja
            estado,             # L  Estado
        ]

    def campos_faltantes(self) -> list[str]:
        """Lista de campos obligatorios que están vacíos."""
        requeridos = {
            "Fecha de Venta": self.fecha_venta,
            "Orden": self.orden,
            "Nombre": self.nombre,
            "Rut": self.rut,
            "Dirección": self.direccion,
            "Fecha Agenda": self.fecha_agenda,
            "Contacto": self.contacto,
            "Franja": self.franja,
        }
        return [nombre for nombre, valor in requeridos.items() if not valor.strip()]
