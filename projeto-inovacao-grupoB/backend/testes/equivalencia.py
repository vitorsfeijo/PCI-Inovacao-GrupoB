"""
Equivalencia entre o dominio compilado e o dominio estendido do Ciclo 2.

O dominio estendido tem as tres regras sinteticas juntas (higienizacao,
mascara e coletor). Enquanto o compilador so cobre parte delas, a comparacao
e feita com a PROJECAO do estendido: o estendido sem os elementos das regras
que ainda nao foram escritas como modelos. A projecao e mecanica, por nome
de predicado, sem edicao manual:

    1. remove os predicados das regras de fora e as acoes que os produzem
       ou consomem com exclusividade;
    2. remove das demais acoes os literais com esses predicados;
    3. remove os (prox a b) que sobraram sem uso e os parametros que nao
       aparecem em mais nenhum literal.

Comparacoes:

    estrutural      mesmos predicados, mesmas acoes, e em cada acao os
                    mesmos parametros, precondicoes, efeitos e custo
    comportamental  em cada instancia, mesmo custo otimo nos dois dominios,
                    e o plano de cada um e valido e de mesmo custo no outro

Uso direto (relatorio com mais instancias):

    cd projeto-inovacao-grupoB
    python3 acs.py equivalencia
"""

from __future__ import annotations

import copy
import itertools
import os
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from compilador import (NOME_PADRAO, carregar_regras, compilar_dominio,  # noqa: E402
                        gerar_problema_com_regras)
from compilador import ciclo2  # noqa: E402
from compilador.pddl import em_linha, escrever_pddl  # noqa: E402
from compilador.regras import Regras  # noqa: E402

EXEMPLOS = RAIZ.parent / "exemplos"

# Predicados de cada regra sintetica do dominio estendido.
PREDICADOS_SINTETICOS = {
    "higienizacao": {"maos-higienizadas", "alcool", "nivel-maximo-alcool"},
    "mascara": {"exige-protecao-respiratoria", "mascara-vestida", "mascaras",
                "nivel-maximo-mascaras", "protecao-conferida"},
    "coletor": {"coletor", "nivel-maximo-coletor"},
}


# ============================================================================
#  PROJECAO DO DOMINIO ESTENDIDO
# ============================================================================

def _acoes(arvore: list) -> list[list]:
    return [item for item in arvore[2:]
            if isinstance(item, list) and item and item[0] == ":action"]


def _campo(acao: list, chave: str):
    return acao[acao.index(chave) + 1]


def _literais(expressao: list) -> list[list]:
    """Itens de um (and ...), ou o proprio literal."""
    return expressao[1:] if expressao and expressao[0] == "and" else [expressao]


def _atomo(literal: list) -> list:
    return literal[1] if literal[0] == "not" else literal


def _variaveis(literal: list) -> set[str]:
    texto = str(literal)
    return {t.strip("'[], ") for t in texto.split() if t.strip("'[], ").startswith("?")}


def _pares_tipados(parametros: list[str]) -> list[tuple[str, str]]:
    pares, pendentes, i = [], [], 0
    while i < len(parametros):
        if parametros[i] == "-":
            pares.extend((v, parametros[i + 1]) for v in pendentes)
            pendentes, i = [], i + 2
        else:
            pendentes.append(parametros[i])
            i += 1
    return pares


def projetar(arvore: list, manter: set[str]) -> list:
    """Estendido sem as regras sinteticas fora de `manter`."""
    remover = set().union(*(p for nome, p in PREDICADOS_SINTETICOS.items()
                            if nome not in manter))
    saida = copy.deepcopy(arvore)

    predicados = next(s for s in saida[2:] if s[0] == ":predicates")
    predicados[1:] = [p for p in predicados[1:] if p[0] not in remover]

    novas_acoes = []
    for acao in _acoes(saida):
        pre = [l for l in _literais(_campo(acao, ":precondition"))
               if _atomo(l)[0] not in remover]
        efe = [l for l in _literais(_campo(acao, ":effect"))
               if l[0] == "increase" or _atomo(l)[0] not in remover]
        # acao que so existia para uma regra removida: tudo o que ela fazia sumiu
        if not any(l[0] != "increase" for l in efe):
            continue
        # (prox a b) que sobrou sem uso: as variaveis nao aparecem em mais nada
        for _ in range(2):
            outros = [l for l in pre + efe if _atomo(l)[0] != "prox"]
            usadas = set().union(*(_variaveis(l) for l in outros)) if outros else set()
            pre = [l for l in pre
                   if _atomo(l)[0] != "prox" or _variaveis(l) & usadas == _variaveis(l)]
        usadas = set().union(*(_variaveis(l) for l in pre + efe))
        parametros = []
        for variavel, tipo in _pares_tipados(_campo(acao, ":parameters")):
            if variavel in usadas:
                parametros += [variavel, "-", tipo]
        acao[acao.index(":parameters") + 1] = parametros
        acao[acao.index(":precondition") + 1] = ["and", *pre]
        acao[acao.index(":effect") + 1] = ["and", *efe]
        novas_acoes.append(acao)

    saida[:] = [item for item in saida if not (isinstance(item, list) and item
                                               and item[0] == ":action")]
    saida.extend(novas_acoes)
    return saida


# ============================================================================
#  COMPARACAO ESTRUTURAL
# ============================================================================

def _renomear(no, mapa: dict[str, str]):
    if isinstance(no, str):
        return mapa.get(no, no)
    return [_renomear(filho, mapa) for filho in no]


def _partes(acao: list) -> tuple[list[tuple[str, str]], set[str], set[str], list[str]]:
    efeitos = _literais(_campo(acao, ":effect"))
    return (_pares_tipados(_campo(acao, ":parameters")),
            {em_linha(l) for l in _literais(_campo(acao, ":precondition"))},
            {em_linha(l) for l in efeitos if l[0] != "increase"},
            [em_linha(l) for l in efeitos if l[0] == "increase"])


def acoes_equivalentes(a: list, b: list) -> bool:
    """
    Mesma acao a menos dos nomes das variaveis: existe uma troca de nomes
    (entre variaveis do mesmo tipo) que torna parametros, precondicoes,
    efeitos e custo identicos. O compilador gera, por exemplo, ?coletor onde
    o dominio escrito a mao usa ?c.
    """
    pares_a, pre_a, efe_a, custo_a = _partes(a)
    pares_b = _pares_tipados(_campo(b, ":parameters"))
    if sorted(t for _, t in pares_a) != sorted(t for _, t in pares_b):
        return False
    tipos = sorted({t for _, t in pares_a})
    por_tipo_a = {t: [v for v, u in pares_a if u == t] for t in tipos}
    por_tipo_b = {t: [v for v, u in pares_b if u == t] for t in tipos}
    escolhas = [itertools.permutations(por_tipo_a[t]) for t in tipos]
    for combinacao in itertools.product(*escolhas):
        mapa = {vb: va for t, perm in zip(tipos, combinacao)
                for vb, va in zip(por_tipo_b[t], perm)}
        _, pre_b, efe_b, custo_b = _partes(_renomear(b, mapa))
        if (pre_a, efe_a, custo_a) == (pre_b, efe_b, custo_b):
            return True
    return False


def diferencas_estruturais(a: list, b: list) -> list[str]:
    """Lista legivel das diferencas entre dois dominios (vazia se iguais)."""
    difs = []
    for chave in (":requirements", ":predicates"):
        sa = {em_linha(x) for x in next(s for s in a[2:] if s[0] == chave)[1:]}
        sb = {em_linha(x) for x in next(s for s in b[2:] if s[0] == chave)[1:]}
        if sa != sb:
            difs.append(f"{chave[1:]}: so no primeiro {sorted(sa - sb)}; "
                        f"so no segundo {sorted(sb - sa)}")
    acoes_a = {x[1]: x for x in _acoes(a)}
    acoes_b = {x[1]: x for x in _acoes(b)}
    for nome in sorted(acoes_a.keys() | acoes_b.keys()):
        if nome not in acoes_a or nome not in acoes_b:
            lado = "primeiro" if nome in acoes_a else "segundo"
            difs.append(f"acao {nome}: so existe no {lado}")
            continue
        if acoes_equivalentes(acoes_a[nome], acoes_b[nome]):
            continue
        # mostra a diferenca crua (sem renomear), que costuma ser a informativa
        pa, pre_a, efe_a, custo_a = _partes(acoes_a[nome])
        pb, pre_b, efe_b, custo_b = _partes(acoes_b[nome])
        partes = []
        for rotulo, x, y in (("parametros", set(map(str, pa)), set(map(str, pb))),
                             ("precondicao", pre_a, pre_b), ("efeito", efe_a, efe_b),
                             ("custo", set(custo_a), set(custo_b))):
            if x != y:
                partes.append(f"{rotulo}: so no primeiro {sorted(x - y)}; "
                              f"so no segundo {sorted(y - x)}")
        difs.append(f"acao {nome} (mesmo renomeando variaveis): " + " | ".join(partes))
    return difs


# ============================================================================
#  COMPARACAO COMPORTAMENTAL
# ============================================================================

def executar_plano(tarefa, plano: list[str]) -> int | None:
    """Executa o plano na tarefa. Devolve o custo, ou None se for invalido."""
    por_nome = {a.assinatura: a for a in tarefa.acoes}
    estado = tarefa.estado_inicial
    custo = 0
    for passo in plano:
        acao = por_nome.get(passo)
        if acao is None or not acao.pre_pos <= estado or acao.pre_neg & estado:
            return None
        estado = (estado - acao.remocoes) | acao.adicoes
        custo += acao.custo
    return custo if tarefa.e_objetivo(estado) else None


@dataclass
class Comparacao:
    pacientes: int
    semente: int
    custo_compilado: int | None
    custo_estendido: int | None
    cruzado_compilado_no_estendido: int | None
    cruzado_estendido_no_compilado: int | None
    reposicoes: int = 0
    marcados: int = 0

    @property
    def equivalente(self) -> bool:
        custos = {self.custo_compilado, self.custo_estendido,
                  self.cruzado_compilado_no_estendido,
                  self.cruzado_estendido_no_compilado}
        return None not in custos and len(custos) == 1


def _comparar(tarefas: dict, pacientes: int, semente: int,
              limite_segundos: float, **extras) -> Comparacao:
    """Resolve as duas tarefas e executa o plano de cada uma na outra."""
    planejador = ciclo2.planejador()
    resultados = {nome: planejador.resolver(t, "astar-hmax", limite_segundos=limite_segundos)
                  for nome, t in tarefas.items()}

    def custo(nome):
        r = resultados[nome]
        return r.custo if r.sucesso else None

    def cruzado(de, em):
        r = resultados[de]
        return executar_plano(tarefas[em], r.plano) if r.sucesso else None

    reposicoes = sum(passo.startswith(("repor-", "trocar-"))
                     for passo in resultados["compilado"].plano)
    return Comparacao(pacientes, semente, custo("compilado"), custo("estendido"),
                      cruzado("compilado", "estendido"), cruzado("estendido", "compilado"),
                      reposicoes, **extras)


def _tarefa(dominio: str, problema: str):
    planejador = ciclo2.planejador()
    return planejador.TarefaPlanejamento(planejador.carregar_dominio(dominio),
                                         planejador.carregar_problema(problema))


def _gravar_dominio(arvore: list, caminho: str) -> str:
    Path(caminho).write_text(escrever_pddl(arvore, ["teste de equivalencia"]),
                             encoding="utf-8")
    return caminho


# ---------------------------------------------------------------------------
#  equivalencia parcial: projecao do estendido, mesmo problema para os dois
# ---------------------------------------------------------------------------

def preparar_dominios(regras: Regras, manter: set[str]) -> tuple[list, list]:
    """(compilado, estendido projetado), como arvores."""
    ler = ciclo2.planejador().ler_sexp
    compilado = compilar_dominio(ler(str(ciclo2.DOMINIO_LEGAL)), regras, nome=NOME_PADRAO)
    estendido = projetar(ler(str(ciclo2.DOMINIO_ESTENDIDO)), manter)
    return compilado, estendido


def comparar_instancia(regras: Regras, compilado: list, estendido: list,
                       pacientes: int, semente: int, *, fitas: int = 3,
                       limite_segundos: float = 60.0) -> Comparacao:
    from acsplan.dados import gerador
    from acsplan.geo import roteirizador

    dados = gerador.gerar(pacientes, semente, fitas_por_carga=fitas)
    roteamento = roteirizador.roteirizar(dados, usar_precedencia=True)
    with tempfile.TemporaryDirectory() as pasta:
        problema = os.path.join(pasta, "problema.pddl")
        gerar_problema_com_regras(dados, roteamento, regras, problema,
                                  nome_dominio=NOME_PADRAO)
        tarefas = {nome: _tarefa(_gravar_dominio(arvore, os.path.join(pasta, nome)),
                                 problema)
                   for nome, arvore in (("compilado", compilado), ("estendido", estendido))}
    return _comparar(tarefas, pacientes, semente, limite_segundos)


def com_capacidade(regras: Regras, capacidade: int) -> Regras:
    """As mesmas regras, com outra capacidade em todos os recursos."""
    return replace(regras, recursos=tuple(replace(r, capacidade=capacidade)
                                          for r in regras.recursos))


# ---------------------------------------------------------------------------
#  equivalencia completa: pipeline do Ciclo 2 inteiro x pipeline compilado
# ---------------------------------------------------------------------------

# Recurso do TOML -> chave de capacidade nos dados do Ciclo 2.
CAPACIDADES_CICLO2 = {
    "alcool": "doses_alcool_por_carga",
    "mascaras": "mascaras_por_carga",
    "coletor": "capacidade_coletor",
}


def comparar_pipeline_completo(regras: Regras, compilado: list, pacientes: int,
                               semente: int, *, fitas: int = 3,
                               capacidades: dict[str, int] | None = None,
                               limite_segundos: float = 120.0) -> Comparacao:
    """
    Ciclo 2: dominio-estendido.pddl + problema gerado pelo Ciclo 2 para ele.
    Nosso:   dominio legal + regras compiladas + problema legal com as regras.
    As capacidades dos recursos saem dos mesmos dados nos dois lados.
    """
    from acsplan.dados import gerador
    from acsplan.geo import roteirizador
    from acsplan.logica.gerador_problema import gerar_problema

    capacidades = capacidades or {}
    dados = gerador.gerar(pacientes, semente, fitas_por_carga=fitas,
                          doses_alcool=capacidades.get("alcool", 6),
                          mascaras=capacidades.get("mascaras", 2),
                          capacidade_coletor=capacidades.get("coletor", 3))
    regras = replace(regras, recursos=tuple(
        replace(r, capacidade=dados["recursos"][CAPACIDADES_CICLO2[r.nome]])
        for r in regras.recursos))
    roteamento = roteirizador.roteirizar(dados, usar_precedencia=True)
    marcados = sum(bool(p.get("exige_protecao_respiratoria")) for p in dados["pacientes"])

    with tempfile.TemporaryDirectory() as pasta:
        nosso = os.path.join(pasta, "problema-compilado.pddl")
        deles = os.path.join(pasta, "problema-estendido.pddl")
        gerar_problema_com_regras(dados, roteamento, regras, nosso,
                                  nome_dominio=NOME_PADRAO)
        gerar_problema(dados, roteamento, deles, dominio="estendido")
        tarefas = {
            "compilado": _tarefa(_gravar_dominio(compilado,
                                                 os.path.join(pasta, "compilado")), nosso),
            "estendido": _tarefa(str(ciclo2.DOMINIO_ESTENDIDO), deles),
        }
    return _comparar(tarefas, pacientes, semente, limite_segundos, marcados=marcados)


# ============================================================================
#  RELATORIO
# ============================================================================

def _linha(rotulo: str, c: Comparacao, extra: str = "") -> str:
    f = lambda v: "-" if v is None else str(v)
    return (f"  {rotulo:>8} {c.pacientes:>3} {c.semente:>3} {f(c.custo_compilado):>9} "
            f"{f(c.custo_estendido):>9} {f(c.cruzado_compilado_no_estendido):>9} "
            f"{f(c.cruzado_estendido_no_compilado):>9} {c.reposicoes:>6}{extra}  "
            f"{'ok' if c.equivalente else 'DIFERENTE'}")


def relatorio_parcial() -> bool:
    regras = carregar_regras(str(EXEMPLOS / "higienizacao.toml"))
    compilado, estendido = preparar_dominios(regras, {"higienizacao"})

    print("1. Higienizacao compilada x higienizacao do estendido (projecao)\n")
    difs = diferencas_estruturais(compilado, estendido)
    print(f"Estrutural: {'IGUAIS' if not difs else f'{len(difs)} diferenca(s)'}")
    for d in difs:
        print(f"  - {d}")
    print("\nComportamental (A* com h_max, custo otimo):")
    print(f"  {'alcool':>8} {'pac':>3} {'sem':>3} {'compilado':>9} {'estendido':>9} "
          f"{'comp->est':>9} {'est->comp':>9} {'repos.':>6}  resultado")
    todas = True
    for capacidade in (regras.recursos[0].capacidade, 2):
        variante = com_capacidade(regras, capacidade)
        for pacientes in (2, 3, 4):
            for semente in range(1, 6):
                c = comparar_instancia(variante, compilado, estendido, pacientes, semente)
                todas &= c.equivalente
                print(_linha(str(capacidade), c))
    return todas and not difs


def relatorio_completo() -> bool:
    regras = carregar_regras(str(EXEMPLOS / "sinteticas-ciclo2.toml"))
    ler = ciclo2.planejador().ler_sexp
    compilado = compilar_dominio(ler(str(ciclo2.DOMINIO_LEGAL)), regras, nome=NOME_PADRAO)
    estendido = ler(str(ciclo2.DOMINIO_ESTENDIDO))

    print("\n2. As tres regras sinteticas compiladas x dominio estendido COMPLETO\n")
    difs = diferencas_estruturais(compilado, estendido)
    print(f"Estrutural: {'IGUAIS' if not difs else f'{len(difs)} diferenca(s)'}")
    for d in difs:
        print(f"  - {d}")
    print("\nComportamental: pipeline do Ciclo 2 (estendido + problema do Ciclo 2) x")
    print("pipeline compilado (legal + regras + problema compilado)")
    print(f"  {'recursos':>8} {'pac':>3} {'sem':>3} {'compilado':>9} {'estendido':>9} "
          f"{'comp->est':>9} {'est->comp':>9} {'repos.':>6} {'masc.':>5}  resultado")
    todas = True
    for rotulo, capacidades in (("padrao", {}),
                                ("escassos", {"alcool": 2, "mascaras": 1, "coletor": 2})):
        for pacientes in (2, 3):
            for semente in range(1, 6):
                c = comparar_pipeline_completo(regras, compilado, pacientes, semente,
                                               capacidades=capacidades)
                todas &= c.equivalente
                print(_linha(rotulo, c, f" {c.marcados:>5}"))
    # as unicas sementes do gerador do Ciclo 2 (ate 200) com dois pacientes que
    # exigem mascara: com uma mascara por carga, forcam a reposicao
    for semente in (2, 164):
        for rotulo, capacidades in (("padrao", {}), ("1 masc.", {"mascaras": 1})):
            c = comparar_pipeline_completo(regras, compilado, 4, semente,
                                           capacidades=capacidades, limite_segundos=300)
            todas &= c.equivalente
            print(_linha(rotulo, c, f" {c.marcados:>5}"))
    return todas and not difs


def main() -> int:
    parcial = relatorio_parcial()
    completo = relatorio_completo()
    print("\ncomp->est: custo do plano do compilado executado no estendido (e vice-versa)")
    print("repos.: reposicoes/trocas na UBS no plano do compilado")
    print("masc.: pacientes que exigem protecao respiratoria")
    ok = parcial and completo
    print(f"\nResultado: {'EQUIVALENTES' if ok else 'NAO EQUIVALENTES'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
