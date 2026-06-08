"""Orquestación: OCR de la carpeta, emparejamiento y armado de solicitudes."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..ocr import engine, parsers
from ..ocr.parsers import TipoCaptura
from .models import Solicitud

logger = logging.getLogger(__name__)

ProgresoCallback = Callable[[int, int, str], None]


@dataclass
class _CapturaOCR:
    """Resultado intermedio del OCR de una sola imagen."""

    path: Path
    texto: str
    tipo: TipoCaptura
    rut: str = ""


@dataclass
class ResultadoProceso:
    solicitudes: list[Solicitud] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def procesar_carpeta(
    imagenes: list[Path],
    progreso: ProgresoCallback | None = None,
) -> ResultadoProceso:
    """Procesa una lista de imágenes y devuelve solicitudes emparejadas.

    Estrategia de emparejamiento:
    1. Se hace OCR de cada imagen y se clasifica (orden / agendamiento).
    2. Se emparejan capturas de tipos distintos que comparten el mismo RUT.
    3. Las que no calzan por RUT se emparejan por orden de aparición.
    """
    resultado = ResultadoProceso()
    if not imagenes:
        resultado.errores.append("No se encontraron imágenes en la carpeta.")
        return resultado

    capturas: list[_CapturaOCR] = []
    total = len(imagenes)
    for i, path in enumerate(imagenes, start=1):
        if progreso:
            progreso(i, total, f"Leyendo {path.name}")
        try:
            texto = engine.image_to_text(path)
        except engine.OCRError as exc:
            resultado.errores.append(str(exc))
            logger.error("OCR falló: %s", exc)
            continue
        tipo = parsers.clasificar(texto)
        rut = parsers.rut_digitos(texto)
        capturas.append(_CapturaOCR(path=path, texto=texto, tipo=tipo, rut=rut))

    pares = _emparejar(capturas, resultado)
    for cap_orden, cap_agenda in pares:
        resultado.solicitudes.append(_armar_solicitud(cap_orden, cap_agenda))

    return resultado


def _emparejar(
    capturas: list[_CapturaOCR], resultado: ResultadoProceso
) -> list[tuple[_CapturaOCR | None, _CapturaOCR | None]]:
    """Empareja capturas de orden con capturas de agendamiento."""
    ordenes = [c for c in capturas if c.tipo == TipoCaptura.ORDEN]
    agendas = [c for c in capturas if c.tipo == TipoCaptura.AGENDAMIENTO]
    desconocidas = [c for c in capturas if c.tipo == TipoCaptura.DESCONOCIDO]

    if desconocidas:
        # No se pudo clasificar: emparejamiento secuencial puro como respaldo.
        logger.warning("%d captura(s) sin clasificar; uso pares secuenciales.",
                       len(desconocidas))
        return _emparejar_secuencial(capturas, resultado)

    pares: list[tuple[_CapturaOCR | None, _CapturaOCR | None]] = []
    agendas_restantes = list(agendas)

    # Pase 1: emparejar por coincidencia exacta de RUT (lo más confiable).
    ordenes_sin_par: list[_CapturaOCR] = []
    for orden in ordenes:
        match = None
        if orden.rut:
            match = next((a for a in agendas_restantes if a.rut == orden.rut), None)
        if match is not None:
            agendas_restantes.remove(match)
            pares.append((orden, match))
        else:
            ordenes_sin_par.append(orden)

    # Pase 2: asignar las agendas restantes a las órdenes sin par (por orden).
    for orden in ordenes_sin_par:
        if agendas_restantes:
            pares.append((orden, agendas_restantes.pop(0)))
        else:
            pares.append((orden, None))
            resultado.errores.append(
                f"La captura de orden '{orden.path.name}' no tiene "
                "captura de agendamiento asociada."
            )

    for sobrante in agendas_restantes:
        pares.append((None, sobrante))
        resultado.errores.append(
            f"La captura de agendamiento '{sobrante.path.name}' no tiene "
            "captura de orden asociada."
        )

    return pares


def _emparejar_secuencial(
    capturas: list[_CapturaOCR], resultado: ResultadoProceso
) -> list[tuple[_CapturaOCR | None, _CapturaOCR | None]]:
    """Empareja capturas de dos en dos por orden de nombre de archivo."""
    pares: list[tuple[_CapturaOCR | None, _CapturaOCR | None]] = []
    for i in range(0, len(capturas), 2):
        a = capturas[i]
        b = capturas[i + 1] if i + 1 < len(capturas) else None
        # Determinar cuál es orden y cuál agendamiento.
        if b is not None and b.tipo == TipoCaptura.ORDEN and a.tipo != TipoCaptura.ORDEN:
            a, b = b, a
        pares.append((a, b))
        if b is None:
            resultado.errores.append(
                f"La imagen '{a.path.name}' quedó sin pareja (número impar)."
            )
    return pares


def _armar_solicitud(
    cap_orden: _CapturaOCR | None, cap_agenda: _CapturaOCR | None
) -> Solicitud:
    """Combina los campos extraídos de ambas capturas en una Solicitud."""
    sol = Solicitud()
    rut_orden = rut_agenda = ""
    if cap_orden:
        datos = parsers.parse_orden(cap_orden.texto)
        sol.orden = datos["orden"]
        sol.nombre = datos["nombre"]
        rut_orden = datos["rut"]
        sol.fecha_venta = datos["fecha_venta"]
        sol.imagenes.append(cap_orden.path)
    if cap_agenda:
        datos = parsers.parse_agendamiento(cap_agenda.texto)
        sol.direccion = datos["direccion"]
        sol.fecha_agenda = datos["fecha_agenda"]
        sol.contacto = datos["contacto"]
        sol.franja = datos["franja"]
        rut_agenda = datos["rut"]
        sol.imagenes.append(cap_agenda.path)
        if not sol.nombre:
            sol.nombre = datos["nombre"]

    # El RUT del cliente aparece en AMBAS capturas: se combinan y se prefiere
    # el que tenga dígito verificador válido (si la 1ª imagen falla, usa la 2ª).
    sol.rut = _elegir_rut(rut_orden, rut_agenda)

    sol.advertencias = [
        f"Campo '{c}' no detectado" for c in sol.campos_faltantes()
    ]
    return sol


def _elegir_rut(rut_orden: str, rut_agenda: str) -> str:
    """Elige el mejor RUT entre las dos capturas.

    Prioridad: un RUT con dígito verificador válido (primero el de la orden,
    luego el de agendamiento). Si ninguno valida, devuelve el primero detectado.
    """
    candidatos = [r for r in (rut_orden, rut_agenda) if r]
    for r in candidatos:
        if parsers.rut_valido(r):
            if r == rut_agenda and rut_orden != rut_agenda:
                logger.info("RUT tomado de la 2ª imagen (agendamiento): %s", r)
            return r
    if candidatos:
        logger.warning("Ningún RUT validó el dígito verificador; uso %s",
                       candidatos[0])
        return candidatos[0]
    return ""
