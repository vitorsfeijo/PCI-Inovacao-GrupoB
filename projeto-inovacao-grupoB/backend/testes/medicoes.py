"""
Medicoes da avaliacao (etapa 8.4).

    python3 acs.py medicoes            # todas as tabelas
    python3 acs.py medicoes --rapido   # limites menores, para conferir o script

Grava os resultados em exemplos/avaliacao/resultados.md. Todas as medicoes
usam a planilha de avaliacao (10 pacientes, sem selecao) e a MESMA rota.

    A. cada regra sozinha: esforco (linhas de TOML x linhas de PDDL alteradas),
       correcao (compila, roteiro conferido) e impacto (turno otimo, tempo)
    B. regras acumuladas: tamanho da instanciacao e tempo/custo nos dois
       planejadores
    C. as sete regras com 1, 2, 3, 5 e 10 pacientes

As colunas do Fast Downward ficam com "-" quando ele nao esta instalado.
"""

from __future__ import annotations

import argparse
import difflib
import math
import platform
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from compilador import (NOME_PADRAO, ciclo2, compilar_dominio,  # noqa: E402
                        compilar_problema, fastdownward, ler_regras)
from compilador.instanciacao import TarefaPlanejamentoPodada  # noqa: E402
from compilador.limpeza import eliminar_redundantes  # noqa: E402
from compilador.pddl import escrever_pddl  # noqa: E402
from compilador.problema import marcas_dos_dados  # noqa: E402
from compilador import roteiro as roteiro_acs  # noqa: E402
from compilador.regras import Regras, carregar_regras, regras_para_dados  # noqa: E402

from testes.roteiros_avaliacao import verificar  # noqa: E402

AVALIACAO = RAIZ.parent / "exemplos" / "avaliacao"
PLANILHA = AVALIACAO / "microarea-avaliacao.csv"
REGRAS = sorted((AVALIACAO / "regras").glob("r*.toml"))
SINTETICAS = RAIZ.parent / "exemplos" / "sinteticas-ciclo2.toml"
MARCAS = ["gestante", "suspeita_tuberculose", "exige_avental"]
SAIDA = AVALIACAO / "resultados.md"


# ============================================================================
#  infraestrutura
# ============================================================================

def juntar(arquivos: list[Path]) -> Regras:
    dados: dict = {}
    for arquivo in arquivos:
        for modelo, blocos in regras_para_dados(carregar_regras(str(arquivo))).items():
            dados.setdefault(modelo, []).extend(blocos)
    return ler_regras(dados)


def rotulo_regra(arquivo: Path) -> str:
    return arquivo.stem.split("-")[0]           # r1-lancetas -> r1


@dataclass
class Execucao:
    sucesso: bool
    custo: int | None
    segundos: float
    plano: list[str]
    terminou_no_limite: bool = False


class Cenario:
    """Domínio + problema compilados para um conjunto de regras e pacientes."""

    def __init__(self, regras: Regras, dados: dict, roteamento: dict, pasta: Path):
        planejador = ciclo2.planejador()
        legal = planejador.ler_sexp(str(ciclo2.DOMINIO_LEGAL))
        self.regras, self.dados = regras, dados
        self.dominio_arvore = compilar_dominio(legal, regras, nome=NOME_PADRAO)
        self.caminho_dominio = str(pasta / "dominio.pddl")
        self.caminho_problema = str(pasta / "problema.pddl")
        Path(self.caminho_dominio).write_text(escrever_pddl(self.dominio_arvore, ["medicao"]),
                                              encoding="utf-8")
        ciclo2.garantir_caminho()
        from acsplan.logica.gerador_problema import gerar_problema
        legal_problema = str(pasta / "problema-legal.pddl")
        gerar_problema(dados, roteamento, legal_problema, dominio="legal")
        marcados = marcas_dos_dados(dados, regras) if regras.exigencias else None
        problema = compilar_problema(planejador.ler_sexp(legal_problema), regras,
                                     nome_dominio=NOME_PADRAO, marcados=marcados)
        Path(self.caminho_problema).write_text(escrever_pddl(problema, ["medicao"]),
                                               encoding="utf-8")
        inicio = time.perf_counter()
        self.tarefa = TarefaPlanejamentoPodada(
            planejador.carregar_dominio(self.caminho_dominio),
            planejador.carregar_problema(self.caminho_problema))
        self.segundos_instanciacao = time.perf_counter() - inicio

    def combinacoes_sem_poda(self) -> int:
        """Quantas combinacoes a instanciacao original do Ciclo 2 testaria."""
        total = 0
        for acao in self.tarefa.dominio.acoes:
            total += math.prod(len(self.tarefa.objetos_por_tipo.get(t, []))
                               for _, t in acao.parametros)
        return total

    def ciclo2(self, estrategia: str, limite: float) -> Execucao:
        r = ciclo2.planejador().resolver(self.tarefa, estrategia, limite_segundos=limite)
        interrompida = not r.sucesso and r.motivo.startswith(("timeout", "limite"))
        return Execucao(r.sucesso, r.custo if r.sucesso else None, r.segundos, r.plano,
                        interrompida)

    def fd(self, configuracao: str, limite: float) -> Execucao | None:
        if not fastdownward.disponivel():
            return None
        r = fastdownward.resolver(self.caminho_dominio, self.caminho_problema, self.tarefa,
                                  configuracao=configuracao, limite_segundos=limite)
        interrompida = not r.sucesso and r.motivo.startswith(("timeout", "limite"))
        # o LAMA so devolve quando o limite acaba; o custo vale, o tempo nao
        return Execucao(r.sucesso, r.custo if r.sucesso else None, r.segundos, r.plano,
                        interrompida)

    def roteiro_confere(self, plano: list[str], ids: list[str]) -> tuple[bool, int]:
        """(roteiro passa no verificador, minutos do turno depois da limpeza)."""
        limpo = eliminar_redundantes(self.tarefa, plano)
        custos = {a.assinatura: a.custo for a in self.tarefa.acoes}
        paradas = roteiro_acs.montar(limpo, self.dados, custos,
                                     roteiro_acs.legenda_para(self.regras))
        minutos = sum(custos[p] for p in limpo)
        texto = (roteiro_acs.imprimir(paradas, self.dados, custo_total=minutos)
                 + "\n\nPLANO COMPLETO\n" + "\n".join(limpo))
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                         encoding="utf-8") as copia:
            copia.write(self._planilha_texto())
        try:
            ok = all(passou for passou, _ in verificar(texto, Path(copia.name), ids))
        finally:
            Path(copia.name).unlink()
        return ok, minutos

    def _planilha_texto(self) -> str:
        """A planilha so com os pacientes deste cenario (para o verificador)."""
        linhas = PLANILHA.read_text(encoding="utf-8").splitlines()
        ids = {p["id"] for p in self.dados["pacientes"]}
        return "\n".join([linhas[0]] + [l for l in linhas[1:] if l.split(",")[0] in ids]) + "\n"


def carregar_dados(pacientes: list[str] | None = None) -> dict:
    dados = ciclo2.ler_dados(str(PLANILHA), MARCAS + ["exige_protecao_respiratoria"])
    if pacientes is not None:
        dados["pacientes"] = [p for p in dados["pacientes"] if p["id"] in pacientes]
        dados["recursos"]["janelas_supervisao_no_turno"] = len(dados["pacientes"])
    return dados


def rota(dados: dict) -> dict:
    ciclo2.garantir_caminho()
    from acsplan.geo import roteirizador
    return roteirizador.roteirizar(dados, semente=0, silencioso=True)


def linhas_toml(arquivo: Path) -> int:
    return sum(1 for l in arquivo.read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.strip().startswith("#"))


def linhas_alteradas(antes: str, depois: str) -> int:
    diff = difflib.unified_diff(antes.splitlines(), depois.splitlines(), lineterm="", n=0)
    return sum(1 for l in diff if l[:1] in "+-" and not l.startswith(("+++", "---")))


def fmt_tempo(e: Execucao | None, limite: float) -> str:
    if e is None:
        return "-"
    if e.sucesso:
        return f"{e.segundos:.1f} s"
    return f"> {limite:g} s" if e.terminou_no_limite else "sem plano"


def fmt_custo(e: Execucao | None) -> str:
    return "-" if e is None or not e.sucesso else str(e.custo)


# ============================================================================
#  tabelas
# ============================================================================

def tabela_a(limite: float, pasta: Path) -> list[str]:
    dados = carregar_dados()
    roteamento = rota(dados)
    planejador = ciclo2.planejador()
    legal = escrever_pddl(planejador.ler_sexp(str(ciclo2.DOMINIO_LEGAL)), ["medicao"])
    base = Cenario(Regras(), dados, roteamento, pasta / "base")
    otimo_base = base.fd(fastdownward.OTIMO, limite) or base.ciclo2("astar-hmax", limite)
    acoes_legais = {a[1]: a for a in base.dominio_arvore[2:]
                    if isinstance(a, list) and a[0] == ":action"}

    linhas = ["| Regra | TOML (linhas) | PDDL alterado (linhas) | Ações novas | Ações modificadas "
              "| Compila | Roteiro conferido | Turno ótimo | Δ turno | Busca ótima |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    print(f"  base: turno ótimo {fmt_custo(otimo_base)} min")
    for arquivo in REGRAS:
        regras = carregar_regras(str(arquivo))
        (pasta / arquivo.stem).mkdir()
        c = Cenario(regras, dados, roteamento, pasta / arquivo.stem)
        compilado = escrever_pddl(c.dominio_arvore, ["medicao"])
        acoes = {a[1]: a for a in c.dominio_arvore[2:] if isinstance(a, list) and a[0] == ":action"}
        novas = len(set(acoes) - set(acoes_legais))
        modificadas = sum(1 for n in acoes_legais if acoes[n] != acoes_legais[n])
        otimo = c.fd(fastdownward.OTIMO, limite) or c.ciclo2("astar-hmax", limite)
        ok, _ = c.roteiro_confere(otimo.plano, [rotulo_regra(arquivo)]) if otimo.sucesso \
            else (False, None)
        delta = (f"+{otimo.custo - otimo_base.custo}" if otimo.sucesso and otimo_base.sucesso
                 else "-")
        linhas.append(
            f"| {arquivo.stem} | {linhas_toml(arquivo)} | {linhas_alteradas(legal, compilado)} "
            f"| {novas} | {modificadas} | sim | {'sim' if ok else 'NÃO'} "
            f"| {fmt_custo(otimo)} | {delta} | {fmt_tempo(otimo, limite)} |")
        print("  " + linhas[-1])
    planejador_otimo = ("Fast Downward, A* com LM-cut" if fastdownward.disponivel()
                        else "planejador do Ciclo 2, A* com h_max")
    return linhas + ["", f"Turno ótimo sem regras: {fmt_custo(otimo_base)} min. "
                         f"Busca ótima: {planejador_otimo}, limite de {limite:g} s."]


def tabela_b(limite: float, pasta: Path) -> list[str]:
    dados = carregar_dados()
    roteamento = rota(dados)
    conjuntos = [("nenhuma", [])] + [
        (f"R1–R{k}" if k > 1 else "R1", REGRAS[:k]) for k in range(1, len(REGRAS) + 1)]
    conjuntos.append(("R1–R7 + 3 do Ciclo 2", REGRAS + [SINTETICAS]))
    linhas = ["| Regras | Combinações sem poda | Ações com poda | Instanciação | Ciclo 2 (h_add) "
              "| FD 1º plano | FD ótimo (LM-cut) |",
              "|---|---|---|---|---|---|---|"]
    for i, (rotulo, arquivos) in enumerate(conjuntos):
        (pasta / f"b{i}").mkdir()
        c = Cenario(juntar(arquivos), dados, roteamento, pasta / f"b{i}")
        h_add = c.ciclo2("astar-hadd", limite)
        primeiro = c.fd(fastdownward.PRIMEIRO, limite)
        otimo = c.fd(fastdownward.OTIMO, limite)

        def celula(e):
            return "-" if e is None else (
                f"{e.custo} min, {e.segundos:.1f} s" if e.sucesso else fmt_tempo(e, limite))
        milhares = lambda n: f"{n:,}".replace(",", ".")
        linhas.append(f"| {rotulo} | {milhares(c.combinacoes_sem_poda())} "
                      f"| {milhares(len(c.tarefa.acoes))} | {c.segundos_instanciacao:.2f} s "
                      f"| {celula(h_add)} | {celula(primeiro)} | {celula(otimo)} |")
        print("  " + linhas[-1])
    return linhas + ["", f"Limite de {limite:g} s por busca. Os tempos do Fast Downward incluem "
                         f"a tradução do PDDL. Custos antes da limpeza do plano."]


def tabela_c(limite: float, pasta: Path) -> list[str]:
    grupos = [["p7"], ["p6", "p8"], ["p3", "p6", "p7"], ["p3", "p5", "p6", "p7", "p8"], None]
    regras = juntar(REGRAS)
    linhas = ["| Pacientes | Ações | Ciclo 2 (h_add) | FD 1º plano | FD ótimo (LM-cut) |",
              "|---|---|---|---|---|"]
    for i, grupo in enumerate(grupos):
        dados = carregar_dados(grupo)
        (pasta / f"c{i}").mkdir()
        c = Cenario(regras, dados, rota(dados), pasta / f"c{i}")
        h_add = c.ciclo2("astar-hadd", limite)
        primeiro = c.fd(fastdownward.PRIMEIRO, limite)
        otimo = c.fd(fastdownward.OTIMO, limite)

        def celula(e):
            return "-" if e is None else (
                f"{e.custo} min, {e.segundos:.1f} s" if e.sucesso else fmt_tempo(e, limite))
        nomes = ", ".join(grupo) if grupo else "todos os 10"
        linhas.append(f"| {len(dados['pacientes'])} ({nomes}) | {len(c.tarefa.acoes)} "
                      f"| {celula(h_add)} | {celula(primeiro)} | {celula(otimo)} |")
        print("  " + linhas[-1])
    return linhas + ["", f"Sete regras ativas. Limite de {limite:g} s por busca."]


def main() -> int:
    parser = argparse.ArgumentParser(prog="acs.py medicoes")
    parser.add_argument("--rapido", action="store_true",
                        help="limites de 5 s, para conferir o script")
    parser.add_argument("--limite", type=float, default=120.0)
    args = parser.parse_args()
    limite = 5.0 if args.rapido else args.limite

    secoes = [
        ("A. Cada regra sozinha", tabela_a,
         "Esforço: linhas de TOML (sem comentários) que a pessoa escreve, contra "
         "linhas do domínio PDDL que o compilador altera. Turno ótimo no turno "
         "completo da planilha de avaliação; Δ em relação ao turno sem regras."),
        ("B. Regras acumuladas", tabela_b,
         "As regras entram uma a uma (R1, R1–R2, ...), e por fim junto com as três "
         "regras sintéticas do Ciclo 2. Combinações sem poda: o que a instanciação "
         "original do Ciclo 2 testaria."),
        ("C. Sete regras, número de pacientes", tabela_c,
         "Pacientes escolhidos para que as marcas apareçam; janelas de supervisão "
         "iguais ao número de pacientes."),
    ]
    saida = ["# Resultados das medições (etapa 8.4)", "",
             f"Gerado por `python3 acs.py medicoes` em {date.today().isoformat()}, "
             f"Python {platform.python_version()}, "
             f"Fast Downward {'instalado' if fastdownward.disponivel() else 'NÃO instalado'}. "
             "Planilha de avaliação, mesma rota em todas as execuções.", ""]
    with tempfile.TemporaryDirectory() as temporaria:
        for i, (titulo, funcao, nota) in enumerate(secoes):
            print(f"\n{titulo}")
            pasta = Path(temporaria) / f"s{i}"
            pasta.mkdir()
            (pasta / "base").mkdir()
            saida += [f"## {titulo}", "", nota, ""] + funcao(limite, pasta) + [""]
    if not args.rapido:
        SAIDA.write_text("\n".join(saida), encoding="utf-8")
        print(f"\nGravado em {SAIDA.relative_to(RAIZ.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
