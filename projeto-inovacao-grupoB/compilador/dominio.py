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

# Nome do dominio gerado; o problema compilado aponta para ele.
NOME_PADRAO = "visita-domiciliar-acs-regras"


# ----------------------------------------------------------------------------
#  acesso a arvore
# ----------------------------------------------------------------------------

def _secao(arvore: list, chave: str) -> list:
    for item in arvore[2:]:
        if isinstance(item, list) and item and item[0] == chave:
            return item
    raise ErroRegra(f"o domínio de entrada não tem a seção {chave}")


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
    raise ErroRegra(f"a ação \"{acao[1]}\" do domínio de entrada não tem "
                    f"parâmetro do tipo {tipo}")


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
    """Confere as regras contra o dominio. Acumula todos os problemas."""
    erros: list[str] = []
    predicados = {p[0] for p in _secao(arvore, ":predicates")[1:]}
    acoes = _acoes(arvore)
    nomes_recursos = [r.nome for r in regras.recursos]
    gerados: dict[str, str] = {}

    def reservar(nome: str, dono: str, escrito: str) -> None:
        # `escrito` e o nome como aparece na regra; `nome` pode ser derivado
        # dele (ex.: recurso "alcool" gera "repor-alcool").
        if nome == escrito:
            sujeito = f'o nome "{nome}"'
        else:
            sujeito = f'gera o nome "{nome}", que'
        if nome in predicados or nome in acoes:
            erros.append(f"{dono}: {sujeito} já é usado pelo domínio de entrada "
                         f"(lei ou Ciclo 2). Escolha outro nome")
        elif nome in gerados and gerados[nome] != dono:
            erros.append(f"{dono}: {sujeito} coincide com um nome gerado por "
                         f"{gerados[nome]}")
        else:
            gerados[nome] = dono

    for r in regras.recursos:
        dono = f"recurso \"{r.nome}\""
        reservar(r.predicado, dono, r.nome)
        reservar(r.predicado_maximo, dono, r.nome)
        reservar(r.acao_reposicao, dono, r.nome)

    for p in regras.preparos:
        dono = f"preparo \"{p.nome}\""
        reservar(p.nome, dono, p.nome)
        reservar(p.estado, f"{dono}, campo 'estado'", p.estado)
        if p.consome is not None and p.consome not in nomes_recursos:
            declarados = ", ".join(nomes_recursos) or "nenhum"
            erros.append(f"{dono}: consome \"{p.consome}\", mas não há recurso com "
                         f"esse nome. Recursos declarados: {declarados}")
        for procedimento in p.exigido_antes_de:
            acao = PROCEDIMENTOS.get(procedimento)
            if acao not in acoes:
                erros.append(f"{dono}: o domínio de entrada não tem a ação "
                             f"\"{acao or procedimento}\", ligada ao procedimento "
                             f"\"{procedimento}\"")
        if p.desfeito_ao_sair:
            for nome in ACOES_DE_SAIDA:
                if nome not in acoes:
                    erros.append(f"{dono}: o domínio de entrada não tem a ação "
                                 f"\"{nome}\", necessária para 'desfeito_ao_sair'")
    if erros:
        raise ErroRegra(erros)


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
