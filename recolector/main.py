"""Punto de entrada. Recolecta, fusiona y escribe los datos de la web.

Uso habitual
    python -m recolector.main --dias-adelante 10 --dias-atras 1
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from .almacen import Almacen
from .filtros import Clasificador
from .fuentes import FUENTES

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "docs" / "datos"


def rango_fechas(atras: int, adelante: int) -> list[dt.date]:
    hoy = dt.date.today()
    return [hoy + dt.timedelta(days=d) for d in range(-atras, adelante + 1)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Recolector de agendas institucionales")
    p.add_argument("--dias-adelante", type=int, default=10)
    p.add_argument("--dias-atras", type=int, default=1)
    p.add_argument("--fuente", action="append", help="limita a una fuente concreta")
    p.add_argument("--datos", default=str(DATOS))
    p.add_argument("--purgar-dias", type=int, default=60)
    p.add_argument("--config", default=None)
    p.add_argument("--solo-reclasificar", action="store_true",
                   help="aplica los filtros de config.yaml a lo ya guardado "
                        "y no visita ninguna web")
    args = p.parse_args(argv)

    clasificador = Clasificador(args.config) if args.config else Clasificador()

    if args.solo_reclasificar:
        almacen = Almacen(Path(args.datos))
        tocados = almacen.reclasificar(clasificador)
        print(f"Reclasificados {tocados} actos con la configuración actual.")
        return 0

    activas = [c for c in clasificador.claves_activas() if c in FUENTES]
    claves = args.fuente or activas or list(FUENTES)
    desconocidas = [c for c in claves if c not in FUENTES]
    if desconocidas:
        print(f"Fuentes desconocidas {desconocidas}. Disponibles {list(FUENTES)}")
        return 2

    fechas = rango_fechas(args.dias_atras, args.dias_adelante)
    print(f"Recolectando {len(fechas)} días desde {fechas[0]} hasta {fechas[-1]}")

    recolectados = []
    ambito: set[tuple[str, str]] = set()

    for clave in claves:
        fuente = FUENTES[clave]()
        print(f"- {fuente.nombre}")
        actos = fuente.recolectar(fechas)
        for acto in actos:
            clasificador.clasificar(acto)
        relevantes = sum(1 for a in actos if a.relevante)
        print(f"  {relevantes} de {len(actos)} pasan el filtro de la fuente")
        recolectados.extend(actos)
        ambito.update((clave, d) for d in fuente.ambito_fechas(fechas, actos))

    almacen = Almacen(Path(args.datos))
    cambios = almacen.fusionar(recolectados, ambito)
    if args.purgar_dias:
        almacen.purgar(args.purgar_dias)

    # Lo guardado de días anteriores conserva la clasificación con la que se
    # leyó. Se repasa entero para que un cambio en config.yaml se note en
    # todo, y no solo en lo que se acaba de recoger
    tocados = almacen.reclasificar(clasificador)
    if tocados:
        print(f"Reclasificados {tocados} actos con la configuración actual.")

    altas = sum(1 for c in cambios if c["tipo"] == "alta")
    mods = sum(1 for c in cambios if c["tipo"] == "modificacion")
    bajas = sum(1 for c in cambios if c["tipo"] == "baja")
    print(f"Resultado. {len(recolectados)} actos leídos, {altas} altas, "
          f"{mods} modificaciones, {bajas} bajas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
