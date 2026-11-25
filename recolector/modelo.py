"""Modelo de datos común a todas las fuentes.

Cada fuente devuelve objetos Acto ya normalizados. El identificador se
calcula a partir de fuente, fecha, persona y título, pero NO de la hora,
para que un cambio de hora se detecte como modificación y no como un
acto distinto.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field, asdict


def _normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y sin puntuación, para comparar títulos."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9 ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


# Captura el último "en <sitio>" de la descripción, que es donde La Moncloa
# y la mayoría de agendas institucionales colocan el lugar.
_RE_LUGAR = re.compile(
    r",\s+en\s+(?P<lugar>[^,.;]+(?:\s*\([^)]+\))?(?:,\s+en\s+[^,.;]+)?)\s*\.?\s*$"
)


def extraer_lugar(descripcion: str) -> str | None:
    """Intento razonable de aislar el lugar dentro del texto libre."""
    m = _RE_LUGAR.search(descripcion.strip())
    if not m:
        return None
    lugar = m.group("lugar").strip()
    lugar = re.sub(r"^en\s+", "", lugar, flags=re.I)
    lugar = lugar.replace(", en ", ", ")
    if len(lugar) > 120:
        return None
    return lugar


@dataclass
class Acto:
    fuente: str
    organismo: str
    persona: str
    cargo: str
    fecha: str                      # YYYY-MM-DD
    titulo: str
    url: str
    hora: str | None = None         # HH:MM, None si el acto no tiene hora
    lugar: str | None = None
    notas: list[str] = field(default_factory=list)

    # Campos que rellena el clasificador a partir de config.yaml
    temas: list[str] = field(default_factory=list)
    personas_vigiladas: list[str] = field(default_factory=list)
    relevante: bool = True

    # Campos que gestiona el almacén, no las fuentes
    id: str = ""
    estado: str = "nuevo"           # nuevo | vigente | modificado | cancelado
    visto_primera_vez: str = ""
    visto_ultima_vez: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.calcular_id()
        if self.lugar is None:
            self.lugar = extraer_lugar(self.titulo)

    def calcular_id(self) -> str:
        semilla = "|".join(
            [
                self.fuente,
                self.fecha,
                _normalizar(self.persona),
                _normalizar(self.titulo),
            ]
        )
        return hashlib.sha1(semilla.encode("utf-8")).hexdigest()[:12]

    def huella(self) -> str:
        """Lo que se compara entre pasadas para detectar modificaciones."""
        return "|".join([self.hora or "", self.lugar or "", " / ".join(self.notas)])

    def a_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def desde_dict(d: dict) -> "Acto":
        return Acto(**d)


def clave_orden(acto: Acto) -> tuple:
    """Orden natural. Primero por fecha, luego por hora y luego por lugar."""
    return (acto.fecha, acto.hora or "99:99", acto.lugar or "", acto.persona)
