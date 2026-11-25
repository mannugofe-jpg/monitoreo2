"""Contrato que cumple cualquier fuente de agenda.

Para añadir una fuente nueva basta con crear una clase que herede de
Fuente, implementar recolectar_dia y registrarla en fuentes/__init__.py.
"""

from __future__ import annotations

import time
import datetime as dt

import requests

from ..modelo import Acto

CABECERAS = {
    "User-Agent": (
        "agenda-institucional/1.0 (proyecto personal de agregación de "
        "agendas públicas; contacto en el repositorio)"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}


class Fuente:
    clave: str = ""          # identificador corto, p. ej. "moncloa"
    nombre: str = ""         # nombre legible
    organismo: str = ""      # institución a la que pertenece
    pausa_segundos: float = 1.5

    def __init__(self, sesion: requests.Session | None = None) -> None:
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update(CABECERAS)

    def descargar(self, url: str) -> str:
        respuesta = self.sesion.get(url, timeout=30)
        respuesta.raise_for_status()
        respuesta.encoding = respuesta.apparent_encoding or "utf-8"
        time.sleep(self.pausa_segundos)
        return respuesta.text

    def recolectar_dia(self, fecha: dt.date) -> list[Acto]:
        raise NotImplementedError

    def ambito_fechas(self, fechas: list[dt.date], actos: list[Acto]) -> set[str]:
        """Días que esta pasada ha mirado de verdad, para la reconciliación.

        Las fuentes con una URL por día han mirado todos los pedidos. Las
        que son un listado solo han visto los días que aparecían en él.
        """
        return {f.isoformat() for f in fechas}

    def recolectar(self, fechas: list[dt.date]) -> list[Acto]:
        actos: list[Acto] = []
        for fecha in fechas:
            try:
                encontrados = self.recolectar_dia(fecha)
            except Exception as error:  # una fuente caída no tumba el resto
                print(f"  [aviso] {self.clave} {fecha} -> {error}")
                continue
            print(f"  {self.clave} {fecha} -> {len(encontrados)} actos")
            actos.extend(encontrados)
        return actos
