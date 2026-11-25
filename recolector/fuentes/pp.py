"""Agenda del Partido Popular, en pp.es.

Es un WordPress que sirve la agenda ya montada en el HTML. Rechaza las
peticiones que se identifican como robot, cosa que resuelve la cabecera
común.

Cada acto es un div con clase schedule-item, con la hora, el municipio
y una frase que suele empezar por el cargo y el nombre de quien
protagoniza el acto.

Publica solo el día en curso, así que se visita una vez por pasada.
"""

from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup

from ..fechas import leer_fecha, leer_hora
from ..modelo import Acto
from ..personas import extraer
from .base import Fuente

URL = "https://www.pp.es/actualidad/agenda/"

HOY = {"hoy", "avui", "today"}


class PP(Fuente):
    clave = "pp"
    nombre = "Agenda del Partido Popular"
    organismo = "Partido Popular"

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
        actos: list[Acto] = []

        for item in sopa.select(".schedule-item"):
            acto = self._item_a_acto(item, referencia)
            if acto is not None:
                actos.append(acto)

        unicos: dict[str, Acto] = {}
        for acto in actos:
            unicos.setdefault(acto.id, acto)
        return list(unicos.values())

    def _texto(self, item, selector: str) -> str:
        nodo = item.select_one(selector)
        return " ".join(nodo.get_text(" ", strip=True).split()) if nodo else ""

    def _item_a_acto(self, item, referencia: dt.date) -> Acto | None:
        cuando = self._texto(item, ".schedule-when")
        titulo = self._titulo(item)
        if not titulo or len(titulo) < 12:
            return None

        # "Hoy" es lo habitual, pero si algún día ponen una fecha se lee
        fecha = referencia
        if cuando and cuando.lower() not in HOY:
            leida = leer_fecha(cuando, referencia)
            if leida:
                fecha = leida

        hora = leer_hora(self._texto(item, ".schedule-time"))
        lugar = self._texto(item, ".schedule-where") or None
        persona, cargo = extraer(titulo)

        return Acto(
            fuente=self.clave,
            organismo=self.organismo,
            persona=persona,
            cargo=cargo,
            fecha=fecha.isoformat(),
            hora=hora,
            titulo=titulo,
            lugar=lugar,
            url=URL,
        )

    @staticmethod
    def _titulo(item) -> str:
        """El titular es el div sin clase que hay dentro de title-schedule."""
        bloque = item.select_one(".title-schedule")
        if bloque is None:
            return ""
        for hijo in bloque.find_all("div", recursive=False):
            if hijo.get("class"):
                continue
            texto = " ".join(hijo.get_text(" ", strip=True).split())
            if texto:
                return texto
        # Reserva, por si cambian la maquetación
        texto = " ".join(bloque.get_text(" ", strip=True).split())
        for sobra in (
            PP._limpio(bloque, ".schedule-when"),
            PP._limpio(bloque, ".schedule-where"),
        ):
            texto = texto.replace(sobra, " ")
        return " ".join(texto.split())

    @staticmethod
    def _limpio(bloque, selector: str) -> str:
        nodo = bloque.select_one(selector)
        return " ".join(nodo.get_text(" ", strip=True).split()) if nodo else "\0"
