"""Prueba del parser de La Moncloa contra una copia local de la página."""
import datetime as dt
from pathlib import Path

from recolector.fuentes.moncloa import Moncloa

FIXTURE = Path(__file__).parent / "fixture_moncloa.html"


def test_parsea_actos():
    actos = Moncloa().parsear(
        FIXTURE.read_text(encoding="utf-8"), dt.date(2025, 10, 22), "http://x"
    )
    assert len(actos) == 5
    primero = actos[0]
    assert primero.hora == "09:00"
    assert primero.persona == "Pedro Sánchez"
    assert primero.cargo == "Presidente del Gobierno"
    # Un acto sin hora tambien se recoge
    assert any(a.hora is None for a in actos)
    # El lugar se extrae del texto libre
    assert any(a.lugar and "Moncloa" in a.lugar for a in actos)
    # El id no depende de la hora
    assert primero.id == primero.calcular_id()


def test_acn_y_ajbcn():
    import datetime as dt
    from recolector.fuentes.acn import ACN
    from recolector.fuentes.ajbcn import AjuntamentBCN

    base = Path(__file__).parent
    acn = ACN().parsear(
        (base / "fixture_acn.html").read_text(encoding="utf-8"), dt.date(2026, 6, 1)
    )
    assert len(acn) == 4
    assert acn[0].fecha == "2026-06-04"
    assert acn[1].hora == "09:00" and acn[1].lugar == "Barcelona"

    bcn = AjuntamentBCN().parsear(
        (base / "fixture_ajbcn.html").read_text(encoding="utf-8"),
        dt.date(2026, 11, 25),
        "x",
    )
    assert len(bcn) == 2
    assert bcn[0].fecha == "2026-11-25" and bcn[0].hora == "18:30"
    assert bcn[1].fecha == "2026-11-26"


def test_filtro_tematico():
    import datetime as dt
    from recolector.fuentes.acn import ACN
    from recolector.filtros import Clasificador

    c = Clasificador()
    actos = ACN().parsear(
        (Path(__file__).parent / "fixture_acn.html").read_text(encoding="utf-8"),
        dt.date(2026, 6, 1),
    )
    for a in actos:
        c.clasificar(a)
    relevantes = [a for a in actos if a.relevante]
    assert len(relevantes) == 3
    assert any("residuos" in a.temas for a in relevantes)
    assert any("agua" in a.temas for a in relevantes)
