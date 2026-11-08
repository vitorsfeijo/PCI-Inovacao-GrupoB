"""
Ponte para a base do Ciclo 2, copiada para dentro deste projeto.

A pasta `acsplan/`, ao lado de `compilador/`, e uma copia parcial e SEM
ALTERACOES do pacote do Ciclo 2 (ver acsplan/LEIAME.md). Assim o projeto
funciona sozinho, sem depender da pasta PCI-Saude-GroupB. O compilador le o
dominio legal dessa copia e reaproveita dela o parser PDDL, o planejador, o
gerador de problema, o roteirizador e a selecao de pacientes. Tudo o que
depende desses caminhos fica aqui.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Pasta do projeto: contem compilador/ e a copia acsplan/.
RAIZ = Path(__file__).resolve().parents[1]
BASE = RAIZ / "acsplan"
DOMINIOS = BASE / "logica" / "dominios"
DOMINIO_LEGAL = DOMINIOS / "dominio-legal.pddl"
DOMINIO_ESTENDIDO = DOMINIOS / "dominio-estendido.pddl"
PLANILHA_EXEMPLO = BASE / "dados" / "microarea_exemplo.csv"


def garantir_caminho() -> None:
    """Poe a pasta do projeto no inicio do caminho de importacao, para que
    `import acsplan` encontre a copia local mesmo fora desta pasta."""
    if not sys.path or sys.path[0] != str(RAIZ):
        if str(RAIZ) in sys.path:
            sys.path.remove(str(RAIZ))
        sys.path.insert(0, str(RAIZ))


def planejador():
    """Importa e devolve o modulo `acsplan.logica.planejador` da copia local."""
    garantir_caminho()
    from acsplan.logica import planejador as modulo
    return modulo


def ler_dados(caminho: str) -> dict:
    """Le a planilha (.csv) ou o .json de pacientes com o carregador do Ciclo 2."""
    from .regras import ErroRegra
    garantir_caminho()
    from acsplan.dados import carregador
    try:
        return carregador.carregar(caminho)
    except FileNotFoundError:
        raise ErroRegra(f"o arquivo {caminho} não foi encontrado") from None
    except Exception as erro:              # erros de formato do carregador do Ciclo 2
        raise ErroRegra(f"não foi possível ler os dados de {caminho}: {erro}") from None
