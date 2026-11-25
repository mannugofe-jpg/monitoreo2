"""Agenda informativa de EFE Espana publicada en Infobae.

Genera la URL de cada agenda a partir de su fecha: la ruta corresponde
al dia anterior y el titular a la fecha de los actos. No se consultan
URLs cuya fecha prevista de publicacion aun no ha llegado.

Se extrae la seccion AGENDA INFORMATIVA, no las previsiones editoriales
que la preceden. La hora es opcional; no se inventan personas, cargos
ni horas. El robots.txt consultado el 25/11/2026 no excluye esta ruta.
Se utiliza la descarga y la pausa de la clase Fuente, como en diba.py.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from ..modelo import Acto
from .base import Fuente

URL_BASE = "https://www.infobae.com/espana/agencias/"
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def url_agenda(fecha: dt.date) -> str:
    publicacion = fecha - dt.timedelta(days=1)
    return (f"{URL_BASE}{publicacion:%Y/%m/%d}/temas-del-dia-de-efe-espana-del-"
            f"{DIAS[fecha.weekday()]}-{fecha.day}-de-{MESES[fecha.month - 1]}-"
            f"de-{fecha.year}/")


def _limpiar(texto: str) -> str:
    return " ".join(texto.split())


def _normalizar(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", _limpiar(texto))
                   if not unicodedata.combining(c)).casefold()


class _TextoHTML(HTMLParser):
    """Extrae bloques visibles sin dependencias externas."""

    BLOQUES = {"p", "div", "section", "article", "main", "li", "br", "hr",
               "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}
    OCULTOS = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.ocultos: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.OCULTOS:
            self.ocultos.append(tag)
        elif not self.ocultos and tag in self.BLOQUES:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if self.ocultos:
            if tag == self.ocultos[-1]:
                self.ocultos.pop()
        elif tag in self.BLOQUES:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self.ocultos:
            self.partes.append(data.replace("\n", " "))

    def lineas(self) -> list[str]:
        return [t for l in "".join(self.partes).splitlines() if (t := _limpiar(l))]


_HORA = re.compile(r"^(?P<hora>\d{1,2}[:.]\d{2})\s*h?\s*\.\s*[-–—]\s*", re.I)
_SEPARADOR = re.compile(r"\s*\.\s*[-–—]\s*")
_BULLET = re.compile(r"^[-–—]\s+")
_FORMATOS = re.compile(r"\s*\((?:Texto|Foto|V[ií]deo|Audio|Directo|Infograf[ií]a|"
                       r"Recursos de archivo)(?:\b[^)]*)?\)", re.I)


class InfobaeEFE(Fuente):
    clave = "infobae_efe"
    nombre = "Temas del dia de EFE Espana (Infobae)"
    organismo = "Agencia EFE"
    pausa_segundos = 10.0  # pausa prudencial; no es un requisito publicado

    def recolectar(self, fechas: list[dt.date]) -> list[Acto]:
        hoy = dt.datetime.now(ZoneInfo("Europe/Madrid")).date()
        fechas = sorted(set(fechas or [hoy, hoy + dt.timedelta(days=1)]))
        unicos: dict[str, Acto] = {}
        for fecha in fechas:
            if fecha > hoy + dt.timedelta(days=1):
                continue
            url = url_agenda(fecha)
            try:
                actos = self.parsear(self.descargar(url), fecha)
            except Exception as error:
                print(f"  [aviso] {self.clave} {fecha} -> {error}")
                continue
            for acto in actos:
                unicos.setdefault(acto.id, acto)
        print(f"  {self.clave} -> {len(unicos)} actos")
        return list(unicos.values())

    def ambito_fechas(self, fechas, actos):
        # No declarar cubiertas fechas no publicadas, fallidas o sin actos.
        return {a.fecha for a in actos}

    def parsear(self, bruto: str, referencia: dt.date) -> list[Acto]:
        if not isinstance(bruto, str) or not bruto.strip():
            raise ValueError("Respuesta vacia o no textual")
        if re.search(r"<(?:html|body|p|div|article|h1)\b", bruto, re.I):
            parser = _TextoHTML()
            parser.feed(bruto)
            parser.close()
            lineas = parser.lineas()
        else:
            lineas = [t for l in bruto.splitlines() if (t := _limpiar(l))]

        fecha_titular = f"{referencia.day} de {MESES[referencia.month - 1]} de {referencia.year}"
        patron_titular = re.compile(r"temas del dia de efe espana del "
                                    r"(?:\w+ )?" + re.escape(fecha_titular) + r"\b")
        if not any(patron_titular.search(_normalizar(l)) for l in lineas):
            raise ValueError("No se encuentra el titular de la agenda solicitada")

        comienzo = next((i for i, l in enumerate(lineas)
                         if _normalizar(l).rstrip(":") == "agenda informativa"), None)
        if comienzo is None:
            raise ValueError("No se encuentra la seccion AGENDA INFORMATIVA")

        seccion = ""
        entradas: list[tuple[str, str]] = []
        for linea in lineas[comienzo + 1:]:
            normal = _normalizar(linea)
            if normal.startswith(("redaccion efe", "puede escribir a", "en www.efeservicios",
                                  "para cualquier otro producto", "ultimas noticias",
                                  "te recomendamos")):
                break
            if linea.isupper() and len(linea) <= 100 and not _SEPARADOR.search(linea):
                seccion = linea.rstrip(":")
                continue
            if _HORA.match(linea) or len(_SEPARADOR.split(linea, maxsplit=2)) == 3 or _BULLET.match(linea):
                entradas.append((seccion, linea))
            elif entradas and linea.startswith(("(", "Declaraciones a medios")):
                # Informacion complementaria del acto inmediatamente anterior.
                anterior_seccion, anterior = entradas[-1]
                entradas[-1] = (anterior_seccion, anterior + " " + linea)

        actos: dict[tuple, Acto] = {}
        for seccion, linea in entradas:
            acto = self._linea_a_acto(linea, seccion, referencia)
            if acto is not None:
                clave = (acto.fecha, acto.hora, _normalizar(acto.lugar or ""),
                         _normalizar(acto.titulo))
                actos.setdefault(clave, acto)
        if not actos:
            raise ValueError("Agenda localizada, pero no se han reconocido actos")
        return list(actos.values())

    def _linea_a_acto(self, linea: str, seccion: str, fecha: dt.date) -> Acto | None:
        hora = None
        lugar = None
        tema = ""
        match = _HORA.match(linea)
        if match:
            h, m = map(int, re.split(r"[:.]", match.group("hora")))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                return None
            hora = f"{h:02d}:{m:02d}"
            linea = linea[match.end():]

        if _BULLET.match(linea):
            descripcion = _BULLET.sub("", linea, count=1)
        else:
            partes = _SEPARADOR.split(linea, maxsplit=2)
            if len(partes) == 3:
                lugar, tema, descripcion = map(_limpiar, partes)
                # Algunas entradas repiten la ciudad antes del tema.
                if tema == lugar:
                    extra = _SEPARADOR.split(descripcion, maxsplit=1)
                    if len(extra) == 2:
                        tema, descripcion = map(_limpiar, extra)
            elif len(partes) == 2 and hora is not None:
                lugar, descripcion = map(_limpiar, partes)
            elif hora is not None:
                descripcion = _limpiar(linea)
            else:
                return None

        descripcion = _limpiar(_FORMATOS.sub("", descripcion)).strip(" .")
        if len(descripcion) < 6:
            return None
        notas = list(dict.fromkeys(p for p in (seccion, tema) if p))
        # La descripcion se conserva completa, incluidas referencias al recinto
        # y a participantes, sin atribuir automaticamente un cargo o persona.
        return Acto(
            fuente=self.clave,
            organismo=self.organismo,
            persona="",
            cargo="",
            fecha=fecha.isoformat(),
            hora=hora,
            titulo=descripcion,
            lugar=lugar or None,
            notas=notas,
            url=url_agenda(fecha),
        )
