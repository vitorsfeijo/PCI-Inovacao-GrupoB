"""
Planejamento por janelas: visita por visita, olhando as proximas.

Com muitas regras, achar o plano otimo do turno inteiro nao termina, e o
primeiro plano dos planejadores rapidos pode sair bem mais longo que o otimo
(na avaliacao, de 7% a 45%). Mas a ORDEM das visitas ja vem pronta do
roteirizador, e um turno com poucos pacientes tem plano otimo em segundos.

Daí a decomposicao (horizonte deslizante):

    1. a partir do estado atual (estoques, equipamento vestido, janelas de
       supervisao...), planeja-se de forma OTIMA o atendimento das proximas
       k visitas da rota;
    2. desse plano, executa-se so o trecho ate concluir a PRIMEIRA delas;
    3. a janela avanca uma visita e o processo se repete; a ultima janela
       inclui a volta a UBS.

Olhar k visitas a frente evita a miopia de planejar uma casa por vez: por
exemplo, repor dois materiais numa mesma passagem pela UBS, em vez de voltar
la duas vezes. Cada janela e otima; o turno inteiro nao tem essa garantia.

Beco sem saida: todo estoque pode ser reposto na UBS a partir de qualquer
casa, entao os estoques nao criam impasse. O que nao se repoe sao as janelas
de supervisao. Um plano de janela otimo nunca as desperdica, mas, quando a
busca otima nao termina e a janela usa um plano apenas bom, ele pode acionar
a supervisao a toa e deixar as ultimas visitas sem ela (aconteceu nos testes
sem o Fast Downward). Por isso cada plano de janela passa pela limpeza antes
de ser executado.
"""

from __future__ import annotations

import copy
import tempfile
import time
from pathlib import Path

from . import ciclo2, fastdownward
from .limpeza import eliminar_redundantes
from .pddl import escrever_pddl

ciclo2.garantir_caminho()
from acsplan.logica.planejador import Resultado  # noqa: E402


class _Janela:
    """Resolve uma janela: do estado dado ate os objetivos dados."""

    def __init__(self, tarefa, caminho_problema: str, usar_fd: bool, limite: float):
        self.tarefa = tarefa
        self.usar_fd = usar_fd
        self.limite = limite
        self.problema = ciclo2.planejador().ler_sexp(caminho_problema)
        self.planejador = ciclo2.planejador()

    def resolver(self, estado: frozenset[int], objetivos: list[tuple],
                 caminho_dominio: str) -> Resultado:
        if self.usar_fd:
            return self._fd(estado, objetivos, caminho_dominio)
        sub = copy.copy(self.tarefa)
        sub.estado_inicial = estado
        sub.objetivo_pos = frozenset(self.tarefa._id(f) for f in objetivos)
        sub.objetivo_neg = frozenset()
        resultado = self.planejador.resolver(sub, "astar-hmax", limite_segundos=self.limite)
        if resultado.sucesso or not resultado.motivo.startswith(("timeout", "limite")):
            return resultado
        # sem o Fast Downward, o h_max nao da conta de janelas com muitas regras
        return self.planejador.resolver(sub, "astar-hadd", limite_segundos=self.limite)

    def _fd(self, estado, objetivos, caminho_dominio) -> Resultado:
        """Escreve o problema da janela (estado atual como :init, objetivos da
        janela como :goal) e resolve com o Fast Downward, de forma otima."""
        arvore = copy.deepcopy(self.problema)
        for i, secao in enumerate(arvore):
            if isinstance(secao, list) and secao and secao[0] == ":init":
                custos = [f for f in secao[1:] if isinstance(f, list) and f[0] == "="]
                fatos = [list(self.tarefa._fato_por_id[f]) for f in sorted(estado)]
                arvore[i] = [":init", *fatos, *custos]
            elif isinstance(secao, list) and secao and secao[0] == ":goal":
                arvore[i] = [":goal", ["and", *[list(f) for f in objetivos]]]
        with tempfile.TemporaryDirectory() as pasta:
            caminho = str(Path(pasta) / "janela.pddl")
            Path(caminho).write_text(escrever_pddl(arvore, ["janela"]), encoding="utf-8")
            sub = copy.copy(self.tarefa)
            sub.estado_inicial = estado
            sub.objetivo_pos = frozenset(self.tarefa._id(f) for f in objetivos)
            sub.objetivo_neg = frozenset()
            resultado = fastdownward.resolver(caminho_dominio, caminho, sub,
                                              configuracao=fastdownward.OTIMO,
                                              limite_segundos=self.limite)
            if resultado.sucesso or not resultado.motivo.startswith(("timeout", "limite")):
                return resultado
            # janela grande demais para o otimo no limite: um plano bom serve
            return fastdownward.resolver(caminho_dominio, caminho, sub,
                                         configuracao=fastdownward.BOM,
                                         limite_segundos=self.limite)


def planejar_por_janelas(tarefa, caminho_dominio: str, caminho_problema: str,
                         rota: list[str], agente: str, *, tamanho: int = 3,
                         usar_fd: bool | None = None, limite_janela: float = 30.0
                         ) -> Resultado:
    """
    Plano do turno por horizonte deslizante. `rota` e a ordem das visitas
    (ids dos pacientes, sem a UBS); `tamanho` e quantas visitas cada janela
    enxerga.
    """
    if usar_fd is None:
        usar_fd = fastdownward.disponivel()
    janela = _Janela(tarefa, caminho_problema, usar_fd, limite_janela)
    por_nome = {acao.assinatura: acao for acao in tarefa.acoes}
    inicio = time.perf_counter()

    estado, plano, custo = tarefa.estado_inicial, [], 0
    for i, paciente in enumerate(rota):
        objetivos = [("protocolo-cumprido", p) for p in rota[i:i + tamanho]]
        ultima = i + tamanho >= len(rota)
        if ultima:
            objetivos.append(("em", agente, "ubs-fim"))
        resultado = janela.resolver(estado, objetivos, caminho_dominio)
        if not resultado.sucesso:
            resultado.segundos = time.perf_counter() - inicio
            resultado.motivo = f"janela da visita {paciente}: {resultado.motivo}"
            return resultado
        # limpa o plano da janela ANTES de executar: um plano nao otimo (quando
        # a busca otima nao termina) pode acionar a supervisao a toa, e as
        # janelas de supervisao, que nao se repoem, fariam falta nas ultimas
        # visitas
        sub = copy.copy(tarefa)
        sub.estado_inicial = estado
        sub.objetivo_pos = frozenset(tarefa._id(f) for f in objetivos)
        sub.objetivo_neg = frozenset()
        passos = eliminar_redundantes(sub, resultado.plano)
        # executa o plano da janela; na ultima, tudo; nas outras, ate concluir
        # o paciente da vez
        meta = tarefa._id(("protocolo-cumprido", paciente))
        for passo in passos:
            acao = por_nome[passo]
            estado = (estado - acao.remocoes) | acao.adicoes
            plano.append(passo)
            custo += acao.custo
            if not ultima and meta in estado:
                break
        if ultima:
            break
    if not tarefa.e_objetivo(estado):
        return Resultado(False, [], 0, 0, 0, time.perf_counter() - inicio,
                         "planejamento por janelas terminou sem atingir o objetivo")
    return Resultado(True, plano, custo, 0, 0, time.perf_counter() - inicio)
