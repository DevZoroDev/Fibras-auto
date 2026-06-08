"""Verifica que to_row coloca cada campo en la columna correcta por ciudad."""

from fibra_app.config import CITIES, extraer_sheet_id
from fibra_app.core.models import Solicitud

# Encabezados reales de cada pestaña (hasta ESTADO).
HEADERS = {
    "IQUIQUE": ['TIENDA', 'FECHA VENTA', 'EJECUTIVO', 'ORDEN', 'NOMBRE', 'RUT',
                'DIRECCION', 'FECHA AGENDA', 'CONTACTO 1', 'CONTACTO 2', 'FRANJA',
                'ESTADO'],
    "ARICA I": ['TIENDA', 'FECHA VENTA', 'EJECUTIVO', 'ORDEN', 'NOMBRE', 'RUT',
                'DIRECCION', 'CONTACTO 1', 'CONTACTO 2', 'FECHA AGENDA', 'FRANJA',
                'ESTADO'],
    "ALTO HOSPICIO": ['TIENDA', 'FECHA VENTA', 'EJECUTIVO', 'ORDEN', 'NOMBRE',
                      'RUT', 'DIRECCION', 'FECHA AGENDA', 'CONTACTO 1',
                      'CONTACTO 2', 'FRANJA', 'ESTADO'],
    "COPIAPÓ": ['TIENDA', 'FECHA VENTA', 'EJECUTIVO', 'ORDEN', 'PRODUCTO',
                'NOMBRE', 'RUT', 'SERIE', 'DIRECCION', 'FECHA AGENDA',
                'CONTACTO 1', 'CONTACTO 2', 'FRANJA', 'ESTADO'],
    "VALLENAR": ['TIENDA', 'FECHA VENTA', 'EJECUTIVO', 'ORDEN', 'NOMBRE', 'RUT',
                 'PRODUCTO', 'DIRECCION', 'FECHA AGENDA', 'CONTACTO 1',
                 'CONTACTO 2', 'FRANJA', 'ESTADO'],
}

# Qué encabezado corresponde a cada campo lógico.
CAMPO_A_HEADER = {
    "fecha_venta": "FECHA VENTA", "ejecutivo": "EJECUTIVO", "orden": "ORDEN",
    "nombre": "NOMBRE", "rut": "RUT", "direccion": "DIRECCION",
    "fecha_agenda": "FECHA AGENDA", "contacto": "CONTACTO 1", "franja": "FRANJA",
    "estado": "ESTADO", "tienda": "TIENDA",
}


def _solicitud():
    return Solicitud(
        fecha_venta="01-06-2026", orden="12345", nombre="JUAN PEREZ",
        rut="11.111.111-1", direccion="CALLE FALSA 123",
        fecha_agenda="03-06-2026", contacto="+56999999999", franja="14:00-20:00",
    )


def test_mapeo_todas_las_ciudades():
    s = _solicitud()
    for clave, city in CITIES.items():
        fila = s.to_row(city, "ADS_TEST", "En Progreso")
        headers = HEADERS[clave]
        for campo, idx in city.columnas.items():
            assert headers[idx] == CAMPO_A_HEADER[campo], (
                f"{clave}: campo {campo} cayó en {headers[idx]} (col {idx})")


def test_tienda_por_ciudad():
    assert CITIES["COPIAPÓ"].tienda == "COPIAPO"
    assert CITIES["ARICA I"].tienda == "ARICA I"


def test_extraer_sheet_id():
    url = "https://docs.google.com/spreadsheets/d/ABC123_xyz-99/edit?gid=7#gid=7"
    assert extraer_sheet_id(url) == "ABC123_xyz-99"
    assert extraer_sheet_id("ABC123_xyz-99") == "ABC123_xyz-99"
