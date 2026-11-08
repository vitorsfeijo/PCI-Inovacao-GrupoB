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

import csv
import sys
from collections.abc import Iterable
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


def ler_dados(caminho: str, colunas_extras: Iterable[str] = ()) -> dict:
    """
    Le a planilha (.csv) ou o .json de pacientes com o carregador do Ciclo 2.

    O leitor de CSV do Ciclo 2 so guarda as colunas que conhece e descarta as
    demais. As marcas usadas por exigencias (ex.: exige_avental) seriam
    perdidas em silencio, entao as `colunas_extras` sao relidas da planilha
    aqui, com a mesma regra de sim/nao do Ciclo 2. A copia do Ciclo 2 nao e
    alterada. As colunas encontradas ficam em dados["_colunas_pacientes"].
    """
    from .regras import ErroRegra
    garantir_caminho()
    from acsplan.dados import carregador
    try:
        dados = carregador.carregar(caminho)
    except FileNotFoundError:
        raise ErroRegra(f"o arquivo {caminho} não foi encontrado") from None
    except Exception as erro:              # erros de formato do carregador do Ciclo 2
        raise ErroRegra(f"não foi possível ler os dados de {caminho}: {erro}") from None

    if not caminho.lower().endswith(".csv"):
        dados["_colunas_pacientes"] = set().union(*(p.keys() for p in dados["pacientes"]))
        return dados

    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        amostra = arquivo.read(4096)
        arquivo.seek(0)
        try:
            dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
        except csv.Error:
            dialeto = csv.excel
        linhas = [{(k or "").strip().lower(): v for k, v in bruto.items()}
                  for bruto in csv.DictReader(arquivo, dialect=dialeto)]
    cabecalho = set(linhas[0]) if linhas else set()
    por_id = {(linha.get("id") or "").strip(): linha for linha in linhas}
    for coluna in set(colunas_extras) & cabecalho:
        for paciente in dados["pacientes"]:
            paciente[coluna] = carregador._booleano(por_id[paciente["id"]].get(coluna))
    dados["_colunas_pacientes"] = cabecalho
    return dados
