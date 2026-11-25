"""Utilidades compartidas por las cuatro agendas oficiales del PSOE."""
from __future__ import annotations

import datetime as dt
import re
import time
import unicodedata
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser

from ..modelo import Acto
from .base import Fuente

BASE = 'https://www.psoe.es/agenda/'
ROBOTS = 'https://www.psoe.es/robots.txt'
DIAS = ('lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')


def limpio(s):
    return ' '.join(s.split())


def normal(s):
    return ''.join(c for c in unicodedata.normalize('NFD', limpio(s)) if not unicodedata.combining(c)).casefold()


def dia_mes(f):
    return f'{f.day}-de-{MESES[f.month-1]}'


def dia_completo(f):
    return f'{DIAS[f.weekday()]}-{dia_mes(f)}'


_FECHA = re.compile(r'^(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(\d{1,2})\s+de\s+(' + '|'.join(MESES) + r')\s+(?:de\s+)?(20\d{2})(?:,?\s+\d{1,2}:\d{2})?$')
_HORA = re.compile(r'(?<!\w)(?:a\s+las\s+)?(?P<h>[01]?\d|2[0-3])[:.](?P<m>[0-5]\d)\s*(?:horas?\b|h\b)\.?', re.I)
_BALA = re.compile(r'^\s*[◘•●▪‣*–—-]\s*')
_SECCION = re.compile(r'^(?:previsiones (?:del|de la|de los|de las|de senadores)|comision ejecutiva federal$)', re.I)
_SIGUIENTE = re.compile(r'^(?:posteriormente|finalmente|mas tarde|por la tarde|por la manana|a continuacion|despues|seguidamente)\b', re.I)
_ACCION = re.compile(r'\b(?:interviene|participa|asiste|ofrece|mantiene|se reune|se reúne|visita|comparece|presenta|atiende|es entrevistad[oa]|realiza|inaugura|organiza|acude|pronuncia|clausura|celebra|acompaña|se entrevista|preside|toma parte|recibe|departe)\b', re.I)


def _fecha_linea(s):
    m = _FECHA.fullmatch(normal(s))
    if m:
        try:
            return dt.date(int(m[3]), MESES.index(m[2])+1, int(m[1]))
        except ValueError:
            pass
    return None


class _HTML(HTMLParser):
    """Conserva bloques, h1 y separaciones de listas sin paquetes externos."""
    bloques = {'p','div','section','article','main','li','br','hr','h1','h2','h3','h4','h5','h6','blockquote','tr','td','header','footer','nav'}
    ocultos = {'script','style','noscript','template','svg'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self.buffer = []
        self.h1 = False
        self.oculto = []

    def flush(self):
        s = limpio(''.join(self.buffer))
        if s:
            self.partes.append(('h1' if self.h1 else 'texto', s))
        self.buffer.clear()

    def handle_starttag(self, tag, attrs):
        if tag in self.ocultos:
            self.oculto.append(tag)
        elif not self.oculto and tag in self.bloques:
            self.flush()
            if tag == 'h1':
                self.h1 = True

    def handle_endtag(self, tag):
        if self.oculto:
            if tag == self.oculto[-1]:
                self.oculto.pop()
        elif tag in self.bloques:
            self.flush()
            if tag == 'h1':
                self.h1 = False

    def handle_data(self, data):
        if not self.oculto:
            self.buffer.append(data.replace('\n',' '))

    def close(self):
        super().close()
        self.flush()


def _bloques(bruto):
    if re.search(r'<(?:html|body|p|div|h1|article)\b', bruto, re.I):
        p = _HTML(); p.feed(bruto); p.close()
        return p.partes
    # Permite probar con la version textual de una pagina.
    return [('h1' if l.startswith('# ') else 'texto', limpio(l.removeprefix('# '))) for l in bruto.splitlines() if limpio(l)]


def _actor(s):
    """Extrae solo un sujeto explicito; mantiene su texto completo en el titulo."""
    s = re.sub(r'^\s*\(hora insular\)\.?\s*', '', s, flags=re.I)
    m = _ACCION.search(s)
    if not m:
        return '', '', ''
    sujeto = s[:m.start()].strip(' ,.:')
    if not sujeto or len(sujeto) > 300 or _SIGUIENTE.match(normal(sujeto)):
        return '', '', ''
    partes = sujeto.split(',')
    candidato = partes[-1].strip()
    if re.fullmatch(r'[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ.’-]+(?:\s+(?:(?:de|del|la|las|los|y)\s+)?[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ.’-]+)+', candidato):
        return candidato, ','.join(partes[:-1]).strip(), sujeto
    return '', '', ''


# El control es comun a las cuatro fuentes, no cuatro pausas independientes.
_robots = None
_robots_error = None
_ultimo = 0.0
_pausa = 5.0


def _status(error):
    return getattr(getattr(error, 'response', None), 'status_code', None)


def _descarga(fuente, url):
    global _robots, _robots_error, _ultimo, _pausa
    if _robots_error:
        raise PermissionError(_robots_error)
    if _robots is None:
        r = RobotFileParser(ROBOTS)
        try:
            texto = fuente.descargar(ROBOTS)
        except Exception as e:
            if _status(e) not in (404, 410):
                _robots_error = f'No se pudo comprobar robots.txt: {e}'
                raise PermissionError(_robots_error) from e
            texto = ''
        if not isinstance(texto, str) or re.search(r'<html\b', texto, re.I):
            _robots_error = 'robots.txt no es una respuesta textual valida'
            raise PermissionError(_robots_error)
        r.parse(texto.splitlines())
        _pausa = max(5.0, r.crawl_delay('*') or 0)
        rr = r.request_rate('*')
        if rr and rr.requests:
            _pausa = max(_pausa, rr.seconds / rr.requests)
        _robots = r
        _ultimo = time.monotonic()
    if not _robots.can_fetch('*', url):
        raise PermissionError('Ruta no permitida por robots.txt')
    time.sleep(max(0.0, _pausa - (time.monotonic() - _ultimo)))
    try:
        return fuente.descargar(url)
    finally:
        _ultimo = time.monotonic()


class PSOEBase(Fuente):
    organismo = 'PSOE'
    pausa_segundos = 5.0
    modalidad = ''

    def urls(self, fecha):
        raise NotImplementedError

    def fechas_pagina(self, fecha):
        return (fecha,)

    def recolectar(self, fechas: list[dt.date]) -> list[Acto]:
        fechas = sorted(set(fechas or [dt.date.today()]))
        solicitadas = {f.isoformat() for f in fechas}
        unicos = {}
        visitadas = set()
        for fecha in fechas:
            for url in self.urls(fecha):
                if url in visitadas:
                    continue
                visitadas.add(url)
                try:
                    bruto = _descarga(self, url)
                    actos = self.parsear(bruto, fecha, url)
                except Exception as e:
                    if _status(e) in (404, 410):
                        continue
                    print(f'  [aviso] {self.clave} {fecha} -> {e}')
                    if isinstance(e, PermissionError) or _status(e) in (401,403,429) or 'robots.txt' in str(e):
                        print(f'  {self.clave} -> {len(unicos)} actos (recoleccion interrumpida)')
                        return list(unicos.values())
                    continue
                for a in actos:
                    if a.fecha in solicitadas:
                        clave = (a.fecha, a.hora, normal(a.titulo))
                        unicos.setdefault(clave, a)
                # Las variantes de URL de una fecha son alternativas.
                if actos:
                    break
        print(f'  {self.clave} -> {len(unicos)} actos ({len(visitadas)} URLs consultadas)')
        return list(unicos.values())

    def ambito_fechas(self, fechas, actos):
        # No dar por cubiertas fechas con error, 404 o sin actos reconocidos.
        return {a.fecha for a in actos}

    def _titulo_valido(self, titulo, fechas):
        n = re.sub(r'^(congreso|senado)\s*[:.–—-]?\s+', r'\1. ', normal(titulo))
        prefijo = {'general':'previsiones ', 'cef':'previsiones cef ', 'congreso':'congreso. previsiones ', 'senado':'senado. previsiones '}[self.modalidad]
        if not n.startswith(prefijo):
            return False
        if self.modalidad == 'general' and n.startswith('previsiones cef '):
            return False
        if len(fechas) == 2:
            a,b = fechas
            patron = rf'\bsabado\s+{a.day}\b.*\bdomingo\s+{b.day}\s+de\s+{MESES[b.month-1]}\b'
        else:
            f = fechas[0]
            patron = rf'\b{f.day}\s+de\s+{MESES[f.month-1]}\b'
            if self.modalidad != 'cef' and DIAS[f.weekday()] not in n:
                return False
        anos = re.findall(r'\b20\d{2}\b', n)
        return bool(re.search(patron,n)) and (not anos or str(fechas[0].year) in anos or str(fechas[-1].year) in anos)

    def parsear(self, bruto: str, referencia: dt.date, url: str | None = None) -> list[Acto]:
        if not isinstance(bruto,str) or not bruto.strip():
            raise ValueError('Respuesta vacia')
        fechas = self.fechas_pagina(referencia)
        bloques = _bloques(bruto)
        i = next((i for i,(tipo,s) in enumerate(bloques) if tipo=='h1' and self._titulo_valido(s,fechas)),None)
        if i is None:
            raise ValueError('No se reconoce el titular de la agenda solicitada')
        titulo = bloques[i][1]
        # Las URL sin ano pueden pertenecer a otro ejercicio. La fecha propia
        # de la pagina aparece inmediatamente antes del H1, no en destacados.
        metadato = next((d for _,s in reversed(bloques[max(0,i-6):i]) if (d:=_fecha_linea(s))),None)
        anos = re.findall(r'\b20\d{2}\b', titulo)
        if metadato:
            if not (fechas[0]-dt.timedelta(days=7) <= metadato <= fechas[-1]+dt.timedelta(days=1)):
                raise ValueError('La fecha de publicacion no corresponde a la agenda solicitada')
        elif not anos:
            raise ValueError('No se ha podido confirmar el ano de la agenda')
        fecha = fechas[0] if len(fechas)==1 else None
        seccion = ''
        contexto = ('','','')
        entradas = []
        for tipo, texto in bloques[i+1:]:
            n = normal(texto)
            if tipo=='h1' or n.startswith(('compartir en','compartir por','psoe - cef','aviso legal','politica de privacidad','actos destacados','compartir este','politica de cookies')):
                break
            d = _fecha_linea(texto)
            if d:
                fecha = d if d in fechas else None
                contexto = ('','',''); seccion = ''
                continue
            if fecha is None:
                continue
            if _SECCION.match(n):
                seccion = texto; contexto = ('','','')
                continue
            bala = bool(_BALA.match(texto))
            texto = _BALA.sub('',texto)
            if re.search(r'\b(?:siguiente agenda|siguientes actos)\s*:?$',normal(texto)):
                actor = _actor(texto)
                if actor[0]: contexto = actor
                continue
            if n.startswith(('la organizacion ofrecera','se retransmitira','se ofrecera','por satelite','nota:','senal de','senal realizada','acreditaciones')):
                if entradas:
                    entradas[-1]['notas'].append(texto)
                continue
            # Varias horas en el mismo parrafo: solo separa cuando el texto
            # anuncia otro acto (no horarios de emision o de acreditacion).
            trozos = re.split(r'(?i)(?<=\.)\s+(?=(?:posteriormente|finalmente|mas tarde|más tarde|por la tarde|por la mañana|a continuación|después|seguidamente),?\s+(?:a\s+las\s+)?\d{1,2}[:.]\d{2}\s*(?:h|hora))',texto)
            for j,t in enumerate(trozos):
                t = limpio(t)
                horas = list(_HORA.finditer(t))
                es_acto = bool(horas or bala or _SIGUIENTE.match(normal(t)) or _ACCION.search(t))
                if not es_acto:
                    if entradas and len(t)>4:
                        entradas[-1]['notas'].append(t)
                    continue
                hora = None
                desc = t
                if horas:
                    h = horas[0]; hora = f'{int(h["h"]):02d}:{h["m"]}'
                    antes = t[:h.start()].strip(' ,.:')
                    if not antes or _SIGUIENTE.match(normal(antes)):
                        desc = t[h.end():].strip(' ,.:')
                    elif not t[h.end():].strip(' ,.:'):
                        desc = antes
                    # Hora situada en mitad del acto: conservar el original.
                actor = _actor(desc)
                if actor[0]:
                    contexto = actor
                elif contexto[0] and (j>0 or _SIGUIENTE.match(normal(t)) or re.match(r'^(?:participa|interviene|asiste|ofrece|visita|a un acto)',normal(desc))):
                    actor = contexto
                    desc = f'{contexto[0]}: {desc}'
                if len(desc)<6:
                    continue
                notas = [seccion] if seccion else []
                entradas.append(dict(fecha=fecha.isoformat(), hora=hora, titulo=desc, persona=actor[0], cargo=actor[1], lugar=None, notas=notas))
        if not entradas:
            raise ValueError('Agenda localizada, pero no se han reconocido actos')
        unicos = {}
        for e in entradas:
            e['notas'] = list(dict.fromkeys(e['notas']))
            a = Acto(fuente=self.clave, organismo=self.organismo, url=url or self.urls(referencia)[0], **e)
            unicos.setdefault((a.fecha,a.hora,normal(a.titulo)),a)
        return list(unicos.values())
