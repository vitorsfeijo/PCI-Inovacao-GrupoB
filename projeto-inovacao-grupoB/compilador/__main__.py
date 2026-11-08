"""
Linha de comando do compilador.

    # so o dominio
    python -m compilador exemplos/higienizacao.toml -o dominio.pddl

    # dominio e problema (o problema de entrada e um problema do dominio legal)
    python -m compilador exemplos/higienizacao.toml -o dominio.pddl \\
        --problema problema-legal.pddl --saida-problema problema.pddl

    # regras com exigencia por paciente: as marcas vem da planilha
    python -m compilador exemplos/sinteticas-ciclo2.toml -o dominio.pddl \\
        --problema problema-legal.pddl --saida-problema problema.pddl \\
        --dados acsplan/dados/microarea_exemplo.csv

Sem -o, o dominio e escrito na saida padrao.

Outros comandos:

    python -m compilador planejar regras.toml    # turno inteiro + roteiro do ACS
    python -m compilador assistente regras.toml  # escreve regras por perguntas
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ciclo2
from .dominio import NOME_PADRAO, compilar_dominio
from .pddl import escrever_pddl
from .problema import compilar_problema, marcas_dos_dados
from .regras import ErroRegra, avisos, carregar_regras


def _ler_pddl(caminho: str) -> list:
    try:
        return ciclo2.planejador().ler_sexp(caminho)
    except FileNotFoundError:
        raise ErroRegra(f"o arquivo {caminho} não foi encontrado") from None
    except SyntaxError as erro:
        raise ErroRegra(f"o arquivo {caminho} não é um PDDL válido ({erro})") from None


def _relatar_erros(caminho: str, problemas: list[str]) -> None:
    if len(problemas) == 1:
        print(f"Não foi possível compilar {caminho}: {problemas[0]}", file=sys.stderr)
        return
    print(f"Não foi possível compilar {caminho}. "
          f"{len(problemas)} problemas encontrados:", file=sys.stderr)
    for numero, problema in enumerate(problemas, start=1):
        print(f"  {numero}. {problema}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "planejar":
        from .planejar import main as planejar
        return planejar(argv[1:])
    if argv and argv[0] == "assistente":
        from .assistente import main as assistente
        return assistente(argv[1:])

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
    parser.add_argument("--dados",
                        help="pacientes (.csv ou .json do Ciclo 2), de onde vem as "
                             "marcas usadas pelas exigencias")
    args = parser.parse_args(argv)

    if bool(args.problema) != bool(args.saida_problema):
        parser.error("--problema e --saida-problema devem ser usados juntos")

    try:
        regras = carregar_regras(args.regras)
        dominio = compilar_dominio(_ler_pddl(args.dominio), regras, nome=args.nome)
        problema = None
        if args.problema:
            marcados = None
            if regras.exigencias and args.dados:
                dados = ciclo2.ler_dados(args.dados,
                                         [e.campo_paciente for e in regras.exigencias])
                marcados = marcas_dos_dados(dados, regras)
            elif regras.exigencias:
                raise ErroRegra("as regras têm exigências por paciente; informe os "
                                "dados dos pacientes com --dados planilha.csv")
            problema = compilar_problema(_ler_pddl(args.problema), regras,
                                         nome_dominio=args.nome, marcados=marcados)
    except ErroRegra as erro:
        _relatar_erros(args.regras, erro.problemas)
        return 1

    for aviso_regra in avisos(regras):
        print(f"Aviso: {aviso_regra}", file=sys.stderr)

    resumo = [
        f"Regras: {Path(args.regras).name}",
        f"  recursos: {', '.join(r.nome for r in regras.recursos) or '-'}",
        f"  preparos: {', '.join(p.nome for p in regras.preparos) or '-'}",
        f"  consumos: {', '.join(f'{c.procedimento}->{c.recurso}' for c in regras.consumos) or '-'}",
        f"  exigencias: {', '.join(e.nome for e in regras.exigencias) or '-'}",
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
