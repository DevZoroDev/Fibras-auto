"""Modelos de datos del dominio."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import CityConfig


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

    def to_row(self, city: "CityConfig", ejecutivo: str, estado: str) -> list[str]:
        """Convierte la solicitud en una fila según el mapeo de columnas de la ciudad.

        Cada ciudad tiene su propio orden de columnas; los campos se colocan en
        su índice correcto y las columnas no usadas (PRODUCTO, SERIE,
        CONTACTO 2…) quedan vacías. La fila abarca hasta la columna ESTADO,
        dejando intactas las columnas posteriores.
        """
        valores = {
            "tienda": city.tienda,
            "fecha_venta": self.fecha_venta,
            "ejecutivo": ejecutivo,
            "orden": self.orden,
            "nombre": self.nombre,
            "rut": self.rut,
            "direccion": self.direccion,
            "fecha_agenda": self.fecha_agenda,
            "contacto": self.contacto,
            "franja": self.franja,
            "estado": estado,
        }
        n = max(city.columnas.values()) + 1
        fila = [""] * n
        for campo, idx in city.columnas.items():
            fila[idx] = valores.get(campo, "")
        return fila

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
