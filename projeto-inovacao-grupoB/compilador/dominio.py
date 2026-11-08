"""
Compilacao: dominio legal + regras -> dominio com as regras aplicadas.

O dominio de entrada e lido, nunca alterado: o compilador trabalha sobre
uma copia da arvore. Cada modelo de regra vira um conjunto fixo de
alteracoes, sempre as mesmas para as mesmas entradas.

    Recurso R (modelo A)
        predicados  (R ?n - nivel)  (nivel-maximo-R ?n - nivel)
        acao        repor-R: na UBS, leva o estoque de R ao maximo

    Preparo Y com estado E (modelo B)
        predicado   (E ?ag - agente)
        acao        Y: torna E verdadeiro; se consome R, gasta uma unidade
        efeito      (not (E ?ag)) nas acoes de saida, se desfeito ao sair

    Pre-requisito (modelo C)
        precondicao (E ?ag) nas acoes dos procedimentos listados

As acoes e os nomes gerados seguem o padrao do dominio estendido do
Ciclo 2, para que as regras sinteticas possam ser reproduzidas por ele.
"""

from __future__ import annotations

import copy
from typing import Any

from .regras import PROCEDIMENTOS, ErroRegra, Regras

# Acoes em que o ACS deixa a casa: o que for "desfeito ao sair" cai nelas.
ACOES_DE_SAIDA = ("mover", "desviar-para-ubs")


# ----------------------------------------------------------------------------
#  acesso a arvore
# ----------------------------------------------------------------------------

def _secao(arvore: list, chave: str) -> list:
    for item in arvore[2:]:
        if isinstance(item, list) and item and item[0] == chave:
            return item
    raise ErroRegra(f"o dominio de entrada nao tem a secao {chave}")


def _acoes(arvore: list) -> dict[str, list]:
    return {item[1]: item for item in arvore[2:]
            if isinstance(item, list) and item and item[0] == ":action"}


def _campo(acao: list, chave: str) -> Any:
    indice = acao.index(chave)
    return acao[indice + 1]


def _trocar_campo(acao: list, chave: str, valor: Any) -> None:
    acao[acao.index(chave) + 1] = valor


def _variavel_do_tipo(acao: list, tipo: str) -> str:
    """Primeiro parametro do tipo pedido, ex.: '?ag' para 'agente'."""
    pendentes: list[str] = []
    for token in _campo(acao, ":parameters"):
        if token == "-":
            continue
        if token.startswith("?"):
            pendentes.append(token)
            continue
        if token == tipo and pendentes:
            return pendentes[0]
        pendentes = []
    raise ErroRegra(f"a acao '{acao[1]}' nao tem parametro do tipo {tipo}")


def _como_and(expressao: list) -> list:
    if expressao and expressao[0] == "and":
        return expressao
    return ["and", expressao] if expressao else ["and"]


def _acrescentar_efeito(acao: list, literal: list) -> None:
    """Acrescenta o literal antes do (increase (total-cost) ...), se houver."""
    efeito = _como_and(_campo(acao, ":effect"))
    posicao = next((i for i, f in enumerate(efeito)
                    if isinstance(f, list) and f and f[0] == "increase"), len(efeito))
    efeito.insert(posicao, literal)
    _trocar_campo(acao, ":effect", efeito)


def _acrescentar_precondicao(acao: list, literal: list) -> None:
    precondicao = _como_and(_campo(acao, ":precondition"))
    precondicao.append(literal)
    _trocar_campo(acao, ":precondition", precondicao)


def _custo(minutos: int) -> list:
    return ["increase", ["total-cost"], str(minutos)]


# ----------------------------------------------------------------------------
#  conferencias que dependem do dominio
# ----------------------------------------------------------------------------

def _conferir(arvore: list, regras: Regras) -> None:
    predicados = {p[0] for p in _secao(arvore, ":predicates")[1:]}
    acoes = _acoes(arvore)
    nomes_recursos = [r.nome for r in regras.recursos]

    novos_predicados: dict[str, str] = {}
    novas_acoes: dict[str, str] = {}

    def reservar(nome: str, tabela: dict, existentes, tipo: str, dono: str) -> None:
        if nome in existentes:
            raise ErroRegra(f"{dono}: o nome '{nome}' ja existe no dominio como "
                            f"{tipo}. Escolha outro nome")
        if nome in tabela:
            raise ErroRegra(f"{dono}: o nome '{nome}' ja foi usado por {tabela[nome]}")
        tabela[nome] = dono

    for r in regras.recursos:
        dono = f"recurso '{r.nome}'"
        reservar(r.predicado, novos_predicados, predicados, "predicado", dono)
        reservar(r.predicado_maximo, novos_predicados, predicados, "predicado", dono)
        reservar(r.acao_reposicao, novas_acoes, acoes, "acao", dono)

    for p in regras.preparos:
        dono = f"preparo '{p.nome}'"
        reservar(p.estado, novos_predicados, predicados, "predicado", dono)
        reservar(p.nome, novas_acoes, acoes, "acao", dono)
        if p.consome is not None and p.consome not in nomes_recursos:
            disponiveis = ", ".join(nomes_recursos) or "nenhum recurso declarado"
            raise ErroRegra(f"{dono}: consome '{p.consome}', mas nao ha recurso com "
                            f"esse nome. Recursos declarados: {disponiveis}")
        for procedimento in p.exigido_antes_de:
            if PROCEDIMENTOS[procedimento] not in acoes:
                raise ErroRegra(f"{dono}: o dominio de entrada nao tem a acao "
                                f"'{PROCEDIMENTOS[procedimento]}'")
        if p.desfeito_ao_sair:
            for nome in ACOES_DE_SAIDA:
                if nome not in acoes:
                    raise ErroRegra(f"{dono}: o dominio de entrada nao tem a acao "
                                    f"'{nome}', necessaria para 'desfeito_ao_sair'")


# ----------------------------------------------------------------------------
#  geracao
# ----------------------------------------------------------------------------

def _acao_reposicao(r) -> list:
    return [":action", r.acao_reposicao,
            ":parameters", ["?ag", "-", "agente", "?ubs", "-", "local",
                            "?atual", "-", "nivel", "?cheio", "-", "nivel"],
            ":precondition", ["and",
                              ["em", "?ag", "?ubs"],
                              ["e-ubs", "?ubs"],
                              [r.predicado, "?atual"],
                              [r.predicado_maximo, "?cheio"]],
            ":effect", ["and",
                        ["not", [r.predicado, "?atual"]],
                        [r.predicado, "?cheio"],
                        _custo(r.custo_reposicao)]]


def _acao_preparo(p, recurso) -> list:
    parametros = ["?ag", "-", "agente"]
    precondicao: list = ["and"]
    efeito: list = ["and", [p.estado, "?ag"]]
    if recurso is not None:
        parametros += ["?n", "-", "nivel", "?n-1", "-", "nivel"]
        precondicao += [[recurso.predicado, "?n"], ["prox", "?n-1", "?n"]]
        efeito += [["not", [recurso.predicado, "?n"]], [recurso.predicado, "?n-1"]]
    precondicao.append(["not", [p.estado, "?ag"]])
    efeito.append(_custo(p.custo))
    return [":action", p.nome, ":parameters", parametros,
            ":precondition", precondicao, ":effect", efeito]


def _posicao_apos_ultima_acao(arvore: list) -> int:
    indices = [i for i, item in enumerate(arvore)
               if isinstance(item, list) and item and item[0] == ":action"]
    return indices[-1] + 1 if indices else len(arvore)


def compilar_dominio(arvore: list, regras: Regras, *, nome: str | None = None) -> list:
    """Devolve uma nova arvore de dominio com as regras aplicadas."""
    _conferir(arvore, regras)
    saida = copy.deepcopy(arvore)
    if nome is not None:
        saida[1] = ["domain", nome]

    requisitos = _secao(saida, ":requirements")
    if regras.preparos and ":negative-preconditions" not in requisitos:
        requisitos.append(":negative-preconditions")

    predicados = _secao(saida, ":predicates")
    acoes = _acoes(saida)
    recursos = {r.nome: r for r in regras.recursos}
    novas_acoes: list[list] = []

    for r in regras.recursos:
        predicados.append([r.predicado, "?n", "-", "nivel"])
        predicados.append([r.predicado_maximo, "?n", "-", "nivel"])
        novas_acoes.append(_acao_reposicao(r))

    for p in regras.preparos:
        predicados.append([p.estado, "?ag", "-", "agente"])
        novas_acoes.append(_acao_preparo(p, recursos.get(p.consome)))
        if p.desfeito_ao_sair:
            for nome_acao in ACOES_DE_SAIDA:
                acao = acoes[nome_acao]
                agente = _variavel_do_tipo(acao, "agente")
                _acrescentar_efeito(acao, ["not", [p.estado, agente]])
        for procedimento in p.exigido_antes_de:
            acao = acoes[PROCEDIMENTOS[procedimento]]
            agente = _variavel_do_tipo(acao, "agente")
            _acrescentar_precondicao(acao, [p.estado, agente])

    posicao = _posicao_apos_ultima_acao(saida)
    saida[posicao:posicao] = novas_acoes
    return saida
