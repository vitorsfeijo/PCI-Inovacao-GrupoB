"""
Linha de comando do compilador.

    python -m compilador exemplos/higienizacao.toml -o dominio-com-regras.pddl

Sem -o, o dominio e escrito na saida padrao.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ciclo2
from .dominio import compilar_dominio
from .pddl import escrever_dominio
from .regras import ErroRegra, carregar_regras


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m compilador",
        description="Aplica regras escritas em TOML sobre o dominio PDDL do ACS.")
    parser.add_argument("regras", help="arquivo .toml com as regras")
    parser.add_argument("--dominio", default=str(ciclo2.DOMINIO_LEGAL),
                        help="dominio de entrada (padrao: dominio legal do Ciclo 2)")
    parser.add_argument("-o", "--saida", help="arquivo .pddl de saida")
    parser.add_argument("--nome", default="visita-domiciliar-acs-regras",
                        help="nome do dominio gerado")
    args = parser.parse_args(argv)

    try:
        regras = carregar_regras(args.regras)
        arvore = ciclo2.planejador().ler_sexp(args.dominio)
        compilado = compilar_dominio(arvore, regras, nome=args.nome)
    except ErroRegra as erro:
        print(f"Erro na regra: {erro}", file=sys.stderr)
        return 1

    cabecalho = [
        "ARQUIVO GERADO pelo compilador de regras. Nao editar a mao.",
        f"Dominio de entrada: {Path(args.dominio).name}",
        f"Regras: {Path(args.regras).name}",
        f"  recursos: {', '.join(r.nome for r in regras.recursos) or '-'}",
        f"  preparos: {', '.join(p.nome for p in regras.preparos) or '-'}",
    ]
    texto = escrever_dominio(compilado, cabecalho)

    if args.saida:
        Path(args.saida).write_text(texto, encoding="utf-8")
        print(f"Dominio gravado em {args.saida}", file=sys.stderr)
    else:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
