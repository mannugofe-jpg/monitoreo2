"""Agenda del Grupo Parlamentario Socialista en el Congreso."""
from ._psoe_comun import BASE, PSOEBase, dia_completo

class PSOECongreso(PSOEBase):
    clave = "psoe_congreso"
    nombre = "PSOE - Congreso"
    modalidad = "congreso"

    def urls(self, fecha):
        return [f"{BASE}congreso-previsiones-para-el-{dia_completo(fecha)}-de-{fecha.year}/"]
