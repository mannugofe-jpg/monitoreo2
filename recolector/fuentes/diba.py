"""Agenda corporativa de la Diputació de Barcelona, por datos abiertos.

La web de la Diputació tiene Disallow en su robots.txt, así que no se
raspa. En cambio publican la agenda como conjunto de datos abiertos,
con licencia Creative Commons y pensado justo para esto.

Una sola petición devuelve el conjunto entero, con actos de varios años,
así que basta con una visita por pasada y luego filtrar por fecha. El
robots.txt del servidor de datos pide diez segundos entre peticiones y
se respetan, aunque solo se haga una.

El conjunto no incluye la agenda de los cargos electos, pero sí los
plenos ordinarios de la Diputació, que es lo que interesa aquí.
"""

from __future__ import annotations

import datetime as dt
import json

from ..modelo import Acto
from .base import Fuente

URL = "https://do.diba.cat/api/dataset/agendageneral_ca/format/json"

# Cuánto futuro se guarda. El conjunto llega hasta dentro de dos años y
# no tiene sentido arrastrarlo entero
DIAS_ADELANTE = 120
DIAS_ATRAS = 2


class DIBA(Fuente):
    clave = "diba"
    nombre = "Agenda corporativa de la Diputació de Barcelona"
    organismo = "Diputació de Barcelona"
    pausa_segundos = 10.0  # lo que pide su robots.txt

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

    def parsear(self, bruto: str, referencia: dt.date) -> list[Acto]:
        datos = json.loads(bruto)
        elementos = datos.get("elements") or []

        desde = (referencia - dt.timedelta(days=DIAS_ATRAS)).isoformat()
        hasta = (referencia + dt.timedelta(days=DIAS_ADELANTE)).isoformat()

        actos: list[Acto] = []
        for elemento in elementos:
            acto = self._elemento_a_acto(elemento, desde, hasta)
            if acto is not None:
                actos.append(acto)

        unicos: dict[str, Acto] = {}
        for acto in actos:
            unicos.setdefault(acto.id, acto)
        return list(unicos.values())

    def _elemento_a_acto(self, elemento: dict, desde: str, hasta: str) -> Acto | None:
        inicio = (elemento.get("data_inici") or "").strip()
        if len(inicio) < 10:
            return None
        fecha = inicio[:10]
        if not (desde <= fecha <= hasta):
            return None

        titulo = " ".join((elemento.get("titol") or "").split())
        if len(titulo) < 6:
            return None

        hora = inicio[11:16] if len(inicio) >= 16 else None
        if hora == "00:00":
            hora = None

        notas = []
        tema = elemento.get("rel_temes")
        if isinstance(tema, dict) and tema.get("tema_nom"):
            notas.append(str(tema["tema_nom"]))
        cuerpo = " ".join((elemento.get("cos") or "").split())
        if cuerpo:
            notas.append(cuerpo[:280])

        return Acto(
            fuente=self.clave,
            organismo=self.organismo,
            persona="",
            cargo="",
            fecha=fecha,
            hora=hora,
            titulo=titulo,
            lugar=self._lugar(elemento),
            notas=notas,
            url=(elemento.get("acte_url") or URL).strip() or URL,
        )

    @staticmethod
    def _lugar(elemento: dict) -> str | None:
        direccion = elemento.get("grup_adreca")
        if not isinstance(direccion, dict):
            return None
        partes = [
            " ".join(str(direccion.get(campo) or "").split())
            for campo in ("adreca_nom", "municipi_nom")
        ]
        partes = [p for p in partes if p]
        return ", ".join(dict.fromkeys(partes)) or None
