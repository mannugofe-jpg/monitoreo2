"""Descarga una URL y guarda el HTML tal cual, para poder inspeccionarlo.

Sirve para dos cosas. Para preparar una fuente nueva, mirando cómo
publica de verdad su agenda, y para diagnosticar un parser que un día
deja de devolver actos.

    python herramientas/volcar.py https://govern.cat/gov/agenda govern.html
"""

import sys
from pathlib import Path

import requests

CABECERAS = {
    "User-Agent": (
        "agenda-institucional/1.0 (proyecto personal de agregación de "
        "agendas públicas; contacto en el repositorio)"
    ),
    "Accept-Language": "ca,es;q=0.9",
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    url = sys.argv[1]
    destino = Path(sys.argv[2] if len(sys.argv) > 2 else "volcado.html")

    r = requests.get(url, headers=CABECERAS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    destino.write_text(r.text, encoding="utf-8")

    print(f"{r.status_code}  {len(r.text)} caracteres  ->  {destino}")
    # Pista rápida sobre si la página se monta con JavaScript
    texto = r.text.lower()
    if len(texto) < 4000 or texto.count("<script") > 30:
        print("Aviso. La página puede montarse con JavaScript. Mira el HTML "
              "y, si el contenido no está, busca en la pestaña de red del "
              "navegador la llamada que trae los datos en JSON.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
