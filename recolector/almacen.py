"""Fusiona lo recién recolectado con lo que ya había y detecta cambios.

La regla importante es que solo se reconcilian los pares de fuente y día
que se han visitado en esta pasada. Si un día no se ha visitado, sus
actos se dejan intactos, para no marcar como cancelado lo que
simplemente no se ha mirado.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .modelo import Acto, clave_orden

MAX_CAMBIOS = 500


def _ahora() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Almacen:
    def __init__(self, ruta_datos: Path) -> None:
        self.ruta_datos = Path(ruta_datos)
        self.ruta_actos = self.ruta_datos / "actos.json"
        self.ruta_cambios = self.ruta_datos / "cambios.json"
        self.ruta_datos.mkdir(parents=True, exist_ok=True)

    def cargar(self) -> dict[str, Acto]:
        if not self.ruta_actos.exists():
            return {}
        bruto = json.loads(self.ruta_actos.read_text(encoding="utf-8"))
        return {a["id"]: Acto.desde_dict(a) for a in bruto.get("actos", [])}

    def cargar_cambios(self) -> list[dict]:
        if not self.ruta_cambios.exists():
            return []
        return json.loads(self.ruta_cambios.read_text(encoding="utf-8"))

    def fusionar(
        self,
        recolectados: list[Acto],
        ambito: set[tuple[str, str]],
    ) -> list[dict]:
        """Devuelve la lista de cambios detectados en esta pasada."""
        previos = self.cargar()
        momento = _ahora()
        cambios: list[dict] = []

        nuevos_por_id = {a.id: a for a in recolectados}

        for acto in recolectados:
            anterior = previos.get(acto.id)
            if anterior is None:
                acto.estado = "nuevo"
                acto.visto_primera_vez = momento
                acto.visto_ultima_vez = momento
                previos[acto.id] = acto
                cambios.append(self._cambio("alta", momento, acto))
                continue

            if anterior.huella() != acto.huella():
                cambios.append(
                    self._cambio(
                        "modificacion",
                        momento,
                        acto,
                        antes={"hora": anterior.hora, "lugar": anterior.lugar},
                        despues={"hora": acto.hora, "lugar": acto.lugar},
                    )
                )
                anterior.hora = acto.hora
                anterior.lugar = acto.lugar
                anterior.notas = acto.notas
                anterior.estado = "modificado"
            elif anterior.estado == "cancelado":
                anterior.estado = "modificado"
                cambios.append(self._cambio("recuperacion", momento, acto))
            else:
                anterior.estado = "vigente"

            anterior.cargo = acto.cargo or anterior.cargo
            anterior.visto_ultima_vez = momento

        # Bajas, solo dentro del ámbito recolectado
        for acto in previos.values():
            if (acto.fuente, acto.fecha) not in ambito:
                continue
            if acto.id in nuevos_por_id:
                continue
            if acto.estado == "cancelado":
                continue
            acto.estado = "cancelado"
            cambios.append(self._cambio("baja", momento, acto))

        self._guardar(list(previos.values()), momento)
        self._guardar_cambios(cambios)
        return cambios

    def _cambio(self, tipo, momento, acto, antes=None, despues=None) -> dict:
        registro = {
            "tipo": tipo,
            "momento": momento,
            "id": acto.id,
            "fuente": acto.fuente,
            "fecha": acto.fecha,
            "hora": acto.hora,
            "persona": acto.persona,
            "titulo": acto.titulo,
        }
        if antes is not None:
            registro["antes"] = antes
            registro["despues"] = despues
        return registro

    def _guardar(self, actos: list[Acto], momento: str) -> None:
        actos.sort(key=clave_orden)
        contenido = {
            "generado": momento,
            "total": len(actos),
            "actos": [a.a_dict() for a in actos],
        }
        self.ruta_actos.write_text(
            json.dumps(contenido, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def _guardar_cambios(self, nuevos: list[dict]) -> None:
        historico = nuevos + self.cargar_cambios()
        self.ruta_cambios.write_text(
            json.dumps(historico[:MAX_CAMBIOS], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def purgar(self, dias_atras: int = 60) -> None:
        """Elimina actos muy antiguos para que el fichero no crezca sin fin."""
        limite = (dt.date.today() - dt.timedelta(days=dias_atras)).isoformat()
        actos = [a for a in self.cargar().values() if a.fecha >= limite]
        self._guardar(actos, _ahora())
