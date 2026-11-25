"""Previsiones generales del PSOE: tres variantes de URL por fecha."""
from ._psoe_comun import BASE, PSOEBase, dia_completo

class PSOEGeneral(PSOEBase):
    clave = 'psoe_general'
    nombre = 'PSOE - Previsiones generales'
    modalidad = 'general'

    def urls(self, fecha):
        raiz = BASE + 'previsiones-' + dia_completo(fecha)
        return [f'{raiz}/', f'{raiz}-{fecha.year}/', f'{raiz}-de-{fecha.year}/']
