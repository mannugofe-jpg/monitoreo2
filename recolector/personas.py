"""Saca el nombre y el cargo de una frase de agenda.

Las agendas institucionales escriben siempre igual, cargo primero y
nombre después, separados por coma. "La consellera de Territori,
Habitatge i Transició Ecològica, Sílvia Paneque i Sureda, inaugurarà..."

El problema es que el cargo puede llevar comas dentro, así que no sirve
quedarse con la primera. La solución es buscar el último tramo que
parezca un nombre propio antes de que arranque el verbo.
"""

from __future__ import annotations

import re

CARGOS = (
    r"president|presidenta|presidente|vicepresident|vicepresidenta|"
    r"vicepresidente|conseller|consellera|consejero|consejera|"
    r"ministre|ministra|ministro|secretari|secretaria|secretario|"
    r"delegat|delegada|delegado|director|directora|portaveu|portavoz|"
    r"vicesecretari|vicesecretaria|vicesecretario|alcalde|alcaldessa|"
    r"alcaldesa|coordinador|coordinadora|diputat|diputada|diputado"
)

# Una palabra de nombre propio, o un conector en minúscula que puede ir
# dentro de un apellido compuesto
_PALABRA = r"(?:[A-ZÀ-ÖØ-Þ][\wÀ-ÿ'’·-]+|i|de|del|la|dels|las|los|y)"

_RE_CARGO = re.compile(r"\b(?P<articulo>El|La|Els|Les|Los|Las)\s+(?:" + CARGOS + r")",
                       re.UNICODE | re.IGNORECASE)

# Un tramo entre comas que podría ser el nombre de la persona
_RE_CANDIDATO = re.compile(
    r",\s*(?P<persona>" + _PALABRA + r"(?:\s+" + _PALABRA + r"){1,4})\s*(?=[,;])",
    re.UNICODE,
)


def _limpiar(texto: str) -> str:
    return " ".join((texto or "").split()).strip(" ,;.")


def extraer(texto: str) -> tuple[str, str]:
    """Devuelve persona y cargo. Cadenas vacías si no se reconoce nada.

    El truco está en distinguir el nombre de las partes del cargo que
    también van entre comas, como "Territori, Habitatge i Transició
    Ecològica". La pista es lo que viene después. Tras el nombre
    arranca el verbo, en minúscula. Tras un trozo de cargo viene otro
    tramo que empieza en mayúscula.
    """
    if not texto:
        return "", ""

    inicio = _RE_CARGO.search(texto)
    if not inicio:
        return "", ""

    for m in _RE_CANDIDATO.finditer(texto, inicio.end()):
        resto = texto[m.end():].lstrip(" ,;").lstrip()
        if resto and resto[0].isupper():
            continue  # seguimos dentro del cargo
        persona = _limpiar(m.group("persona"))
        if len(persona.split()) < 2 or persona.split()[0].islower():
            continue
        cargo = _limpiar(texto[inicio.start():m.start()])
        return persona, cargo

    return "", ""
