from .base import Fuente
from .acn import ACN
from .ajbcn import AjuntamentBCN
from .diba import DIBA
from .generalitat import Generalitat
from .infobae_efe import InfobaeEFE
from .moncloa import Moncloa
from .parlament import Parlament
from .pp import PP

# Añade aquí cada fuente nueva y quedará incluida en la recolección
FUENTES: dict[str, type[Fuente]] = {
    Moncloa.clave: Moncloa,
    Generalitat.clave: Generalitat,
    Parlament.clave: Parlament,
    ACN.clave: ACN,
    InfobaeEFE.clave: InfobaeEFE,
    AjuntamentBCN.clave: AjuntamentBCN,
    DIBA.clave: DIBA,
    PP.clave: PP,
}

__all__ = [
    "Fuente", "Moncloa", "Generalitat", "Parlament", "ACN", "AjuntamentBCN",
    "DIBA", "PP", "InfobaeEFE", "FUENTES",
]
