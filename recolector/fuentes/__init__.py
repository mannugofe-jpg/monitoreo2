from .base import Fuente
from .acn import ACN
from .ajbcn import AjuntamentBCN
from .generalitat import Generalitat
from .moncloa import Moncloa
from .pp import PP

# Añade aquí cada fuente nueva y quedará incluida en la recolección
FUENTES: dict[str, type[Fuente]] = {
    Moncloa.clave: Moncloa,
    Generalitat.clave: Generalitat,
    ACN.clave: ACN,
    AjuntamentBCN.clave: AjuntamentBCN,
    PP.clave: PP,
}

__all__ = [
    "Fuente", "Moncloa", "Generalitat", "ACN", "AjuntamentBCN", "PP", "FUENTES",
]
