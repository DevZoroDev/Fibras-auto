"""Pruebas de los parsers contra textos OCR de ejemplo (capturas reales)."""

from fibra_app.ocr import parsers
from fibra_app.ocr.parsers import TipoCaptura

# Texto aproximado del OCR de la Captura 1 (información de la orden).
TEXTO_ORDEN = """\
Mabel Cynthia Moreira Moreira / Titular
10.994.246-4 / 1-6B790IOY / DCL001187340603
ID de solicitud 1-6B74ROVO
Informacion de la orden ID: 79283817
PONR Not Reached
Tipo Venta Servicios
Estado En progreso
Fecha de inicio 02-06-26
Milestone actual CreateRequiredInventory_Completed
ID Carrito CSE00134926535
"""

# Texto aproximado del OCR de la Captura 2 (detalle del agendamiento).
TEXTO_AGENDA = """\
Mabel Cynthia Moreira Moreira / Titular
10.994.246-4 / 1-6B790IOY
Especificaciones
Dirección
Pasaje Los Suspiros 949, Depto 3442, Iquique, Tarapaca, Chile
Delivery
Agendamiento instalación
Detalle del agendamiento
Dirección de agendamiento Estado
El Carmelo 3442, Iquique, Orden de trabajo creada
Tarapaca, Chile S/N
Actividades
Fecha Rango horario
Miércoles 03-06-2026 14:00 - 20:00
Nombre contacto que recibe RUT Contacto
Mabel Cynthia Moreira 10994246-4 +56987153787
Técnico asignado RUT Servicio
"""


def test_clasificar():
    assert parsers.clasificar(TEXTO_ORDEN) == TipoCaptura.ORDEN
    assert parsers.clasificar(TEXTO_AGENDA) == TipoCaptura.AGENDAMIENTO


def test_parse_orden():
    datos = parsers.parse_orden(TEXTO_ORDEN)
    assert datos["orden"] == "79283817"
    assert datos["rut"] == "10.994.246-4"
    assert datos["fecha_venta"] == "02-06-2026"
    assert "Moreira" in datos["nombre"]


def test_parse_agendamiento():
    datos = parsers.parse_agendamiento(TEXTO_AGENDA)
    assert datos["fecha_agenda"] == "03-06-2026"
    assert datos["contacto"] == "987153787"          # sin +56
    assert datos["franja"] == "14:00-20:00"
    assert datos["direccion"] == "El Carmelo 3442"   # sin comuna/ciudad
    assert "Los Suspiros" not in datos["direccion"]  # no debe tomar la otra dir.


def test_normalizar_franja():
    assert parsers.normalizar_franja("09:00 - 14:00") == "9:00-14:00"
    assert parsers.normalizar_franja("14:00 - 20:00") == "14:00-20:00"


def test_normalizar_rut():
    assert parsers.normalizar_rut("10994246-4") == "10.994.246-4"
    assert parsers.normalizar_rut("10.994.246-4") == "10.994.246-4"


def test_emparejar_por_rut():
    assert parsers.rut_digitos("10.994.246-4") == parsers.rut_digitos("10994246-4")


def test_rut_valido():
    # RUTs reales (dígito verificador correcto)
    assert parsers.rut_valido("10.994.246-4")
    assert parsers.rut_valido("14.105.611-5")
    assert parsers.rut_valido("12899407-6")  # sin puntos
    # DV incorrecto / basura
    assert not parsers.rut_valido("10.994.246-9")
    assert not parsers.rut_valido("")
    assert not parsers.rut_valido("123")


def test_elegir_rut_entre_dos_imagenes():
    from fibra_app.core.processor import _elegir_rut
    # 1ª imagen sin RUT -> usa el de la 2ª
    assert _elegir_rut("", "14.105.611-5") == "14.105.611-5"
    # 1ª imagen con RUT inválido -> prefiere el válido de la 2ª
    assert _elegir_rut("10.994.246-9", "14.105.611-5") == "14.105.611-5"
    # ambos válidos -> mantiene el de la orden (1ª)
    assert _elegir_rut("10.994.246-4", "14.105.611-5") == "10.994.246-4"
    # solo la orden -> ese
    assert _elegir_rut("14.105.611-5", "") == "14.105.611-5"


# Texto OCR REAL (con ruido del menú lateral y errores típicos de Tesseract).
TEXTO_ORDEN_RUIDO = """\
7% 15:27 mar,2jun AB y - 200)
4 Mabel Cynthia Moreira Moreira /
Pe dr des, : EI ID Solicitud:
| ¡7% 6) 10.994.246-4 / / [ono 1-6879010Y (0)
E ID de solicitud 1-6B74ROVO Lista Solicitudes Cancelar orden
Pe Informacion de la orden 1D: 79283817 Revisar documentación Solicitud ID: 1-6874ROVO
Fecha de inicio Fecha de término
02-06-26 y ienda ropia Orden
"""

TEXTO_AGENDA_RUIDO = """\
17:55 lun, tjun LOS :
WM Sonia Mollo Iribarren /  Titula Pope) E ID Solicitud:
6, 14.105.611-5 / 1-6B4AM) NU / 1-6B4AMYNU
Especificaciones ? Gladys Marin 4715- A, Depto
... | 1411, Alto Hospicio,
Eu | Tarapaca, Chile
je tm | Agendamiento instalación > Detalle del agendamiento
dd | Actividades > Dirección de Estado Tiempo promedio
is | agendamiento Orden de trabajo creada actividad
== = | Gladys Marin 4715- A, Depto S/N
8 | 1411, Alto Hospicio,
q a | Tarapaca, Chile
== | Miércoles 03-06-2026 14:00 - 20:00
| recibe 12899407-6 +56982867679
"""


def test_orden_ruido_real():
    # 'ID' mal leído como '1D' y nombre con ruido de íconos al inicio.
    datos = parsers.parse_orden(TEXTO_ORDEN_RUIDO)
    assert datos["orden"] == "79283817"
    assert datos["nombre"] == "Mabel Cynthia Moreira Moreira"
    assert datos["rut"] == "10.994.246-4"
    assert datos["fecha_venta"] == "02-06-2026"


def test_agenda_ruido_real():
    datos = parsers.parse_agendamiento(TEXTO_AGENDA_RUIDO)
    # Calle + número + depto, SIN comuna/ciudad/región ni ruido del menú.
    assert datos["direccion"].startswith("Gladys Marin 4715")
    assert "Depto 1411" in datos["direccion"]
    assert "|" not in datos["direccion"]
    assert "Chile" not in datos["direccion"]
    assert "Hospicio" not in datos["direccion"]
    assert datos["contacto"] == "982867679"  # sin +56
    assert datos["nombre"] == "Sonia Mollo Iribarren"
    assert datos["fecha_agenda"] == "03-06-2026"
    assert datos["franja"] == "14:00-20:00"
