"""
Planejamento do turno com regras, de ponta a ponta, e roteiro para o ACS.

    python -m compilador planejar exemplos/sinteticas-ciclo2.toml
    python -m compilador planejar regras.toml --dados minha-microarea.csv --orcamento 240

Equivale ao `acsplan roteiro` do Ciclo 2, com as regras da equipe aplicadas:

    [1] selecao     quem entra no turno (prioridade e atraso, sob orcamento)
    [2] roteamento  em que ordem visitar
    [3] regras      dominio legal + regras compiladas; problema com os fatos
                    das regras (estoques, marcas dos pacientes); instanciacao
                    com poda (compilador/instanciacao.py)
    [4] plano       busca no espaco de estados (padrao: A* com h_max, otimo)
    [5] limpeza     retira do plano as acoes redundantes (compilador/limpeza.py)
    [6] roteiro     o que o ACS recebe

Sem arquivo de regras, planeja so com o dominio legal. O resumo de cada
passo vai para a saida de erro; o roteiro, para a saida padrao (ou para o
arquivo de --salvar), para poder ser redirecionado sozinho.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

from . import ciclo2, roteiro
from .instanciacao import TarefaPlanejamentoPodada
from .limpeza import eliminar_redundantes
from .dominio import NOME_PADRAO, compilar_dominio
from .pddl import escrever_pddl
from .problema import gerar_problema_com_regras
from .regras import ErroRegra, Regras, avisos, carregar_regras

# Padrao: "auto". A* com h_max e o unico com garantia de plano otimo, mas
# nao termina em turnos realistas com regras (a planilha de exemplo com as
# tres regras sinteticas passa de 60 s). A* com h_add e rapido, mas na
# avaliacao deu turnos 11% mais longos que o otimo sem nenhuma regra, e ate
# 35% com exigencias na porta; a limpeza do plano reduz isso para ~10%.
# "auto" tenta h_max na primeira metade do limite e, se o tempo acabar, usa
# h_add na outra metade, avisando que o plano nao e garantidamente otimo.
ESTRATEGIAS = {
    "auto": "h_max (ótimo); se não terminar na metade do limite, h_add",
    "astar-hmax": "A* com h_max (plano ótimo)",
    "astar-hadd": "A* com h_add (mais rápido, mas o turno pode sair bem mais longo)",
    "gbfs": "busca gulosa (a mais rápida, plano pode ter ações inúteis)",
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
    p.add_argument("--estrategia", choices=list(ESTRATEGIAS), default="auto")
    p.add_argument("--limite", type=float, default=60.0, metavar="S",
                   help="limite de tempo da busca, em segundos")
    p.add_argument("--salvar", metavar="ARQUIVO", help="grava o roteiro em arquivo")
    p.add_argument("--salvar-pddl", metavar="PASTA",
                   help="grava o domínio e o problema compilados nessa pasta")
    p.add_argument("--mostrar-plano", action="store_true",
                   help="lista também o plano completo (já limpo), ação por ação")
    p.add_argument("--sem-limpeza", action="store_true",
                   help="não retira do plano as ações redundantes")
    return p


def _info(texto: str = "") -> None:
    print(texto, file=sys.stderr)


def _buscar(planejador, tarefa, estrategia: str, limite: float):
    """Devolve (resultado, estrategia usada)."""
    if estrategia != "auto":
        return planejador.resolver(tarefa, estrategia, limite_segundos=limite), estrategia
    resultado = planejador.resolver(tarefa, "astar-hmax", limite_segundos=limite / 2)
    if resultado.sucesso or not _interrompida(resultado.motivo):
        return resultado, "astar-hmax"         # plano otimo, ou impossibilidade provada
    _info(f"    h_max não terminou em {limite / 2:g} s; buscando com h_add "
          f"(o plano pode não ser ótimo)")
    return (planejador.resolver(tarefa, "astar-hadd", limite_segundos=limite / 2),
            "astar-hadd")


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
        inicio = time.perf_counter()
        tarefa = TarefaPlanejamentoPodada(
            planejador.carregar_dominio(str(caminho_dominio)),
            planejador.carregar_problema(str(caminho_problema)))
        segundos_instanciacao = time.perf_counter() - inicio
    if args.salvar_pddl:
        _info(f"    domínio e problema gravados em {args.salvar_pddl}{os.sep}")

    _info(f"[3] Instanciação: {len(tarefa.acoes)} ações em {segundos_instanciacao:.1f} s")
    _info(f"    Busca: {ESTRATEGIAS[args.estrategia]}, limite de {args.limite:g} s")
    resultado, usada = _buscar(planejador, tarefa, args.estrategia, args.limite)
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
    garantia = "ótimo" if usada == "astar-hmax" else "sem garantia de ser ótimo"
    _info(f"[4] Plano: {resultado.tamanho} ações, {resultado.custo} min "
          f"({resultado.segundos:.1f} s de busca, {usada}, {garantia})")

    # [5] limpeza do plano
    custos = {acao.assinatura: acao.custo for acao in tarefa.acoes}
    plano = resultado.plano
    if not args.sem_limpeza:
        plano = eliminar_redundantes(tarefa, resultado.plano)
        retiradas = len(resultado.plano) - len(plano)
        if retiradas:
            _info(f"[5] Limpeza: {retiradas} ações redundantes retiradas, "
                  f"{resultado.custo} -> {sum(custos[p] for p in plano)} min")
        else:
            _info("[5] Limpeza: nenhuma ação redundante")
    custo_total = sum(custos[passo] for passo in plano)

    # [6] roteiro
    paradas = roteiro.montar(plano, dados, custos, roteiro.legenda_para(regras))
    texto = roteiro.imprimir(paradas, dados, custo_total=custo_total,
                             orcamento=args.orcamento)
    _info("")
    if args.salvar:
        Path(args.salvar).write_text(texto + "\n", encoding="utf-8")
        _info(f"Roteiro gravado em {args.salvar}")
    else:
        print(texto)

    if args.mostrar_plano:
        print("\nPLANO COMPLETO (representação interna)")
        for numero, passo in enumerate(plano, start=1):
            print(f"  {numero:>3}. {passo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
