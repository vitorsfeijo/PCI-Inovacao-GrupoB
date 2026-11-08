"""
Compilacao do problema: problema do dominio legal + regras -> problema
para o dominio compilado.

O gerador de problema do Ciclo 2 nao e alterado. Ele continua gerando o
problema para o dominio legal (rota, pacientes, fitas, janelas, custos), e
este modulo acrescenta o que as regras exigem:

    Recurso R com capacidade N (modelo A)
        (R nN)                 o turno comeca com o estoque cheio
        (nivel-maximo-R nN)    ate onde a reposicao na UBS enche
        objetos e fatos (prox ...) a mais, se N passa do maior nivel existente

    Preparo (modelos B e C)
        nada: o estado do preparo comeca falso, e no PDDL o que nao esta
        no estado inicial e falso.

O dominio declarado no problema passa a ser o do dominio compilado.
"""

from __future__ import annotations

import copy
import re

from .regras import ErroRegra, Regras

_NIVEL = re.compile(r"^n(\d+)$")


def _secao(arvore: list, chave: str) -> list:
    for item in arvore[2:]:
        if isinstance(item, list) and item and item[0] == chave:
            return item
    raise ErroRegra(f"o problema de entrada não tem a seção {chave}")


def _objetos_do_tipo(objetos: list, tipo: str) -> list[str]:
    """Le `a b - tipo c - outro` e devolve os objetos do tipo pedido."""
    encontrados: list[str] = []
    pendentes: list[str] = []
    i = 0
    while i < len(objetos):
        if objetos[i] == "-":
            if objetos[i + 1] == tipo:
                encontrados.extend(pendentes)
            pendentes = []
            i += 2
        else:
            pendentes.append(objetos[i])
            i += 1
    return encontrados


def _maior_nivel(objetos: list) -> int:
    indices = []
    for nome in _objetos_do_tipo(objetos, "nivel"):
        casamento = _NIVEL.match(nome)
        if not casamento:
            raise ErroRegra(f"o problema de entrada tem um nível chamado \"{nome}\"; "
                            f"o compilador espera níveis no formato n0, n1, n2...")
        indices.append(int(casamento.group(1)))
    if not indices:
        raise ErroRegra("o problema de entrada não declara objetos do tipo nivel")
    if sorted(indices) != list(range(max(indices) + 1)):
        raise ErroRegra("os níveis do problema de entrada não formam uma sequência "
                        "contínua a partir de n0")
    return max(indices)


def compilar_problema(arvore: list, regras: Regras, *, nome_dominio: str) -> list:
    """Devolve uma nova arvore de problema com os fatos que as regras exigem."""
    saida = copy.deepcopy(arvore)
    _secao(saida, ":domain")[1] = nome_dominio

    objetos = _secao(saida, ":objects")
    init = _secao(saida, ":init")

    ja_existentes = {fato[0] for fato in init[1:] if isinstance(fato, list) and fato}
    erros = [f"recurso \"{r.nome}\": o problema de entrada já tem fatos "
             f"\"{predicado}\". Use um problema gerado para o domínio legal"
             for r in regras.recursos
             for predicado in (r.predicado, r.predicado_maximo)
             if predicado in ja_existentes]
    if erros:
        raise ErroRegra(erros)

    # fatos novos entram antes dos custos (= ...), junto dos demais fatos
    posicao = next((i for i, fato in enumerate(init)
                    if isinstance(fato, list) and fato and fato[0] == "="), len(init))
    fatos = []

    # niveis a mais, se alguma capacidade passa do maior nivel existente
    maior = _maior_nivel(objetos[1:])
    necessario = max([maior] + [r.capacidade for r in regras.recursos])
    if necessario > maior:
        novos = [f"n{i}" for i in range(maior + 1, necessario + 1)]
        if objetos[-2:] == ["-", "nivel"]:
            objetos[-2:-2] = novos            # junta ao grupo "n0 n1 ... - nivel"
        else:
            objetos.extend(novos + ["-", "nivel"])
        fatos.extend(["prox", f"n{i}", f"n{i + 1}"] for i in range(maior, necessario))

    for r in regras.recursos:
        fatos.append([r.predicado, f"n{r.capacidade}"])
        fatos.append([r.predicado_maximo, f"n{r.capacidade}"])
    init[posicao:posicao] = fatos
    return saida


def gerar_problema_com_regras(dados: dict, roteamento: dict, regras: Regras,
                              caminho_saida: str, *, nome_dominio: str) -> str:
    """
    Atalho para quem usa o pipeline do Ciclo 2: gera o problema legal com o
    gerador do Ciclo 2 e aplica as regras. Devolve o texto gravado.
    """
    import os
    import tempfile

    from . import ciclo2
    from .pddl import escrever_pddl

    ciclo2.planejador()  # garante o Ciclo 2 no caminho de importacao
    from acsplan.logica.gerador_problema import gerar_problema

    with tempfile.TemporaryDirectory() as pasta:
        caminho_legal = os.path.join(pasta, "problema-legal.pddl")
        gerar_problema(dados, roteamento, caminho_legal, dominio="legal")
        arvore = ciclo2.planejador().ler_sexp(caminho_legal)

    compilado = compilar_problema(arvore, regras, nome_dominio=nome_dominio)
    texto = escrever_pddl(compilado, [
        "ARQUIVO GERADO pelo compilador de regras. Nao editar a mao.",
        "Problema do Ciclo 2 (dominio legal) com os fatos exigidos pelas regras.",
    ])
    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)
    return texto
