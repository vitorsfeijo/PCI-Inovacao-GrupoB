"""
Planejamento do turno com regras, de ponta a ponta, e roteiro para o ACS.

    python -m compilador planejar exemplos/sinteticas-ciclo2.toml
    python -m compilador planejar regras.toml --dados minha-microarea.csv --orcamento 240

Equivale ao `acsplan roteiro` do Ciclo 2, com as regras da equipe aplicadas:

    [1] selecao     quem entra no turno (prioridade e atraso, sob orcamento)
    [2] roteamento  em que ordem visitar
    [3] regras      dominio legal + regras compiladas; problema com os fatos
                    das regras (estoques, marcas dos pacientes)
    [4] plano       busca no espaco de estados
    [5] roteiro     o que o ACS recebe

Sem arquivo de regras, planeja so com o dominio legal. O resumo de cada
passo vai para a saida de erro; o roteiro, para a saida padrao (ou para o
arquivo de --salvar), para poder ser redirecionado sozinho.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from . import ciclo2, roteiro
from .dominio import NOME_PADRAO, compilar_dominio
from .pddl import escrever_pddl
from .problema import gerar_problema_com_regras
from .regras import ErroRegra, Regras, avisos, carregar_regras

ESTRATEGIAS = {
    "astar-hmax": "A* com h_max (ótimo, mais lento)",
    "astar-hadd": "A* com h_add (quase sempre ótimo, mais rápido)",
    "gbfs": "busca gulosa (mais rápida, plano pode ser mais longo)",
}


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m compilador planejar",
        description="Planeja o turno com as regras da equipe e imprime o roteiro do ACS.")
    p.add_argument("regras", nargs="?",
                   help="arquivo .toml com as regras (sem ele, só o domínio legal)")
    p.add_argument("--dados", default=str(ciclo2.PLANILHA_EXEMPLO),
                   help="pacientes (.csv ou .json); padrão: planilha de exemplo")
    p.add_argument("--instancia-sintetica", nargs=2, type=int, metavar=("N", "SEMENTE"),
                   help="usa uma microárea sorteada em vez da planilha")
    p.add_argument("--orcamento", type=int, metavar="MIN",
                   help="orçamento do turno em minutos")
    p.add_argument("--max-pacientes", type=int)
    p.add_argument("--sem-selecao", action="store_true",
                   help="todos os pacientes entram no turno")
    p.add_argument("--sem-precedencia", action="store_true",
                   help="não obriga urgência alta antes de urgência baixa")
    p.add_argument("--metodo", choices=["nn2opt", "ag"], default="ag",
                   help="roteirizador: vizinho mais próximo + 2-opt, ou genético")
    p.add_argument("--distancias", choices=["haversine", "osrm"], default="haversine")
    p.add_argument("--modal", choices=["pe", "carro"], default="pe")
    p.add_argument("--semente", type=int, default=0)
    p.add_argument("--estrategia", choices=list(ESTRATEGIAS), default="astar-hadd")
    p.add_argument("--limite", type=float, default=60.0, metavar="S",
                   help="limite de tempo da busca, em segundos")
    p.add_argument("--salvar", metavar="ARQUIVO", help="grava o roteiro em arquivo")
    p.add_argument("--salvar-pddl", metavar="PASTA",
                   help="grava o domínio e o problema compilados nessa pasta")
    p.add_argument("--mostrar-plano", action="store_true",
                   help="lista também o plano completo, ação por ação")
    return p


def _info(texto: str = "") -> None:
    print(texto, file=sys.stderr)


def _interrompida(motivo: str) -> bool:
    """A busca parou num limite (tempo ou expansoes), sem provar nada? O
    planejador do Ciclo 2 so prova a impossibilidade quando o objetivo e
    inalcancavel na relaxacao ou quando esgota o espaco de estados."""
    return motivo.startswith(("timeout", "limite"))


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    ciclo2.garantir_caminho()
    from acsplan.dados import gerador
    from acsplan.geo import roteirizador
    from acsplan.selecao import politica

    try:
        regras = carregar_regras(args.regras) if args.regras else Regras()
        if args.instancia_sintetica:
            dados = gerador.gerar(*args.instancia_sintetica)
            origem = "instância sintética n={} semente={}".format(*args.instancia_sintetica)
        else:
            dados = ciclo2.ler_dados(args.dados,
                                     [e.campo_paciente for e in regras.exigencias])
            origem = args.dados
        dominio = compilar_dominio(ciclo2.planejador().ler_sexp(str(ciclo2.DOMINIO_LEGAL)),
                                   regras, nome=NOME_PADRAO)
    except ErroRegra as erro:
        for problema in erro.problemas:
            _info(f"Erro: {problema}")
        return 1

    _info(f"Regras: {args.regras or 'nenhuma (só o domínio legal)'}")
    for aviso in avisos(regras) if args.regras else []:
        _info(f"  Aviso: {aviso}")
    _info(f"Pacientes: {origem}")

    # [1] selecao
    dados = politica.selecionar(dados, orcamento_minutos=args.orcamento,
                                maximo_pacientes=args.max_pacientes,
                                ativar=not args.sem_selecao)
    selecao = dados["_selecao"]
    _info(f"[1] Seleção: {len(selecao['selecionados'])} no turno"
          + (f", {len(selecao['adiados'])} adiados" if selecao["adiados"] else ""))

    # [2] roteamento
    roteamento = roteirizador.roteirizar(
        dados, metodo=args.metodo, provedor_distancia=args.distancias,
        modal=args.modal, usar_precedencia=not args.sem_precedencia,
        semente=args.semente, silencioso=True)
    _info(f"[2] Rota: {' -> '.join(roteamento['rota'])}")

    # [3] regras e [4] plano
    planejador = ciclo2.planejador()
    with tempfile.TemporaryDirectory() as temporaria:
        pasta = Path(args.salvar_pddl) if args.salvar_pddl else Path(temporaria)
        pasta.mkdir(parents=True, exist_ok=True)
        caminho_dominio = pasta / "dominio.pddl"
        caminho_problema = pasta / "problema.pddl"
        caminho_dominio.write_text(
            escrever_pddl(dominio, ["ARQUIVO GERADO por python -m compilador planejar.",
                                    f"Regras: {args.regras or '-'}"]),
            encoding="utf-8")
        try:
            gerar_problema_com_regras(dados, roteamento, regras, str(caminho_problema),
                                      nome_dominio=NOME_PADRAO)
        except ErroRegra as erro:
            for problema in erro.problemas:
                _info(f"Erro: {problema}")
            return 1
        tarefa = planejador.TarefaPlanejamento(
            planejador.carregar_dominio(str(caminho_dominio)),
            planejador.carregar_problema(str(caminho_problema)))
    if args.salvar_pddl:
        _info(f"    domínio e problema gravados em {args.salvar_pddl}{os.sep}")

    _info(f"[3] Busca: {ESTRATEGIAS[args.estrategia]}, limite de {args.limite:g} s")
    resultado = planejador.resolver(tarefa, args.estrategia, limite_segundos=args.limite)
    if not resultado.sucesso:
        _info("")
        if _interrompida(resultado.motivo):
            _info("Não foi possível montar o roteiro: a busca parou no limite antes de "
                  "encontrar um plano. Isso NÃO mostra que o turno é impossível.")
            _info(f"Motivo informado pelo planejador: {resultado.motivo}")
            _info("Tente --estrategia gbfs (mais rápida), um --limite maior ou menos "
                  "pacientes (--max-pacientes).")
        else:
            _info("Não foi possível montar o roteiro: nenhuma sequência de ações cumpre "
                  "as regras neste turno.")
            _info(f"Motivo informado pelo planejador: {resultado.motivo}")
            _info("Reveja a seleção de pacientes, os recursos ou as regras.")
        return 1
    _info(f"[4] Plano: {resultado.tamanho} ações, {resultado.custo} min "
          f"({resultado.segundos:.1f} s de busca)")

    # [5] roteiro
    custos = {acao.assinatura: acao.custo for acao in tarefa.acoes}
    paradas = roteiro.montar(resultado.plano, dados, custos, roteiro.legenda_para(regras))
    texto = roteiro.imprimir(paradas, dados, custo_total=resultado.custo,
                             orcamento=args.orcamento)
    _info("")
    if args.salvar:
        Path(args.salvar).write_text(texto + "\n", encoding="utf-8")
        _info(f"Roteiro gravado em {args.salvar}")
    else:
        print(texto)

    if args.mostrar_plano:
        print("\nPLANO COMPLETO (representação interna)")
        for numero, passo in enumerate(resultado.plano, start=1):
            print(f"  {numero:>3}. {passo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
