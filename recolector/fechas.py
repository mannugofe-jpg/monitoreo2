"""Lectura de fechas escritas en prosa, en catalán y en castellano.

Las agendas no publican fechas ISO, publican cosas como "dijous 04 de
juny del 2026" o "Dimecres 25 de novembre, a les 18.30 hores". Aquí se
traducen a date y a hora.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata

MESES = {
    # catalán
    "gener": 1, "febrer": 2, "marc": 3, "abril": 4, "maig": 5, "juny": 6,
    "juliol": 7, "agost": 8, "setembre": 9, "octubre": 10,
    "novembre": 11, "desembre": 12,
    # castellano
    "enero": 1, "febrero": 2, "marzo": 3, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}

_RE_FECHA = re.compile(
    r"\b(?P<dia>\d{1,2})\s+(?:de\s+|d\s*)?(?P<mes>[a-z]+)\b"
    r"(?:\s+(?:de\s+|del\s+)?(?P<anio>\d{4}))?"
)

_RE_HORA = re.compile(
    r"\b(?:a\s+les\s+|a\s+las\s+)?(?P<h>\d{1,2})[:.h](?P<m>\d{2})\s*"
    r"(?:h|hores|horas)?\b"
)


def _sin_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def leer_fecha(texto: str, referencia: dt.date | None = None) -> dt.date | None:
    """Saca una fecha de un texto en prosa.

    Si no hay año, se deduce del de referencia, asumiendo que una fecha
    que cae más de seis meses atrás pertenece en realidad al año
    siguiente. Es lo correcto para agendas, que miran hacia delante.
    """
    referencia = referencia or dt.date.today()
    m = _RE_FECHA.search(_sin_acentos(texto))
    if not m:
        return None
    mes = MESES.get(m.group("mes"))
    if not mes:
        return None
    dia = int(m.group("dia"))
    anio = int(m.group("anio")) if m.group("anio") else referencia.year
    try:
        fecha = dt.date(anio, mes, dia)
    except ValueError:
        return None
    if not m.group("anio") and (referencia - fecha).days > 180:
        try:
            fecha = dt.date(anio + 1, mes, dia)
        except ValueError:
            return None
    return fecha


def leer_hora(texto: str) -> str | None:
    """Devuelve HH:MM a partir de '18.30 hores', '13:00 h' o 'a les 9.00'."""
    for m in _RE_HORA.finditer(_sin_acentos(texto)):
        h, mi = int(m.group("h")), int(m.group("m"))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return f"{h:02d}:{mi:02d}"
    return None
