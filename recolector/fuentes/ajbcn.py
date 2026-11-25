"""Properes convocatòries del Servei de Premsa de l'Ajuntament de Barcelona.

Es un WordPress. Cada convocatoria es una entrada con el titular en un
enlace y, debajo, una línea en prosa con el día, la hora y el sitio, del
estilo "Dimecres 25 de novembre, a les 18.30 hores a la Casa del Mar de
Barcelona (carrer d'Albareda, 1-13)".

Como es un listado y no una URL por día, se visita una vez por pasada y
se recorren un par de páginas de paginación.
"""

from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup

from ..fechas import leer_fecha, leer_hora
from ..modelo import Acto
from .base import Fuente

BASE = "https://ajuntament.barcelona.cat/premsa/category/properes-convocatories/"
PAGINAS = 2

RE_LUGAR = re.compile(r"\bhore?s\s+(?:a\s+|al\s+|a\s+la\s+|en\s+)?(?P<lugar>.+)$", re.I)


class AjuntamentBCN(Fuente):
    clave = "ajbcn"
    nombre = "Convocatòries de premsa de l'Ajuntament de Barcelona"
    organismo = "Ajuntament de Barcelona"

    def recolectar(self, fechas: list[dt.date]) -> list[Acto]:
        referencia = fechas[0] if fechas else dt.date.today()
        actos: list[Acto] = []
        for pagina in range(1, PAGINAS + 1):
            url = BASE if pagina == 1 else f"{BASE}page/{pagina}/"
            try:
                actos.extend(self.parsear(self.descargar(url), referencia, url))
            except Exception as error:
                print(f"  [aviso] {self.clave} pág {pagina} -> {error}")
                break
        unicos: dict[str, Acto] = {}
        for acto in actos:
            unicos.setdefault(acto.id, acto)
        print(f"  {self.clave} -> {len(unicos)} actos")
        return list(unicos.values())

    def ambito_fechas(self, fechas, actos):
        return {a.fecha for a in actos}

    def parsear(self, html: str, referencia: dt.date, url: str) -> list[Acto]:
        sopa = BeautifulSoup(html, "lxml")
        actos: list[Acto] = []

        for titular in sopa.find_all(["h1", "h2", "h3"]):
            enlace = titular.find("a", href=True)
            if not enlace:
                continue
            href = enlace["href"]
            if "/premsa/" not in href or "/category/" in href:
                continue
            titulo = enlace.get_text(" ", strip=True)
            if len(titulo) < 12:
                continue

            detalle = self._detalle(titular)
            if not detalle:
                continue
            fecha = leer_fecha(detalle, referencia)
            if not fecha:
                continue

            actos.append(
                Acto(
                    fuente=self.clave,
                    organismo=self.organismo,
                    persona="",
                    cargo="",
                    fecha=fecha.isoformat(),
                    hora=leer_hora(detalle),
                    titulo=titulo,
                    lugar=self._lugar(detalle),
                    notas=[detalle] if len(detalle) < 220 else [],
                    url=href,
                )
            )
        return actos

    @staticmethod
    def _detalle(titular) -> str | None:
        """La línea de día, hora y sitio que va justo debajo del titular."""
        for hermano in titular.find_all_next(limit=6):
            if hermano.name in ("h1", "h2", "h3"):
                break
            if hermano.name not in ("p", "div", "span"):
                continue
            texto = hermano.get_text(" ", strip=True)
            if 15 < len(texto) < 400 and leer_fecha(texto) is not None:
                return texto
        return None

    @staticmethod
    def _lugar(detalle: str) -> str | None:
        m = RE_LUGAR.search(detalle)
        if not m:
            return None
        lugar = m.group("lugar").strip(" .,")
        return lugar if 3 < len(lugar) < 160 else None
