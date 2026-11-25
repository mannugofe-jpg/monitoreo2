"""Agenda de la Comision Ejecutiva Federal del PSOE."""
from ._psoe_comun import BASE, PSOEBase, dia_mes

class PSOECEF(PSOEBase):
    clave = 'psoe_cef'
    nombre = 'PSOE - Comisión Ejecutiva Federal'
    modalidad = 'cef'

    def urls(self, fecha):
        return [f'{BASE}previsiones-cef-{dia_mes(fecha)}-de-{fecha.year}/']
