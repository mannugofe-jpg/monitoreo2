"""Agenda del Govern de Catalunya, en govern.cat.

La web está hecha con Angular pero se sirve ya montada desde el
servidor, así que se lee sin navegador. Rechaza las peticiones que se
identifican como robot, cosa que resuelve la cabecera común.

Cada acto es un elemento gov-core-agenda-item con la hora, el título,
la sede, el municipio y un texto descriptivo del que se saca quién
protagoniza el acto. Dos encabezados separan los actos del president de
los de los consellers.

Publica solo el día en curso, así que se visita una vez por pasada.
"""

from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup

from ..fechas import leer_fecha
from ..modelo import Acto
from ..personas import extraer
from .base import Fuente

URL = "https://govern.cat/gov/agenda"

RE_HORA = re.compile(r"^(\d{1,2}):(\d{2})$")


class Generalitat(Fuente):
    clave = "generalitat"
    nombre = "Agenda del Govern de Catalunya"
    organismo = "Generalitat de Catalunya"

    def recolectar(self, fechas: list[dt.date]) -> list[Acto]:
        try:
            actos = self.parsear(
                self.descargar(URL), fechas[0] if fechas else dt.date.today()
            )
        except Exception as error:
            print(f"  [aviso] {self.clave} -> {error}")
            return []
        print(f"  {self.clave} -> {len(actos)} actos")
        return actos

    def ambito_fechas(self, fechas, actos):
        return {a.fecha for a in actos}

    def parsear(self, html: str, referencia: dt.date) -> list[Acto]:
        sopa = BeautifulSoup(html, "lxml")
        fecha = self._fecha(sopa, referencia)
        actos: list[Acto] = []

        for item in sopa.find_all("gov-core-agenda-item"):
            acto = self._item_a_acto(item, fecha)
            if acto is not None:
                actos.append(acto)

        unicos: dict[str, Acto] = {}
        for acto in actos:
            unicos.setdefault(acto.id, acto)
        return list(unicos.values())

    def _fecha(self, sopa, referencia: dt.date) -> dt.date:
        """La fecha va en un texto suelto justo después del título."""
        h1 = sopa.find("h1")
        if h1:
            for cadena in h1.find_all_next(string=True, limit=40):
                leida = leer_fecha(" ".join(cadena.split()), referencia)
                if leida:
                    return leida
        return referencia

    def _seccion(self, item) -> str:
        previo = item.find_previous(["h2", "h3"])
        return " ".join(previo.get_text(" ", strip=True).split()) if previo else ""

    def _item_a_acto(self, item, fecha: dt.date) -> Acto | None:
        titulo_nodo = item.select_one(".cl-agenda-item__title")
        if titulo_nodo is None:
            return None
        titulo = " ".join(titulo_nodo.get_text(" ", strip=True).split())
        if len(titulo) < 8:
            return None

        hora = None
        hora_nodo = item.select_one(".cl-agenda-item__date")
        if hora_nodo:
            m = RE_HORA.match(hora_nodo.get_text(strip=True))
            if m:
                hora = f"{int(m.group(1)):02d}:{m.group(2)}"

        # Sede y municipio van en dos cursivas seguidas, tras el título
        cursivas = [
            " ".join(i.get_text(" ", strip=True).split())
            for i in titulo_nodo.parent.find_all("i")
        ]
        cursivas = [c for c in cursivas if c]
        lugar = ", ".join(cursivas[:2]) if cursivas else None

        descripcion = ""
        for parrafo in item.find_all("p"):
            texto = " ".join(parrafo.get_text(" ", strip=True).split())
            if texto and texto != titulo and len(texto) > 40:
                descripcion = texto
                break

        persona, cargo = extraer(descripcion or titulo)
        if not persona and "president" in self._seccion(item).lower():
            cargo = cargo or "President de la Generalitat"

        return Acto(
            fuente=self.clave,
            organismo=self.organismo,
            persona=persona,
            cargo=cargo,
            fecha=fecha.isoformat(),
            hora=hora,
            titulo=titulo,
            lugar=lugar,
            notas=[descripcion[:300]] if descripcion else [],
            url=URL,
        )
