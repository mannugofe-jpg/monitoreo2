"""Agenda parlamentària del Parlament de Catalunya.

Publica la semana entera, de lunes a domingo, servida en el HTML. Cada
día es un h3 seguido de una tabla donde los actos ocupan dos filas. La
primera lleva la hora y el título, la segunda el tipo de sesión, la sala
y la fecha en que se publicó.

Que dé la semana completa es lo que la hace valiosa, porque es la única
fuente que mira hacia delante.
"""

from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup

from ..fechas import leer_fecha
from ..modelo import Acto
from ..personas import extraer
from .base import Fuente

URL = "https://www.parlament.cat/web/actualitat/agenda/index.html"

RE_HORA = re.compile(r"(\d{1,2}):(\d{2})")
RE_DIA = re.compile(r"(\d{1,2})\s*$")
RE_PUBLICADO = re.compile(r"aparici[oó]\s+al\s+web", re.I)


class Parlament(Fuente):
    clave = "parlament"
    nombre = "Agenda del Parlament de Catalunya"
    organismo = "Parlament de Catalunya"

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
        inicio_semana = self._inicio_semana(sopa, referencia)
        actos: list[Acto] = []

        for h3 in sopa.select("h3.sub_titol_caixa"):
            fecha = self._fecha_del_dia(h3, inicio_semana)
            if fecha is None:
                continue
            tabla = h3.find_next("table", class_="taula_actes_agenda")
            if tabla is None:
                continue
            actos.extend(self._tabla_a_actos(tabla, fecha))

        unicos: dict[str, Acto] = {}
        for acto in actos:
            unicos.setdefault(acto.id, acto)
        return list(unicos.values())

    def _inicio_semana(self, sopa, referencia: dt.date) -> dt.date:
        """El h2 trae el rango, del tipo '23 de novembre de 2026 - 29 de...'."""
        for h2 in sopa.find_all("h2"):
            texto = " ".join(h2.get_text(" ", strip=True).split())
            if "-" not in texto:
                continue
            leida = leer_fecha(texto.split("-")[0], referencia)
            if leida:
                return leida
        return referencia - dt.timedelta(days=referencia.weekday())

    def _fecha_del_dia(self, h3, inicio_semana: dt.date) -> dt.date | None:
        """El h3 dice 'Dilluns, 23'. El número de día basta para situarlo."""
        texto = " ".join(h3.get_text(" ", strip=True).split())
        m = RE_DIA.search(texto)
        if not m:
            return None
        dia = int(m.group(1))
        # La semana puede cruzar el cambio de mes
        for salto in range(0, 8):
            candidata = inicio_semana + dt.timedelta(days=salto)
            if candidata.day == dia:
                return candidata
        return None

    def _tabla_a_actos(self, tabla, fecha: dt.date) -> list[Acto]:
        actos: list[Acto] = []
        pendiente: dict | None = None

        for fila in tabla.find_all("tr"):
            cabecera = fila.find("th", class_="hora_lloc")
            if cabecera is not None:
                if pendiente:
                    actos.append(self._construir(pendiente, fecha))
                hora = None
                m = RE_HORA.search(cabecera.get_text(" ", strip=True))
                if m:
                    hora = f"{int(m.group(1)):02d}:{m.group(2)}"
                celda = fila.find("td")
                titulo = (
                    " ".join(celda.get_text(" ", strip=True).split()) if celda else ""
                )
                pendiente = {"hora": hora, "titulo": titulo, "detalle": []}
                continue

            detalle = fila.find("td", class_="tema_acte")
            if detalle is not None and pendiente is not None:
                for parrafo in detalle.find_all("p"):
                    texto = " ".join(parrafo.get_text(" ", strip=True).split())
                    if texto and not RE_PUBLICADO.search(texto):
                        pendiente["detalle"].append(texto)

        if pendiente:
            actos.append(self._construir(pendiente, fecha))
        return [a for a in actos if a is not None]

    def _construir(self, datos: dict, fecha: dt.date) -> Acto | None:
        titulo = datos["titulo"]
        if not titulo or len(titulo) < 6:
            return None
        detalle = datos["detalle"]
        persona, cargo = extraer(titulo)

        return Acto(
            fuente=self.clave,
            organismo=self.organismo,
            persona=persona,
            cargo=cargo,
            fecha=fecha.isoformat(),
            hora=datos["hora"],
            titulo=titulo,
            lugar=", ".join(detalle[:2]) if detalle else None,
            notas=detalle[2:],
            url=URL,
        )
