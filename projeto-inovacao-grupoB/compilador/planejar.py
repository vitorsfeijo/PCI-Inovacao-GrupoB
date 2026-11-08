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

from . import ciclo2, fastdownward, roteiro
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
    "auto": "ótimo se terminar na metade do limite; senão, um plano bom",
    "astar-hmax": "só o ótimo (Ciclo 2: h_max; Fast Downward: LM-cut)",
    "astar-hadd": "plano bom e rápido (Ciclo 2: h_add; Fast Downward: LAMA)",
    "gbfs": "o primeiro plano (Ciclo 2: busca gulosa; Fast Downward: LAMA, 1º plano)",
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
    p.add_argument("--planejador", choices=["auto", "fast-downward", "ciclo2"],
                   default="auto",
                   help="auto: Fast Downward se estiver instalado, senão o do Ciclo 2")
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


# Estrategia -> configuracao do Fast Downward com o mesmo papel.
FD_POR_ESTRATEGIA = {
    "astar-hmax": fastdownward.OTIMO,    # A* com LM-cut: otimo
    "astar-hadd": fastdownward.BOM,      # LAMA: rapido e continua melhorando
    "gbfs": fastdownward.PRIMEIRO,       # LAMA: primeiro plano
}


def _escolher_planejador(escolha: str) -> bool | None:
    """True: Fast Downward; False: planejador do Ciclo 2; None: erro."""
    if escolha == "ciclo2":
        return False
    if fastdownward.disponivel():
        return True
    if escolha == "fast-downward":
        _info(f"Erro: o Fast Downward não está instalado neste Python. Instale com: "
              f"{fastdownward.INSTALACAO}")
        return None
    _info(f"    (Fast Downward não instalado: usando o planejador do Ciclo 2, que não "
          f"escala com muitas regras; {fastdownward.INSTALACAO} acelera)")
    return False


def _buscar(planejador, tarefa, estrategia: str, limite: float, usar_fd: bool,
            caminhos: tuple[str, str]):
    """Devolve (resultado, configuracao usada, se o plano e garantidamente otimo)."""
    def rodar(configuracao: str, segundos: float):
        if usar_fd:
            return fastdownward.resolver(*caminhos, tarefa, configuracao=configuracao,
                                         limite_segundos=segundos)
        return planejador.resolver(tarefa, configuracao, limite_segundos=segundos)

    otima = fastdownward.OTIMO if usar_fd else "astar-hmax"
    if estrategia != "auto":
        configuracao = FD_POR_ESTRATEGIA[estrategia] if usar_fd else estrategia
        return rodar(configuracao, limite), configuracao, configuracao == otima
    resultado = rodar(otima, limite / 2)
    if resultado.sucesso or not _interrompida(resultado.motivo):
        return resultado, otima, True          # plano otimo, ou impossibilidade provada
    boa = fastdownward.BOM if usar_fd else "astar-hadd"
    _info(f"    {otima} não terminou em {limite / 2:g} s; buscando com {boa} "
          f"(o plano pode não ser ótimo)")
    return rodar(boa, limite / 2), boa, False


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
    usar_fd = _escolher_planejador(args.planejador)
    if usar_fd is None:
        return 1
    with tempfile.TemporaryDirectory() as temporaria:
        pasta = Path(args.salvar_pddl) if args.salvar_pddl else Path(temporaria)
        pasta.mkdir(parents=True, exist_ok=True)
        caminhos = (str(pasta / "dominio.pddl"), str(pasta / "problema.pddl"))
        Path(caminhos[0]).write_text(
            escrever_pddl(dominio, ["ARQUIVO GERADO por python -m compilador planejar.",
                                    f"Regras: {args.regras or '-'}"]),
            encoding="utf-8")
        try:
            gerar_problema_com_regras(dados, roteamento, regras, caminhos[1],
                                      nome_dominio=NOME_PADRAO)
        except ErroRegra as erro:
            for problema in erro.problemas:
                _info(f"Erro: {problema}")
            return 1
        inicio = time.perf_counter()
        tarefa = TarefaPlanejamentoPodada(planejador.carregar_dominio(caminhos[0]),
                                          planejador.carregar_problema(caminhos[1]))
        segundos_instanciacao = time.perf_counter() - inicio
        if args.salvar_pddl:
            _info(f"    domínio e problema gravados em {args.salvar_pddl}{os.sep}")

        _info(f"[3] Instanciação: {len(tarefa.acoes)} ações em {segundos_instanciacao:.1f} s")
        nome_planejador = "Fast Downward" if usar_fd else "planejador do Ciclo 2"
        _info(f"    Busca: {nome_planejador}, {ESTRATEGIAS[args.estrategia]}, "
              f"limite de {args.limite:g} s")
        try:
            resultado, usada, otimo = _buscar(planejador, tarefa, args.estrategia,
                                              args.limite, usar_fd, caminhos)
        except RuntimeError as erro:
            _info(f"Erro: {erro}")
            return 1

    if not resultado.sucesso:
        _info("")
        if _interrompida(resultado.motivo):
            _info("Não foi possível montar o roteiro: a busca parou no limite antes de "
                  "encontrar um plano. Isso NÃO mostra que o turno é impossível.")
            _info(f"Motivo informado pelo planejador: {resultado.motivo}")
            dica = ("" if usar_fd else
                    f"; instalar o Fast Downward ({fastdownward.INSTALACAO}) costuma resolver")
            _info(f"Tente um --limite maior ou menos pacientes (--max-pacientes){dica}.")
        else:
            _info("Não foi possível montar o roteiro: nenhuma sequência de ações cumpre "
                  "as regras neste turno.")
            _info(f"Motivo informado pelo planejador: {resultado.motivo}")
            _info("Reveja a seleção de pacientes, os recursos ou as regras.")
        return 1
    garantia = "ótimo" if otimo else "sem garantia de ser ótimo"
    _info(f"[4] Plano: {resultado.tamanho} ações, {resultado.custo} min "
          f"({resultado.segundos:.1f} s, {usada}, {garantia})")

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
