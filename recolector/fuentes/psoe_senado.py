"""Agenda socialista del Senado. Sabado y domingo comparten pagina."""
import datetime as dt
from ._psoe_comun import BASE, PSOEBase, dia_completo, dia_mes

class PSOESenado(PSOEBase):
    clave = 'psoe_senado'
    nombre = 'PSOE - Senado'
    modalidad = 'senado'

    def fechas_pagina(self, fecha):
        if fecha.weekday() < 5:
            return (fecha,)
        sabado = fecha - dt.timedelta(days=fecha.weekday()-5)
        return sabado, sabado + dt.timedelta(days=1)

    def urls(self, fecha):
        fechas = self.fechas_pagina(fecha)
        raiz = BASE + 'senado-previsiones-para-el-'
        if len(fechas)==1:
            return [f'{raiz}{dia_completo(fecha)}-2/']
        s,d = fechas
        if s.month == d.month:
            return [f'{raiz}sabado-{s.day}-y-domingo-{dia_mes(d)}/']
        # Variante inferida para fines de semana entre dos meses.
        return [f'{raiz}sabado-{dia_mes(s)}-y-domingo-{dia_mes(d)}/']
