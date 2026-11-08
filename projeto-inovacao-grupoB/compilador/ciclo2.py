"""
Ponte para o codigo do Ciclo 2 (pasta PCI-Saude-GroupB na raiz do repositorio).

O compilador nao copia nada do Ciclo 2: le o dominio legal de la e reaproveita
o parser PDDL do planejador. Tudo o que depende desse caminho fica aqui.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ_CICLO2 = Path(__file__).resolve().parents[2] / "PCI-Saude-GroupB"
DOMINIOS = RAIZ_CICLO2 / "acsplan" / "logica" / "dominios"
DOMINIO_LEGAL = DOMINIOS / "dominio-legal.pddl"
DOMINIO_ESTENDIDO = DOMINIOS / "dominio-estendido.pddl"


def planejador():
    """Importa e devolve o modulo `acsplan.logica.planejador` do Ciclo 2."""
    if str(RAIZ_CICLO2) not in sys.path:
        sys.path.insert(0, str(RAIZ_CICLO2))
    from acsplan.logica import planejador as modulo
    return modulo
