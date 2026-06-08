"""Extracción de campos desde el texto OCR de las capturas.

Las capturas provienen del sistema de ventas Entel (vista de Orden y vista de
Detalle de Agendamiento). Estos parsers están optimizados para ese formato.
"""

from __future__ import annotations

import re
from enum import Enum

# ---------------------------------------------------------------------------
# Clasificación de capturas
# ---------------------------------------------------------------------------


class TipoCaptura(Enum):
    ORDEN = "orden"          # Captura 1: información de la orden
    AGENDAMIENTO = "agenda"  # Captura 2: detalle del agendamiento
    DESCONOCIDO = "desconocido"


def clasificar(texto: str) -> TipoCaptura:
    """Determina si el texto corresponde a la captura 1 o la captura 2."""
    t = texto.lower()
    score_orden = sum(
        kw in t for kw in ("informacion de la orden", "información de la orden",
                            "id de solicitud", "ponr", "id carrito", "milestone")
    )
    score_agenda = sum(
        kw in t for kw in ("detalle del agendamiento", "rango horario",
                            "agendamiento instalación", "agendamiento instalacion",
                            "orden de trabajo", "técnico asignado", "tecnico asignado")
    )
    if score_agenda > score_orden:
        return TipoCaptura.AGENDAMIENTO
    if score_orden > 0:
        return TipoCaptura.ORDEN
    return TipoCaptura.DESCONOCIDO


# ---------------------------------------------------------------------------
# Normalizadores
# ---------------------------------------------------------------------------

_RUT_RE = re.compile(r"(\d{1,2}[\.\s]?\d{3}[\.\s]?\d{3}\s*-\s*[\dkK])")
_DATE_RE = re.compile(r"(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{2,4})")
_PHONE_RE = re.compile(r"(\+?\s?56\s?9[\s\d]{8,}|\+?\s?9[\s\d]{8})")
_FRANJA_RE = re.compile(r"(\d{1,2})\s*:\s*(\d{2})\s*[-–]\s*(\d{1,2})\s*:\s*(\d{2})")
# "ID" puede salir mal en OCR: "1D", "lD", "|D", etc.
_ORDEN_RE = re.compile(
    r"orden\s*[I1lL|i]\s*D[:\s.]*([0-9]{5,})", re.IGNORECASE
)


def normalizar_rut(raw: str | None) -> str:
    """Devuelve el RUT en formato XX.XXX.XXX-D."""
    if not raw:
        return ""
    m = _RUT_RE.search(raw)
    if not m:
        return ""
    rut = re.sub(r"[^\dkK]", "", m.group(1))
    if len(rut) < 2:
        return ""
    cuerpo, dv = rut[:-1], rut[-1].upper()
    # Formatear con puntos de miles.
    cuerpo_fmt = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo_fmt}-{dv}"


def rut_digitos(raw: str | None) -> str:
    """Solo los dígitos del RUT, para comparar pares de capturas."""
    if not raw:
        return ""
    m = _RUT_RE.search(raw)
    base = m.group(1) if m else raw
    return re.sub(r"[^\dkK]", "", base).upper()


def _dv_esperado(cuerpo: int) -> str:
    """Calcula el dígito verificador de un RUT chileno (módulo 11)."""
    suma, mult = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def rut_valido(rut: str | None) -> bool:
    """Indica si un RUT (en cualquier formato) tiene dígito verificador correcto."""
    limpio = re.sub(r"[^\dkK]", "", (rut or "")).upper()
    if len(limpio) < 7:  # un RUT real tiene al menos 7 caracteres
        return False
    cuerpo, dv = limpio[:-1], limpio[-1]
    if not cuerpo.isdigit():
        return False
    return _dv_esperado(int(cuerpo)) == dv


def normalizar_fecha(raw: str | None) -> str:
    """Devuelve la fecha como DD-MM-AAAA (asume siglo 20xx en años de 2 cifras)."""
    if not raw:
        return ""
    m = _DATE_RE.search(raw)
    if not m:
        return ""
    d, mes, a = m.groups()
    anio = int(a)
    if anio < 100:
        anio += 2000
    return f"{int(d):02d}-{int(mes):02d}-{anio:04d}"


def normalizar_franja(raw: str | None) -> str:
    """Convierte '14:00 - 20:00' -> '14:00-20:00' y '09:00 - 14:00' -> '9:00-14:00'."""
    if not raw:
        return ""
    m = _FRANJA_RE.search(raw)
    if not m:
        return ""
    h1, m1, h2, m2 = m.groups()
    return f"{int(h1)}:{m1}-{int(h2)}:{m2}"


def normalizar_telefono(raw: str | None) -> str:
    """Devuelve el teléfono SIN prefijo país: 9 dígitos, p.ej. '945794728'."""
    if not raw:
        return ""
    m = _PHONE_RE.search(raw)
    if not m:
        return ""
    digitos = re.sub(r"\D", "", m.group(1))
    # Quitar prefijo de país (+56 / 56) y ceros iniciales.
    if digitos.startswith("56"):
        digitos = digitos[2:]
    digitos = digitos.lstrip("0")
    # Si quedó sin el 9 inicial del celular, agregarlo.
    if len(digitos) == 8:
        digitos = "9" + digitos
    return digitos


# ---------------------------------------------------------------------------
# Extractores por campo
# ---------------------------------------------------------------------------


def _lineas(texto: str) -> list[str]:
    return [ln.strip() for ln in texto.splitlines() if ln.strip()]


def extraer_orden(texto: str) -> str:
    m = _ORDEN_RE.search(texto)
    if m:
        return m.group(1)
    # Plan B: una línea con "ID:" seguida de número largo, sin "solicitud".
    for ln in _lineas(texto):
        low = ln.lower()
        if "id" in low and "solicitud" not in low:
            num = re.search(r"\b(\d{6,})\b", ln)
            if num:
                return num.group(1)
    return ""


def extraer_nombre(texto: str) -> str:
    """El nombre del titular está en el encabezado, antes del primer '/'.

    Hay varias líneas con '/' en el encabezado (barra de estado, RUT, etc.).
    Se puntúa cada candidata: bonus si la línea menciona 'Titular', penalización
    si parece barra de estado (contiene una hora HH:MM). El OCR antepone ruido
    de los íconos del menú ('WM', 'Mn', '4'), que se descarta.
    """
    lineas = _lineas(texto)
    mejor, mejor_score = "", -10
    for ln in lineas[:6]:
        if "/" not in ln:
            continue
        cand = _limpiar_nombre(ln.split("/")[0])
        if not cand:
            continue
        score = len(cand.split())
        if re.search(r"titula", ln, re.IGNORECASE):
            score += 3
        if re.search(r"\d{1,2}:\d{2}", ln):  # barra de estado (hora)
            score -= 5
        if score > mejor_score:
            mejor, mejor_score = cand, score
    if mejor:
        return mejor
    # Plan B: línea anterior al RUT.
    for i, ln in enumerate(lineas):
        if _RUT_RE.search(ln) and i > 0:
            nombre = _limpiar_nombre(lineas[i - 1])
            if nombre:
                return nombre
    return ""


def _limpiar_nombre(crudo: str) -> str:
    """Extrae las palabras del nombre, quitando ruido de OCR al inicio/fin."""
    # Conservar solo letras y espacios.
    solo_letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ\s]", " ", crudo)
    tokens = solo_letras.split()
    # Descartar tokens iniciales de 1-2 letras (ruido de íconos: 'WM', 'Mn').
    while tokens and len(tokens[0]) <= 2:
        tokens.pop(0)
    # Descartar palabras de relleno típicas que el OCR mezcla.
    basura = {"titular", "titula", "id", "solicitud", "pope", "ponc", "ls"}
    tokens = [t for t in tokens if t.lower() not in basura]
    # Un nombre válido tiene al menos 2 palabras de 3+ letras.
    validos = [t for t in tokens if len(t) >= 3]
    if len(validos) >= 2:
        return _titlecase(" ".join(validos))
    return ""


def _titlecase(texto: str) -> str:
    return " ".join(p.capitalize() for p in texto.split())


_STOP_DIR = ("fecha", "rango", "nombre", "técnico", "tecnico", "servicio",
             "actividades", "especificaciones", "delivery")


def extraer_direccion_agenda(texto: str) -> str:
    """Dirección del bloque 'Detalle del agendamiento'.

    El OCR suele partir la etiqueta 'Dirección de agendamiento' en dos líneas
    e intercalar otros campos ('Estado', 'Orden de trabajo creada'). La
    dirección real aparece como una o más líneas con número y comas, terminando
    en '..., Chile'. No debe confundirse con la 'Dirección' de Especificaciones,
    por eso se ancla en el bloque de agendamiento.
    """
    lineas = _lineas(texto)
    anchor = _anchor_agenda(lineas)
    if anchor is None:
        return ""

    partes: list[str] = []
    iniciado = False
    for ln in lineas[anchor + 1: anchor + 14]:
        low = ln.lower()
        if any(low.startswith(s) or f" {s} " in f" {low} " for s in _STOP_DIR):
            if iniciado:
                break
            # Etiquetas de la siguiente sección: detener la búsqueda.
            if low.startswith(("fecha", "rango", "nombre", "técnico", "tecnico")):
                break
            continue
        es_direccion = ("chile" in low) or (bool(re.search(r"\d", ln)) and "," in ln)
        if es_direccion:
            limpia = _limpiar_dir(ln)
            if limpia:
                partes.append(limpia)
                iniciado = True
            if "chile" in low:
                break
        elif iniciado:
            break

    direccion = " ".join(partes).strip(" ,")
    direccion = re.sub(r"\s+", " ", direccion).strip(" ,")
    return _solo_calle_numero(direccion)


# Identificadores de la vivienda que SÍ forman parte de la dirección.
_APT_RE = re.compile(
    r"\b(depto|dpto|depart\w*|casa|block|blk|torre|piso|oficina)\b", re.IGNORECASE
)
# Comuna / ciudad / región / país a eliminar si quedan pegados al final.
_TAIL_LUGAR = re.compile(
    r"[,\s]+(chile|tarapac[aá]|atacama|antofagasta|coquimbo|"
    r"arica y parinacota|regi[oó]n[\w\s.]*|provincia[\w\s.]*|"
    r"alto hospicio|iquique|copiap[oó]|vallenar|arica)\s*$",
    re.IGNORECASE,
)


def _solo_calle_numero(direccion: str) -> str:
    """Conserva calle/pasaje/avenida + numeración (y depto/casa), sin comuna/ciudad.

    Ej: 'El Carmelo 3442, Iquique, Tarapacá, Chile' -> 'El Carmelo 3442'
        'Gladys Marin 4715-A, Depto 1411, Alto Hospicio, Chile'
            -> 'Gladys Marin 4715-A, Depto 1411'
    """
    if not direccion:
        return ""
    segmentos = [s.strip() for s in direccion.split(",") if s.strip()]
    if not segmentos:
        return ""
    # El primer segmento es la calle + número (siempre se conserva).
    resultado = [segmentos[0]]
    # Conservar los siguientes solo si son identificador de vivienda (depto/casa…).
    for seg in segmentos[1:]:
        if _APT_RE.search(seg):
            resultado.append(seg)
        else:
            break  # a partir de aquí viene comuna/ciudad/región
    salida = ", ".join(resultado)
    # Limpieza por si la comuna/ciudad quedó pegada sin coma (OCR).
    anterior = None
    while anterior != salida:
        anterior = salida
        salida = _TAIL_LUGAR.sub("", salida).strip(" ,")
    return salida


def _anchor_agenda(lineas: list[str]) -> int | None:
    """Índice de la línea 'Detalle del agendamiento' (o equivalente)."""
    for i, ln in enumerate(lineas):
        low = ln.lower()
        if "detalle" in low and "agendamiento" in low:
            return i
    # Respaldo: línea con 'dirección de' (etiqueta partida).
    for i, ln in enumerate(lineas):
        if "direcc" in ln.lower() and "agend" in " ".join(lineas[i:i + 2]).lower():
            return i
    return None


def _limpiar_dir(ln: str) -> str:
    """Quita ruido del menú lateral y de la columna 'Estado' en una dirección."""
    # El menú lateral queda a la izquierda de un '|'; conservar lo de la derecha.
    if "|" in ln:
        ln = ln.rsplit("|", 1)[1]
    s = re.split(
        r"\b(?:Estado|Orden de trabajo|Tiempo promedio|S\s*/\s*N)\b",
        ln, flags=re.IGNORECASE,
    )[0]
    return s.strip(" ,|")


def extraer_fecha_agenda(texto: str) -> str:
    """Fecha bajo la etiqueta 'Fecha' del agendamiento (puede traer día de semana)."""
    lineas = _lineas(texto)
    for i, ln in enumerate(lineas):
        if re.match(r"^fecha\b", ln.lower()):
            fecha = normalizar_fecha(ln)
            if fecha:
                return fecha
            for sig in lineas[i + 1:i + 3]:
                fecha = normalizar_fecha(sig)
                if fecha:
                    return fecha
    return normalizar_fecha(texto)


def extraer_fecha_venta(texto: str) -> str:
    """Fecha que sigue a 'Fecha de inicio' en la captura de la orden."""
    lineas = _lineas(texto)
    for i, ln in enumerate(lineas):
        if "fecha de inicio" in ln.lower():
            fecha = normalizar_fecha(ln)
            if fecha:
                return fecha
            for sig in lineas[i + 1:i + 3]:
                fecha = normalizar_fecha(sig)
                if fecha:
                    return fecha
    return ""


# ---------------------------------------------------------------------------
# Parsers de alto nivel
# ---------------------------------------------------------------------------


def parse_orden(texto: str) -> dict[str, str]:
    """Extrae campos de la captura 1 (información de la orden)."""
    return {
        "orden": extraer_orden(texto),
        "nombre": extraer_nombre(texto),
        "rut": normalizar_rut(texto),
        "fecha_venta": extraer_fecha_venta(texto),
    }


def parse_agendamiento(texto: str) -> dict[str, str]:
    """Extrae campos de la captura 2 (detalle del agendamiento)."""
    return {
        "direccion": extraer_direccion_agenda(texto),
        "fecha_agenda": extraer_fecha_agenda(texto),
        "contacto": normalizar_telefono(texto),
        "franja": normalizar_franja(texto),
        # El RUT también aparece aquí; sirve para emparejar capturas.
        "rut": normalizar_rut(texto),
        "nombre": extraer_nombre(texto),
    }
