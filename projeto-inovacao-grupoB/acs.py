#!/usr/bin/env python3
"""
Ponto de entrada do projeto. Rode a partir desta pasta:

    python3 acs.py <comando> [opções]        (no Windows: python acs.py ...)

Comandos:

    assistente ARQUIVO.toml        escreve regras respondendo perguntas
    compilar ARQUIVO.toml [...]    gera o domínio (e o problema) PDDL com as regras
    planejar [ARQUIVO.toml] [...]  planeja o turno e imprime o roteiro do ACS
    testes                         roda os testes automáticos

    equivalencia                   regras sintéticas x domínio estendido do Ciclo 2
    medicoes [--rapido]            medições da avaliação
    qualidade [--rapido]           qualidade dos planos (precisa do Fast Downward)
    roteiros ROTEIRO PLANILHA r1…  confere um roteiro contra as regras da avaliação
    conferir-teste SESSAO.toml …   confere uma regra do teste com usuários

`python3 acs.py <comando> --help` mostra as opções de cada um. O código fica
em backend/; veja HOWTORUN.md.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(f"Este projeto precisa do Python 3.11 ou superior "
             f"(este é o {sys.version.split()[0]}).")

BACKEND = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND))

# Comandos que rodam um script de avaliacao em backend/testes/.
SCRIPTS = {
    "equivalencia": "testes.equivalencia",
    "medicoes": "testes.medicoes",
    "qualidade": "testes.qualidade_planos",
    "roteiros": "testes.roteiros_avaliacao",
    "conferir-teste": "testes.teste_usuario",
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "ajuda"):
        print(__doc__.strip())
        return 0
    comando, resto = argv[0], argv[1:]

    if comando in ("assistente", "planejar"):
        from compilador.__main__ import main as compilador
        return compilador([comando, *resto])
    if comando == "compilar":
        from compilador.__main__ import main as compilador
        return compilador(resto)
    if comando == "testes":
        import unittest
        programa = unittest.main(module=None, exit=False, argv=[
            "acs.py testes", "discover", "-s", str(BACKEND / "testes"),
            "-t", str(BACKEND), *resto])
        return 0 if programa.result.wasSuccessful() else 1
    if comando in SCRIPTS:
        sys.argv = [f"acs.py {comando}", *resto]
        try:
            runpy.run_module(SCRIPTS[comando], run_name="__main__")
        except SystemExit as saida:
            return saida.code if isinstance(saida.code, int) else 0
        return 0

    print(f"Comando desconhecido: {comando}. Comandos: assistente, compilar, planejar, "
          f"testes, {', '.join(SCRIPTS)}. Veja: python3 acs.py --help", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
