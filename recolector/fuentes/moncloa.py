"""Agenda del Gobierno de España, publicada en lamoncloa.gob.es.

La página tiene una URL por día con el patrón ?d=YYYYMMDD y agrupa los
actos por miembro del Ejecutivo. Dentro de cada persona hay una lista de
entradas que empiezan por la hora, en formato "09:00 h.", seguida de la
descripción y, a veces, de notas como "Cobertura oficial".

El parser no depende de clases CSS, que son lo primero que cambia cuando
rediseñan el sitio. Se apoya en dos cosas estables, los encabezados h2
con el nombre de la persona y el patrón de hora.
"""

from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup

from ..modelo import Acto
from .base import Fuente

URL_BASE = "https://www.lamoncloa.gob.es/gobierno/agenda/Paginas/agenda.aspx?d={}"

RE_HORA = re.compile(r"^(\d{1,2}):(\d{2})\s*h\.?$")

# Líneas que no son el acto en sí, sino indicaciones para los medios
RE_NOTA = re.compile(
    r"^(cobertura|previamente|al t[eé]rmino|posteriormente|a continuaci[oó]n|"
    r"tras |antes |sin cobertura|acto cerrado|\d{1,2}:\d{2}\s*hora local)",
    re.I,
)


class Moncloa(Fuente):
    clave = "moncloa"
    nombre = "Agenda del Gobierno de España"
    organismo = "Gobierno de España"

    def url_dia(self, fecha: dt.date) -> str:
        return URL_BASE.format(fecha.strftime("%Y%m%d"))

    def recolectar_dia(self, fecha: dt.date) -> list[Acto]:
        url = self.url_dia(fecha)
        return self.parsear(self.descargar(url), fecha, url)

    def parsear(self, html: str, fecha: dt.date, url: str) -> list[Acto]:
        sopa = BeautifulSoup(html, "lxml")
        actos: list[Acto] = []
        vistos: set[str] = set()

        for h2 in sopa.find_all("h2"):
            persona = h2.get_text(" ", strip=True)
            if not persona or len(persona) > 80:
                continue

            bloque = h2.find_parent("li") or h2.parent
            if bloque is None:
                continue

            entradas = [li for li in bloque.find_all("li") if li is not bloque]
            if not entradas:
                continue

            cargo = self._cargo(h2)

            for li in entradas:
                acto = self._entrada_a_acto(li, persona, cargo, fecha, url)
                if acto is None or acto.id in vistos:
                    continue
                vistos.add(acto.id)
                actos.append(acto)

        return actos

    def _cargo(self, h2) -> str:
        """El cargo es el primer texto con contenido que sigue al nombre."""
        for hermano in h2.next_siblings:
            texto = getattr(hermano, "get_text", lambda *_, **__: str(hermano))(
                " ", strip=True
            ) if hasattr(hermano, "get_text") else str(hermano).strip()
            if not texto:
                continue
            if getattr(hermano, "name", None) in ("ul", "ol"):
                break
            if len(texto) < 160:
                return texto
            break
        return ""

    def _entrada_a_acto(
        self, li, persona: str, cargo: str, fecha: dt.date, url: str
    ) -> Acto | None:
        lineas = [
            linea.strip()
            for linea in li.get_text("\n", strip=True).split("\n")
            if linea.strip()
        ]
        if not lineas:
            return None

        hora = None
        m = RE_HORA.match(lineas[0])
        if m:
            hora = f"{int(m.group(1)):02d}:{m.group(2)}"
            lineas = lineas[1:]
        if not lineas:
            return None

        titulo = lineas[0]
        notas = [l for l in lineas[1:] if RE_NOTA.match(l) or len(l) < 200]

        # Descarta ruido de navegación que se haya colado
        if len(titulo) < 8:
            return None

        return Acto(
            fuente=self.clave,
            organismo=self.organismo,
            persona=persona,
            cargo=cargo,
            fecha=fecha.isoformat(),
            hora=hora,
            titulo=titulo,
            notas=notas,
            url=url,
        )
