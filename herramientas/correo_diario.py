"""Envía por correo la agenda del día y lo que ha cambiado desde ayer.

Lee los datos que ya ha dejado el recolector, no sale a ninguna web. Se
manda solo lo que pasa los filtros de config.yaml, porque el correo es
para leerlo de un vistazo, no para repetir la web entera.

Las credenciales se leen de variables de entorno, que en GitHub son
secretos del repositorio.

    CORREO_REMITENTE   la cuenta desde la que se envía
    CORREO_CLAVE       su contraseña de aplicación
    CORREO_DESTINO     a quién se manda, admite varios separados por comas

    python herramientas/correo_diario.py [--probar]

Con --probar escribe el correo en pantalla y no envía nada.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "docs" / "datos"
MADRID = ZoneInfo("Europe/Madrid")

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")

SERVIDOR = "smtp.gmail.com"
PUERTO = 465


def en_largo(fecha: dt.date) -> str:
    return f"{DIAS[fecha.weekday()]} {fecha.day} de {MESES[fecha.month - 1]}"


def cargar(nombre: str, por_defecto):
    ruta = DATOS / nombre
    if not ruta.exists():
        return por_defecto
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return por_defecto


def actos_del_dia(actos: list[dict], dia: str) -> list[dict]:
    elegidos = [
        a for a in actos
        if a.get("fecha") == dia
        and a.get("relevante") is not False
        and a.get("estado") != "cancelado"
    ]
    elegidos.sort(key=lambda a: (a.get("hora") or "99:99", a.get("organismo") or ""))
    return elegidos


def cambios_recientes(cambios: list[dict], actos: list[dict], desde: dt.datetime):
    """Modificaciones y cancelaciones de actos que aún están por venir."""
    por_id = {a.get("id"): a for a in actos}
    hoy = dt.datetime.now(MADRID).date().isoformat()
    salida = []
    for cambio in cambios:
        if cambio.get("tipo") not in ("modificacion", "baja"):
            continue
        if (cambio.get("fecha") or "") < hoy:
            continue
        try:
            momento = dt.datetime.fromisoformat(cambio["momento"])
        except Exception:
            continue
        if momento < desde:
            continue
        acto = por_id.get(cambio.get("id"))
        if acto is None or acto.get("relevante") is False:
            continue
        salida.append((cambio, acto))
    return salida


def _fila(acto: dict) -> str:
    hora = escape(acto.get("hora") or "--:--")
    titulo = escape(acto.get("titulo") or "")
    url = acto.get("url") or ""
    enlace = (f' <a href="{escape(url)}" style="color:#9a3412;'
              f'text-decoration:none">ver</a>') if url.startswith("http") else ""
    detalle = " · ".join(
        escape(x) for x in [acto.get("lugar"), acto.get("organismo")] if x
    )
    temas = ", ".join(escape(t) for t in (acto.get("temas") or []))
    return f"""
    <tr>
      <td style="padding:7px 12px 7px 0;vertical-align:top;white-space:nowrap;
                 font-weight:600;color:#9a3412">{hora}</td>
      <td style="padding:7px 0;vertical-align:top">
        <div style="color:#1b1a17">{titulo}{enlace}</div>
        <div style="font-size:13px;color:#6d6a62">{detalle}</div>
        {f'<div style="font-size:12px;color:#9a3412">{temas}</div>' if temas else ''}
      </td>
    </tr>"""


def construir(actos: list[dict], cambios: list[tuple], dia: dt.date, generado: str):
    titular = f"Agenda del {en_largo(dia)}"
    total = len(actos)
    asunto = f"{titular} — {total} acto{'s' if total != 1 else ''}"
    if cambios:
        asunto += f", {len(cambios)} cambio{'s' if len(cambios) != 1 else ''}"

    if actos:
        cuerpo_actos = f"<table style='border-collapse:collapse;width:100%'>{''.join(_fila(a) for a in actos)}</table>"
    else:
        cuerpo_actos = ("<p style='color:#6d6a62'>Hoy no hay ningún acto que "
                        "pase tus filtros.</p>")

    bloque_cambios = ""
    if cambios:
        filas = []
        for cambio, acto in cambios:
            if cambio["tipo"] == "baja":
                que = "cancelado"
            else:
                antes = (cambio.get("antes") or {}).get("hora") or "sin hora"
                despues = (cambio.get("despues") or {}).get("hora") or "sin hora"
                que = f"cambia de {antes} a {despues}" if antes != despues else "modificado"
            cuando = "hoy" if cambio["fecha"] == dia.isoformat() else cambio["fecha"]
            filas.append(
                f"<li style='margin-bottom:5px'><b>{escape(que)}</b> — "
                f"{escape(acto.get('titulo') or '')} "
                f"<span style='color:#6d6a62'>({escape(cuando)})</span></li>"
            )
        bloque_cambios = f"""
        <h3 style="font-size:14px;text-transform:uppercase;letter-spacing:.06em;
                   color:#6d6a62;margin:26px 0 8px">Cambios desde ayer</h3>
        <ul style="padding-left:18px;margin:0">{''.join(filas)}</ul>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#fbfbf9;padding:22px;
  font:16px/1.5 -apple-system,'Segoe UI',Roboto,sans-serif;color:#1b1a17">
  <div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #e4e2dc;
              border-radius:12px;padding:22px">
    <h2 style="margin:0 0 2px;font-size:19px">{escape(titular)}</h2>
    <p style="margin:0 0 18px;font-size:13px;color:#6d6a62">
      {total} acto{'s' if total != 1 else ''} que vigilas. Última revisión {escape(generado[:16].replace('T', ' '))}.</p>
    {cuerpo_actos}
    {bloque_cambios}
    <p style="margin:26px 0 0;font-size:12px;color:#6d6a62;border-top:1px solid #e4e2dc;
              padding-top:12px">
      Agenda institucional. Para ver todo, incluido lo que no pasa los filtros,
      abre la web del proyecto.</p>
  </div>
</body></html>"""

    texto = [titular, ""]
    for acto in actos:
        detalle = " · ".join(x for x in [acto.get("lugar"), acto.get("organismo")] if x)
        texto.append(f"{acto.get('hora') or '--:--'}  {acto.get('titulo')}")
        if detalle:
            texto.append(f"        {detalle}")
    if not actos:
        texto.append("Hoy no hay ningún acto que pase tus filtros.")
    if cambios:
        texto += ["", "CAMBIOS DESDE AYER"]
        for cambio, acto in cambios:
            texto.append(f"- {cambio['tipo']} — {acto.get('titulo')} ({cambio['fecha']})")

    return asunto, html, "\n".join(texto)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Correo diario de la agenda")
    p.add_argument("--probar", action="store_true",
                   help="muestra el correo por pantalla y no envía nada")
    p.add_argument("--forzar", action="store_true",
                   help="envía aunque no sea la hora prevista")
    args = p.parse_args(argv)

    ahora = dt.datetime.now(MADRID)
    # El reloj de GitHub va en UTC y no cambia con el horario de verano, así
    # que el workflow dispara dos veces y aquí se descarta la que no toca
    if not (args.probar or args.forzar) and ahora.hour != 8:
        print(f"No son las 8 en Madrid, son las {ahora:%H:%M}. No se envía.")
        return 0

    datos = cargar("actos.json", {"actos": [], "generado": ""})
    todos = datos.get("actos") or []
    hoy = ahora.date()

    actos = actos_del_dia(todos, hoy.isoformat())
    cambios = cambios_recientes(
        cargar("cambios.json", []), todos, ahora - dt.timedelta(hours=24)
    )
    asunto, html, texto = construir(actos, cambios, hoy, datos.get("generado") or "")

    if args.probar:
        print(f"ASUNTO: {asunto}\n")
        print(texto)
        (RAIZ / "correo_prueba.html").write_text(html, encoding="utf-8")
        print("\nVersión en HTML escrita en correo_prueba.html")
        return 0

    remitente = os.environ.get("CORREO_REMITENTE", "").strip()
    clave = os.environ.get("CORREO_CLAVE", "").replace(" ", "").strip()
    destino = os.environ.get("CORREO_DESTINO", "").strip()
    if not (remitente and clave and destino):
        print("Faltan CORREO_REMITENTE, CORREO_CLAVE o CORREO_DESTINO.")
        return 1

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = destino
    mensaje.set_content(texto)
    mensaje.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL(SERVIDOR, PUERTO, timeout=30) as smtp:
        smtp.login(remitente, clave)
        smtp.send_message(mensaje)

    print(f"Enviado a {destino}. {len(actos)} actos, {len(cambios)} cambios.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
