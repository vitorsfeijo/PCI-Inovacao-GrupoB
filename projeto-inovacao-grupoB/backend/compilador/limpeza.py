"""
Limpeza do plano: eliminacao de acoes redundantes (action elimination).

Estrategias de busca sem garantia de otimo (A* com h_add, GBFS) podem
devolver planos com acoes inuteis. Na avaliacao, com a exigencia de avental
para acamados, um plano vestiu avental cinco vezes para dois acamados e foi
a UBS quatro vezes so para repor aventais que nao precisava usar. O roteiro
mostraria tudo isso ao ACS.

A tecnica (Fink e Yang, 1992; Nakhost e Muller, 2010): para cada acao do
plano, tenta-se retira-la junto com as acoes seguintes que deixam de ser
aplicaveis sem ela (por exemplo, sem o desvio ate a UBS, a reposicao e a
volta a rota tambem saem). Se o que sobra ainda executa e atinge o objetivo,
a retirada e aceita. O plano so perde acoes, entao continua valido e nunca
fica mais caro; um plano otimo de custo positivo nao tem o que perder.
"""

from __future__ import annotations


def _aplicavel(acao, estado) -> bool:
    return acao.pre_pos <= estado and not (acao.pre_neg & estado)


def _aplicar(acao, estado):
    return (estado - acao.remocoes) | acao.adicoes


def eliminar_redundantes(tarefa, plano: list[str]) -> list[str]:
    """Devolve o plano sem as acoes redundantes. `tarefa` e a tarefa de
    planejamento em que o plano foi encontrado."""
    por_nome = {acao.assinatura: acao for acao in tarefa.acoes}
    acoes = [por_nome[passo] for passo in plano]

    prefixo = tarefa.estado_inicial          # estado antes de acoes[i]
    i = 0
    while i < len(acoes):
        candidato = acoes[:i]
        estado = prefixo
        for acao in acoes[i + 1:]:
            if _aplicavel(acao, estado):
                estado = _aplicar(acao, estado)
                candidato.append(acao)
        if tarefa.e_objetivo(estado):
            acoes = candidato                # retirada aceita; i fica onde esta
        else:
            prefixo = _aplicar(acoes[i], prefixo)
            i += 1
    return [acao.assinatura for acao in acoes]
