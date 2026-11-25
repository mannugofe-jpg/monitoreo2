"""Previsions de l'Agència Catalana de Notícies.

La página es pública y llega servida desde el servidor, no montada con
JavaScript, así que se puede leer con requests. El orden del documento
es hora, municipio y después el titular del acto en un h3. El parser
recorre el texto en ese orden y va arrastrando la última hora y el
último municipio vistos.

Esta fuente no acepta una URL por día. Publica el día en curso, así que
se visita una sola vez por pasada y se queda con las fechas que haya.
"""

from __future__ import annotations

import datetime as dt
import re

from bs4 import BeautifulSoup, NavigableString

from ..fechas import leer_fecha
from ..filtros import normalizar
from ..modelo import Acto
from .base import Fuente

URL = "https://www.acn.cat/previsions"

RE_HORA = re.compile(r"^(\d{1,2}):(\d{2})$")
RE_DIA = re.compile(
    r"\b(dilluns|dimarts|dimecres|dijous|divendres|dissabte|diumenge)\b", re.I
)
IGNORAR = {
    "consulta les previsions per a dema",
    "consulta les previsions per avui",
    "previsions",
    "al minut",
    "fotos",
    "videos",
    "audios",
    "pool",
}


class ACN(Fuente):
    clave = "acn"
    nombre = "Previsions de l'ACN"
    organismo = "Agència Catalana de Notícies"

    def recolectar(self, fechas: list[dt.date]) -> list[Acto]:
        try:
            actos = self.parsear(self.descargar(URL), fechas[0] if fechas else None)
        except Exception as error:
            print(f"  [aviso] {self.clave} -> {error}")
            return []
        print(f"  {self.clave} -> {len(actos)} actos")
        return actos

    def ambito_fechas(self, fechas, actos):
        # Solo se reconcilian los días que la página ha llegado a mostrar
        return {a.fecha for a in actos}

    def parsear(self, html: str, referencia: dt.date | None = None) -> list[Acto]:
        sopa = BeautifulSoup(html, "lxml")
        for basura in sopa(["script", "style", "nav", "footer", "header"]):
            basura.decompose()

        referencia = referencia or dt.date.today()
        fecha_actual: dt.date | None = None
        hora: str | None = None
        lugar: str | None = None
        actos: list[Acto] = []

        for cadena in sopa.find_all(string=True):
            if not isinstance(cadena, NavigableString):
                continue
            texto = " ".join(cadena.split())
            if not texto or normalizar(texto).strip() in IGNORAR:
                continue
            padre = cadena.parent.name if cadena.parent else ""

            # Encabezado de día
            if RE_DIA.search(texto) and len(texto) < 80:
                nueva = leer_fecha(texto, referencia)
                if nueva:
                    fecha_actual = nueva
                    hora = lugar = None
                    continue

            m = RE_HORA.match(texto)
            if m and len(texto) <= 5:
                hora = f"{int(m.group(1)):02d}:{m.group(2)}"
                lugar = None
                continue

            if padre in ("h3", "h2") and len(texto) > 12:
                if fecha_actual is None:
                    fecha_actual = referencia
                actos.append(
                    Acto(
                        fuente=self.clave,
                        organismo=self.organismo,
                        persona="",
                        cargo="",
                        fecha=fecha_actual.isoformat(),
                        hora=hora,
                        titulo=texto,
                        lugar=lugar,
                        url=URL,
                    )
                )
                continue

            # Municipio, entre la hora y el titular
            if hora and lugar is None and 2 < len(texto) < 60 and padre not in ("a",):
                lugar = texto

        # Quita duplicados que la portada repite como destacados
        unicos: dict[str, Acto] = {}
        for acto in actos:
            unicos.setdefault(acto.id, acto)
        return list(unicos.values())
