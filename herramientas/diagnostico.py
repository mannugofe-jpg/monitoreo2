"""Inspecciona una web de agenda y dice cómo publica sus datos.

Descarga la página, guarda el HTML y escribe un informe con lo que hace
falta saber antes de escribir un lector. Si hay un feed, no hay que
raspar nada. Si la página se monta con JavaScript, hay que buscar la
llamada que trae los datos.

    python herramientas/diagnostico.py URL [URL ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

CABECERAS = {
    "User-Agent": (
        "agenda-institucional/1.0 (proyecto personal de agregación de "
        "agendas públicas; contacto en el repositorio)"
    ),
    "Accept-Language": "ca,es;q=0.9,en;q=0.8",
}

SALIDA = Path("diagnostico")
RE_HORA = re.compile(r"\b\d{1,2}[:.]\d{2}\s*(?:h|hores|horas)?\b")

# Rutas que suelen esconder datos estructurados
CANDIDATAS = [
    "/feed/",
    "/rss",
    "?ical=1",
    "/wp-json/tribe/events/v1/events",
    "/wp-json/wp/v2/posts",
]


def nombre_archivo(url: str) -> str:
    p = urlparse(url)
    limpio = (p.netloc + p.path).replace("/", "_").strip("_")
    return re.sub(r"[^A-Za-z0-9._-]", "_", limpio)[:80] or "pagina"


def inspeccionar(url: str) -> None:
    print("=" * 72)
    print(url)
    print("=" * 72)

    try:
        r = requests.get(url, headers=CABECERAS, timeout=30)
    except Exception as error:
        print(f"  NO SE PUDO DESCARGAR -> {error}\n")
        return

    r.encoding = r.apparent_encoding or "utf-8"
    html = r.text
    print(f"  Estado {r.status_code}, {len(html)} caracteres, "
          f"{r.headers.get('content-type', 'sin tipo')}")

    if r.status_code != 200:
        print()
        return

    SALIDA.mkdir(exist_ok=True)
    destino = SALIDA / (nombre_archivo(url) + ".html")
    destino.write_text(html, encoding="utf-8")

    sopa = BeautifulSoup(html, "lxml")
    for basura in sopa(["script", "style"]):
        basura.decompose()
    texto = sopa.get_text(" ", strip=True)

    scripts = html.lower().count("<script")
    proporcion = len(texto) / max(len(html), 1)
    print(f"  Texto visible {len(texto)} caracteres, {scripts} scripts, "
          f"proporción {proporcion:.2%}")
    if proporcion < 0.03 or len(texto) < 1500:
        print("  AVISO. Parece montada con JavaScript, el contenido no está "
              "en el HTML. Busca la llamada de datos en la pestaña de red.")
    else:
        print("  El contenido llega servido, se puede leer con requests.")

    # Gestor y pistas de plugin
    if "wp-content" in html:
        print("  Es un WordPress.")
    if "tribe-events" in html or "the-events-calendar" in html:
        print("  Usa el plugin The Events Calendar, que trae API y iCal.")

    # Feeds declarados en la cabecera
    feeds = []
    for enlace in BeautifulSoup(html, "lxml").find_all("link", href=True):
        tipo = (enlace.get("type") or "").lower()
        if any(k in tipo for k in ("rss", "atom", "calendar", "json")):
            feeds.append((tipo, urljoin(url, enlace["href"])))
    if feeds:
        print("  Feeds declarados")
        for tipo, href in feeds[:10]:
            print(f"    {tipo}  {href}")
    else:
        print("  Sin feeds declarados en la cabecera.")

    # Rutas habituales, probadas de verdad
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    encontradas = []
    for ruta in CANDIDATAS:
        prueba = url.rstrip("/") + ruta if ruta.startswith("?") else urljoin(base, ruta)
        try:
            p = requests.get(prueba, headers=CABECERAS, timeout=15)
        except Exception:
            continue
        tipo = p.headers.get("content-type", "")
        if p.status_code == 200 and len(p.text) > 200 and "html" not in tipo:
            encontradas.append((prueba, tipo, len(p.text)))
    if encontradas:
        print("  Rutas de datos que responden")
        for prueba, tipo, largo in encontradas:
            print(f"    {prueba}  ({tipo}, {largo} caracteres)")

    # Estructura, para orientar el parser
    horas = len(RE_HORA.findall(texto))
    print(f"  Se ven {horas} expresiones de hora en el texto.")
    for etiqueta in ("h1", "h2", "h3"):
        titulos = [
            " ".join(t.get_text(" ", strip=True).split())
            for t in sopa.find_all(etiqueta)
        ]
        titulos = [t for t in titulos if t][:6]
        if titulos:
            print(f"  Primeros {etiqueta}")
            for t in titulos:
                print(f"    {t[:95]}")
    print(f"  HTML guardado en {destino}\n")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for url in argv:
        inspeccionar(url.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
