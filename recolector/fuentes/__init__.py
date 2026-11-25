from .base import Fuente
from .acn import ACN
from .ajbcn import AjuntamentBCN
from .moncloa import Moncloa

# Añade aquí cada fuente nueva y quedará incluida en la recolección
FUENTES: dict[str, type[Fuente]] = {
    Moncloa.clave: Moncloa,
    ACN.clave: ACN,
    AjuntamentBCN.clave: AjuntamentBCN,
}

__all__ = ["Fuente", "Moncloa", "ACN", "AjuntamentBCN", "FUENTES"]
