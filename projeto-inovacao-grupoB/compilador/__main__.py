"""
Linha de comando do compilador.

    # so o dominio
    python -m compilador exemplos/higienizacao.toml -o dominio.pddl

    # dominio e problema (o problema de entrada e um problema do dominio legal)
    python -m compilador exemplos/higienizacao.toml -o dominio.pddl \\
        --problema problema-legal.pddl --saida-problema problema.pddl

Sem -o, o dominio e escrito na saida padrao.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ciclo2
from .dominio import NOME_PADRAO, compilar_dominio
from .pddl import escrever_pddl
from .problema import compilar_problema
from .regras import ErroRegra, carregar_regras


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m compilador",
        description="Aplica regras escritas em TOML sobre o dominio PDDL do ACS.")
    parser.add_argument("regras", help="arquivo .toml com as regras")
    parser.add_argument("--dominio", default=str(ciclo2.DOMINIO_LEGAL),
                        help="dominio de entrada (padrao: dominio legal do Ciclo 2)")
    parser.add_argument("-o", "--saida", help="arquivo .pddl de saida do dominio")
    parser.add_argument("--nome", default=NOME_PADRAO,
                        help=f"nome do dominio gerado (padrao: {NOME_PADRAO})")
    parser.add_argument("--problema",
                        help="problema de entrada, gerado para o dominio legal")
    parser.add_argument("--saida-problema",
                        help="arquivo .pddl de saida do problema")
    args = parser.parse_args(argv)

    if bool(args.problema) != bool(args.saida_problema):
        parser.error("--problema e --saida-problema devem ser usados juntos")

    ler = ciclo2.planejador().ler_sexp
    try:
        regras = carregar_regras(args.regras)
        dominio = compilar_dominio(ler(args.dominio), regras, nome=args.nome)
        problema = (compilar_problema(ler(args.problema), regras, nome_dominio=args.nome)
                    if args.problema else None)
    except ErroRegra as erro:
        print(f"Erro na regra: {erro}", file=sys.stderr)
        return 1

    resumo = [
        f"Regras: {Path(args.regras).name}",
        f"  recursos: {', '.join(r.nome for r in regras.recursos) or '-'}",
        f"  preparos: {', '.join(p.nome for p in regras.preparos) or '-'}",
    ]
    aviso = "ARQUIVO GERADO pelo compilador de regras. Nao editar a mao."
    texto_dominio = escrever_pddl(
        dominio, [aviso, f"Dominio de entrada: {Path(args.dominio).name}", *resumo])

    if args.saida:
        Path(args.saida).write_text(texto_dominio, encoding="utf-8")
        print(f"Dominio gravado em {args.saida}", file=sys.stderr)
    else:
        sys.stdout.write(texto_dominio)

    if problema is not None:
        texto_problema = escrever_pddl(
            problema, [aviso, f"Problema de entrada: {Path(args.problema).name}", *resumo])
        Path(args.saida_problema).write_text(texto_problema, encoding="utf-8")
        print(f"Problema gravado em {args.saida_problema}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
