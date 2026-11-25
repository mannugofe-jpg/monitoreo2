"""Lee config.yaml y decide qué actos son relevantes.

Un acto se marca relevante si menciona a alguna de las personas vigiladas
para esa fuente o si casa con alguna palabra de alguno de sus temas. Una
fuente sin personas ni temas declarados da por relevante todo lo suyo.

Nada se descarta. Lo no relevante se guarda igual, marcado, para poder
revisarlo si algún filtro se queda corto.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config.yaml"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return " " + texto + " "


@dataclass
class ConfigFuente:
    clave: str
    nombre: str
    organismo: str
    url: str
    activa: bool
    personas: list[str]
    temas: list[str]


class Clasificador:
    def __init__(self, ruta: Path | str = CONFIG) -> None:
        datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
        self.temas: dict[str, list[str]] = {
            nombre: [normalizar(p).strip() for p in palabras]
            for nombre, palabras in (datos.get("temas") or {}).items()
        }
        self.fuentes: dict[str, ConfigFuente] = {}
        for f in datos.get("fuentes") or []:
            self.fuentes[f["clave"]] = ConfigFuente(
                clave=f["clave"],
                nombre=f.get("nombre", f["clave"]),
                organismo=f.get("organismo", ""),
                url=f.get("url", ""),
                activa=bool(f.get("activa", False)),
                personas=f.get("personas") or [],
                temas=f.get("temas") or [],
            )

    def claves_activas(self) -> list[str]:
        return [c for c, f in self.fuentes.items() if f.activa]

    def clasificar(self, acto) -> None:
        """Rellena acto.temas, acto.personas_vigiladas y acto.relevante."""
        cfg = self.fuentes.get(acto.fuente)
        texto = normalizar(
            " ".join(
                filter(None, [acto.titulo, acto.persona, acto.cargo, acto.lugar])
            )
        )

        encontrados: list[str] = []
        nombres: list[str] = []

        if cfg:
            for tema in cfg.temas:
                for palabra in self.temas.get(tema, []):
                    if palabra and palabra in texto:
                        encontrados.append(tema)
                        break
            for persona in cfg.personas:
                if self._coincide_persona(persona, texto):
                    nombres.append(persona)

        acto.temas = sorted(set(encontrados))
        acto.personas_vigiladas = nombres
        if cfg and not cfg.temas and not cfg.personas:
            acto.relevante = True
        else:
            acto.relevante = bool(encontrados or nombres)

    @staticmethod
    def _coincide_persona(persona: str, texto_normalizado: str) -> bool:
        partes = [p for p in normalizar(persona).split() if len(p) > 2]
        if not partes:
            return False
        # Basta con el apellido principal para no fallar por "Núñez Feijóo"
        # frente a "Feijóo" a secas
        return all(f" {p} " in texto_normalizado for p in partes) or (
            f" {partes[-1]} " in texto_normalizado and len(partes[-1]) > 4
        )
