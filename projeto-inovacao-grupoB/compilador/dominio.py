"""
Compilacao: dominio legal + regras -> dominio com as regras aplicadas.

O dominio de entrada e lido, nunca alterado: o compilador trabalha sobre
uma copia da arvore. Cada modelo de regra vira um conjunto fixo de
alteracoes, sempre as mesmas para as mesmas entradas.

    Recurso R (modelo A)
        predicados  (R ?n - nivel)  (nivel-maximo-R ?n - nivel)
        acao        repor-R (ou o nome dado): na UBS, leva o estoque ao maximo

    Preparo Y com estado E (modelo B)
        predicado   (E ?ag - agente)
        acao        Y: torna E verdadeiro; se consome R, gasta uma unidade
        efeito      (not (E ?ag)) nas acoes de saida, se desfeito ao sair

    Pre-requisito (modelo C)
        precondicao (E ?ag) nas acoes dos procedimentos listados

    Consumo de R pelo procedimento P (modelo D)
        parametros  ?R ?R-1 a mais em P
        precondicao (R ?R) (prox ?R-1 ?R)
        efeito      (not (R ?R)) (R ?R-1)

    Exigencia X: pacientes com a marca M exigem o preparo Y (modelo E)
        predicados  (M ?p)  (X-conferida ?ag ?p)
        acoes       conferir-X-exigida: com M, exige o estado de Y
                    conferir-X-dispensada: sem M, custo zero
        precondicao (X-conferida ?ag ?p) nas tres variantes de iniciar-visita

As acoes e os nomes gerados seguem o padrao do dominio estendido do
Ciclo 2, para que as regras sinteticas possam ser reproduzidas por ele.
"""

from __future__ import annotations

import copy
from typing import Any

from .regras import PROCEDIMENTOS, ErroRegra, Regras

# Acoes em que o ACS deixa a casa: o que for "desfeito ao sair" cai nelas.
ACOES_DE_SAIDA = ("mover", "desviar-para-ubs")

# Acoes em que a visita comeca: a conferencia de uma exigencia cai nelas.
ACOES_INICIO_VISITA = ("iniciar-visita-urgente", "iniciar-visita", "iniciar-visita-adiavel")

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
    existentes = {p[0] for p in _secao(arvore, ":predicates")[1:]} | set(_acoes(arvore))
    acoes = _acoes(arvore)
    nomes_recursos = {r.nome for r in regras.recursos}
    nomes_preparos = {p.nome for p in regras.preparos}

    def livre(nomes: list[str], dono: str, escritos: set) -> None:
        # `escritos`: nomes digitados na regra; os demais sao derivados deles
        # (ex.: o recurso "alcool" gera "repor-alcool")
        for nome in nomes:
            if nome not in existentes:
                continue
            sujeito = (f'o nome "{nome}"' if nome in escritos
                       else f'gera o nome "{nome}", que')
            erros.append(f"{dono}: {sujeito} já é usado pelo domínio de entrada "
                         f"(lei ou Ciclo 2). Escolha outro nome")

    def acao_existe(nome: str, dono: str, motivo: str) -> None:
        if nome not in acoes:
            erros.append(f"{dono}: o domínio de entrada não tem a ação \"{nome}\", "
                         f"{motivo}")

    for r in regras.recursos:
        livre(r.nomes_gerados, f"recurso \"{r.nome}\"", {r.nome, r.nome_reposicao})
    for p in regras.preparos:
        dono = f"preparo \"{p.nome}\""
        livre([p.nome], dono, {p.nome})
        livre([p.estado], f"{dono}, campo 'estado'", {p.estado})
        if p.consome is not None and p.consome not in nomes_recursos:
            erros.append(f"{dono}: consome \"{p.consome}\", mas não há recurso com "
                         f"esse nome")
        for procedimento in p.exigido_antes_de:
            acao_existe(PROCEDIMENTOS[procedimento], dono,
                        f"ligada ao procedimento \"{procedimento}\"")
        if p.desfeito_ao_sair:
            for nome in ACOES_DE_SAIDA:
                acao_existe(nome, dono, "necessária para 'desfeito_ao_sair'")
    for c in regras.consumos:
        dono = f"consumo de \"{c.recurso}\" por \"{c.procedimento}\""
        if c.recurso not in nomes_recursos:
            erros.append(f"{dono}: não há recurso com esse nome")
        acao_existe(PROCEDIMENTOS[c.procedimento], dono,
                    f"ligada ao procedimento \"{c.procedimento}\"")
    for e in regras.exigencias:
        dono = f"exigência \"{e.nome}\""
        livre([e.marca], f"{dono}, campo 'marca'", {e.marca})
        livre(e.nomes_gerados[1:], dono, set())
        if e.preparo not in nomes_preparos:
            erros.append(f"{dono}: não há preparo \"{e.preparo}\"")
        for nome in ACOES_INICIO_VISITA:
            acao_existe(nome, dono, "onde a conferência é exigida")
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


def _variaveis(acao: list) -> set[str]:
    return {t for t in _campo(acao, ":parameters") if t.startswith("?")}


def _aplicar_consumo(acao: list, recurso) -> None:
    """O procedimento passa a gastar uma unidade do recurso (modelo D)."""
    base = f"?{recurso.nome}"
    sufixo, usadas = "", _variaveis(acao)
    while f"{base}{sufixo}" in usadas or f"{base}{sufixo}-1" in usadas:
        sufixo = str(int(sufixo or 1) + 1)
    atual, anterior = f"{base}{sufixo}", f"{base}{sufixo}-1"
    acao[acao.index(":parameters") + 1] = (_campo(acao, ":parameters")
                                           + [atual, "-", "nivel", anterior, "-", "nivel"])
    _acrescentar_precondicao(acao, [recurso.predicado, atual])
    _acrescentar_precondicao(acao, ["prox", anterior, atual])
    _acrescentar_efeito(acao, ["not", [recurso.predicado, atual]])
    _acrescentar_efeito(acao, [recurso.predicado, anterior])


def _acoes_conferencia(e, estado: str) -> list[list]:
    """As duas variantes da conferencia na porta (modelo E)."""
    parametros = ["?ag", "-", "agente", "?p", "-", "paciente", "?l", "-", "local"]
    base = [["em", "?ag", "?l"], ["residencia-de", "?p", "?l"]]
    ainda_nao = ["not", [e.predicado_conferencia, "?ag", "?p"]]
    conferida = [e.predicado_conferencia, "?ag", "?p"]
    exigida = [":action", e.acao_exigida, ":parameters", list(parametros),
               ":precondition", ["and", *copy.deepcopy(base), [e.marca, "?p"],
                                 [estado, "?ag"], copy.deepcopy(ainda_nao)],
               ":effect", ["and", list(conferida), _custo(e.custo)]]
    dispensada = [":action", e.acao_dispensada, ":parameters", list(parametros),
                  ":precondition", ["and", *copy.deepcopy(base),
                                    ["not", [e.marca, "?p"]], copy.deepcopy(ainda_nao)],
                  ":effect", ["and", list(conferida), _custo(0)]]
    return [exigida, dispensada]


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
    if (regras.preparos or regras.exigencias) and ":negative-preconditions" not in requisitos:
        requisitos.append(":negative-preconditions")

    predicados = _secao(saida, ":predicates")
    acoes = _acoes(saida)
    recursos = {r.nome: r for r in regras.recursos}
    preparos = {p.nome: p for p in regras.preparos}
    novas_acoes: list[list] = []

    # A. recursos
    for r in regras.recursos:
        predicados.append([r.predicado, "?n", "-", "nivel"])
        predicados.append([r.predicado_maximo, "?n", "-", "nivel"])
        novas_acoes.append(_acao_reposicao(r))

    # B e C. preparos e pre-requisitos
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

    # D. consumo em procedimento
    for c in regras.consumos:
        _aplicar_consumo(acoes[PROCEDIMENTOS[c.procedimento]], recursos[c.recurso])

    # E. exigencia por paciente
    for e in regras.exigencias:
        predicados.append([e.marca, "?p", "-", "paciente"])
        predicados.append([e.predicado_conferencia, "?ag", "-", "agente",
                           "?p", "-", "paciente"])
        novas_acoes.extend(_acoes_conferencia(e, preparos[e.preparo].estado))
        for nome_acao in ACOES_INICIO_VISITA:
            acao = acoes[nome_acao]
            _acrescentar_precondicao(acao, [e.predicado_conferencia,
                                            _variavel_do_tipo(acao, "agente"),
                                            _variavel_do_tipo(acao, "paciente")])

    posicao = _posicao_apos_ultima_acao(saida)
    saida[posicao:posicao] = novas_acoes
    return saida
