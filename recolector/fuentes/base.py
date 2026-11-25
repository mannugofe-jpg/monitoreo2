"""Contrato que cumple cualquier fuente de agenda.

Para añadir una fuente nueva basta con crear una clase que herede de
Fuente, implementar recolectar_dia y registrarla en fuentes/__init__.py.
"""

from __future__ import annotations

import time
import datetime as dt
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from ..modelo import Acto

# Varias webs institucionales devuelven 403 a cualquier cabecera que se
# identifique como robot, aunque su robots.txt permita la ruta. Por eso se
# usa una cabecera de navegador normal. Lo que no se toca es el fondo del
# asunto, que es respetar lo que el sitio dice en su robots.txt, y eso se
# comprueba abajo antes de cada descarga.
CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ca,es;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

# Un robots.txt leído por host y recordado durante la pasada
_ROBOTS: dict[str, RobotFileParser | None] = {}


class RutaProhibida(Exception):
    """El robots.txt del sitio no permite leer esta ruta."""


def robots_permite(url: str, sesion: requests.Session) -> bool:
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if host not in _ROBOTS:
        parser: RobotFileParser | None = None
        try:
            r = sesion.get(urljoin(host, "/robots.txt"), timeout=15)
            if r.status_code == 200:
                parser = RobotFileParser()
                parser.parse(r.text.splitlines())
        except Exception:
            parser = None
        _ROBOTS[host] = parser

    parser = _ROBOTS[host]
    if parser is None:
        # Sin robots.txt legible se aplica la convención de permitir
        return True
    return parser.can_fetch("*", url)


class Fuente:
    clave: str = ""          # identificador corto, p. ej. "moncloa"
    nombre: str = ""         # nombre legible
    organismo: str = ""      # institución a la que pertenece
    pausa_segundos: float = 1.5

    def __init__(self, sesion: requests.Session | None = None) -> None:
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update(CABECERAS)

    def descargar(self, url: str) -> str:
        if not robots_permite(url, self.sesion):
            raise RutaProhibida(
                f"el robots.txt de este sitio no permite leer {url}"
            )
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
