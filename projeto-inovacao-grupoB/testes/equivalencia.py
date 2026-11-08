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
    python -m testes.equivalencia
"""

from __future__ import annotations

import copy
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from compilador import (NOME_PADRAO, carregar_regras, compilar_dominio,  # noqa: E402
                        gerar_problema_com_regras)
from compilador import ciclo2  # noqa: E402
from compilador.pddl import em_linha, escrever_pddl  # noqa: E402
from compilador.regras import Regras  # noqa: E402

EXEMPLOS = RAIZ / "exemplos"

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

def _forma(arvore: list) -> dict:
    """Representacao canonica: ordem e nomes de dominio nao importam."""
    chave = em_linha

    predicados = next(s for s in arvore[2:] if s[0] == ":predicates")
    requisitos = next(s for s in arvore[2:] if s[0] == ":requirements")
    acoes = {}
    for acao in _acoes(arvore):
        efeitos = _literais(_campo(acao, ":effect"))
        acoes[acao[1]] = {
            "parametros": sorted(f"{v} - {t}" for v, t in
                                 _pares_tipados(_campo(acao, ":parameters"))),
            "precondicao": sorted(map(chave, _literais(_campo(acao, ":precondition")))),
            "efeito": sorted(chave(l) for l in efeitos if l[0] != "increase"),
            "custo": [chave(l) for l in efeitos if l[0] == "increase"],
        }
    return {
        "requisitos": sorted(requisitos[1:]),
        "predicados": sorted(chave(p) for p in predicados[1:]),
        "acoes": acoes,
    }


def diferencas_estruturais(a: list, b: list) -> list[str]:
    """Lista legivel das diferencas entre dois dominios (vazia se iguais)."""
    fa, fb = _forma(a), _forma(b)
    difs = []
    for campo in ("requisitos", "predicados"):
        so_a = sorted(set(fa[campo]) - set(fb[campo]))
        so_b = sorted(set(fb[campo]) - set(fa[campo]))
        if so_a or so_b:
            difs.append(f"{campo}: so no primeiro {so_a}; so no segundo {so_b}")
    for nome in sorted(fa["acoes"].keys() | fb["acoes"].keys()):
        if nome not in fa["acoes"] or nome not in fb["acoes"]:
            lado = "primeiro" if nome in fa["acoes"] else "segundo"
            difs.append(f"acao {nome}: so existe no {lado}")
            continue
        for campo, valor in fa["acoes"][nome].items():
            outro = fb["acoes"][nome][campo]
            if valor != outro:
                so_a = [x for x in valor if x not in outro]
                so_b = [x for x in outro if x not in valor]
                difs.append(f"acao {nome}, {campo}: so no primeiro {so_a}; "
                            f"so no segundo {so_b}")
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
    reposicoes: int

    @property
    def equivalente(self) -> bool:
        custos = {self.custo_compilado, self.custo_estendido,
                  self.cruzado_compilado_no_estendido,
                  self.cruzado_estendido_no_compilado}
        return None not in custos and len(custos) == 1


def preparar_dominios(regras: Regras, manter: set[str]) -> tuple[list, list]:
    """(compilado, estendido projetado), como arvores."""
    ler = ciclo2.planejador().ler_sexp
    compilado = compilar_dominio(ler(str(ciclo2.DOMINIO_LEGAL)), regras, nome=NOME_PADRAO)
    estendido = projetar(ler(str(ciclo2.DOMINIO_ESTENDIDO)), manter)
    return compilado, estendido


def comparar_instancia(regras: Regras, compilado: list, estendido: list,
                       pacientes: int, semente: int, *, fitas: int = 3,
                       limite_segundos: float = 60.0) -> Comparacao:
    planejador = ciclo2.planejador()
    from acsplan.dados import gerador
    from acsplan.geo import roteirizador

    dados = gerador.gerar(pacientes, semente, fitas_por_carga=fitas)
    roteamento = roteirizador.roteirizar(dados, usar_precedencia=True)

    with tempfile.TemporaryDirectory() as pasta:
        caminhos = {}
        for nome, arvore in (("compilado", compilado), ("estendido", estendido)):
            caminhos[nome] = os.path.join(pasta, f"{nome}.pddl")
            Path(caminhos[nome]).write_text(escrever_pddl(arvore, [nome]), encoding="utf-8")
        problema = os.path.join(pasta, "problema.pddl")
        gerar_problema_com_regras(dados, roteamento, regras, problema,
                                  nome_dominio=NOME_PADRAO)
        tarefas = {nome: planejador.TarefaPlanejamento(
                       planejador.carregar_dominio(caminho),
                       planejador.carregar_problema(problema))
                   for nome, caminho in caminhos.items()}

    resultados = {nome: planejador.resolver(t, "astar-hmax", limite_segundos=limite_segundos)
                  for nome, t in tarefas.items()}

    def custo(nome):
        r = resultados[nome]
        return r.custo if r.sucesso else None

    def cruzado(de, em):
        r = resultados[de]
        return executar_plano(tarefas[em], r.plano) if r.sucesso else None

    reposicoes = sum(passo.startswith("repor-")
                     for passo in resultados["compilado"].plano)
    return Comparacao(pacientes, semente, custo("compilado"), custo("estendido"),
                      cruzado("compilado", "estendido"), cruzado("estendido", "compilado"),
                      reposicoes)


def com_capacidade(regras: Regras, capacidade: int) -> Regras:
    """As mesmas regras, com outra capacidade em todos os recursos."""
    from dataclasses import replace
    return replace(regras, recursos=tuple(replace(r, capacidade=capacidade)
                                          for r in regras.recursos))


def main() -> int:
    regras = carregar_regras(str(EXEMPLOS / "higienizacao.toml"))
    compilado, estendido = preparar_dominios(regras, {"higienizacao"})

    print("Equivalencia: higienizacao compilada x higienizacao do dominio estendido\n")
    difs = diferencas_estruturais(compilado, estendido)
    print(f"Estrutural: {'IGUAIS' if not difs else f'{len(difs)} diferenca(s)'}")
    for d in difs:
        print(f"  - {d}")

    print("\nComportamental (A* com h_max, custo otimo):")
    print(f"  {'alcool':>6} {'pac':>3} {'sem':>3} {'compilado':>9} {'estendido':>9} "
          f"{'comp->est':>9} {'est->comp':>9} {'repos.':>6}  resultado")
    todas = True
    capacidade_exemplo = regras.recursos[0].capacidade
    for capacidade in (capacidade_exemplo, 2):
        variante = com_capacidade(regras, capacidade)
        for pacientes in (2, 3, 4):
            for semente in range(1, 6):
                c = comparar_instancia(variante, compilado, estendido, pacientes, semente)
                todas &= c.equivalente
                f = lambda v: "-" if v is None else str(v)
                print(f"  {capacidade:>6} {pacientes:>3} {semente:>3} "
                      f"{f(c.custo_compilado):>9} {f(c.custo_estendido):>9} "
                      f"{f(c.cruzado_compilado_no_estendido):>9} "
                      f"{f(c.cruzado_estendido_no_compilado):>9} {c.reposicoes:>6}  "
                      f"{'ok' if c.equivalente else 'DIFERENTE'}")
    print("\ncomp->est: custo do plano do compilado executado no estendido (e vice-versa)")
    print("repos.: reposicoes na UBS no plano do compilado")
    print(f"\nResultado: {'EQUIVALENTES' if todas and not difs else 'NAO EQUIVALENTES'}")
    return 0 if todas and not difs else 1


if __name__ == "__main__":
    sys.exit(main())
