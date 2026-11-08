"""
Verificacao dos roteiros com as regras da avaliacao.

Le um roteiro gerado por `python -m compilador planejar` e confere, para cada
regra ativa, o que DEVERIA acontecer, a partir das marcas e procedimentos de
cada paciente na planilha:

    R1 lancetas   reposicao de lancetas quando ha mais glicemias que lancetas
    R2 termometro "Desinfetar o termometro" so em quem afere temperatura
    R3 balanca    "Zerar a balanca" uma unica vez, na primeira pesagem
    R4 avental    avental e conferencia so nos acamados
    R5 N95        N95 e conferencia so em suspeita de tuberculose
    R6 luvas      luvas so em gestante que faz glicemia
    R7 algodao    reposicao de algodao quando o gasto passa da carga

Uso:

    python -m testes.roteiros_avaliacao ROTEIRO.txt PLANILHA.csv r1 r2 ...

O roteiro deve ter sido gerado com --mostrar-plano (algumas conferencias
olham o plano). Devolve 0 se tudo confere.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


def paradas(texto: str) -> list[dict]:
    """Roteiro -> [{nome, tarefas, repor}] na ordem das visitas."""
    roteiro = texto.split("PLANO COMPLETO")[0]
    resultado: list[dict] = []
    for linha in roteiro.splitlines():
        m = re.match(r"^  (\d+)\. (.+?)(  \(|$)", linha)
        if m:
            resultado.append({"nome": m.group(2).strip(), "tarefas": [], "repor": ""})
        elif resultado and "[ ]" in linha:
            resultado[-1]["tarefas"].append(linha.split("[ ]", 1)[1].strip())
        elif resultado and "PASSAR NA UNIDADE" in linha:
            resultado[-1]["repor"] += " " + linha.split("repor", 1)[1].strip()
    return resultado


def verificar(texto: str, planilha: Path, regras: list[str]) -> list[tuple[bool, str]]:
    """Lista de (passou, descricao). `regras`: prefixos como "r1", "r4"."""
    with planilha.open(encoding="utf-8") as arquivo:
        pacientes = {r["nome"]: r for r in csv.DictReader(arquivo)}
    lista = paradas(texto)
    visitados = {p["nome"] for p in lista}
    plano = texto.split("PLANO COMPLETO", 1)[1] if "PLANO COMPLETO" in texto else ""
    reposicoes = " ".join(p["repor"] for p in lista)

    def ids(coluna_a: str, coluna_b: str | None = None) -> set[str]:
        return {n for n, r in pacientes.items() if n in visitados and r[coluna_a] == "sim"
                and (coluna_b is None or r[coluna_b] == "sim")}

    def com(tarefa: str) -> set[str]:
        return {p["nome"] for p in lista if tarefa in p["tarefas"]}

    def igual(tarefa: str, esperado: set[str], rotulo: str):
        obtido = com(tarefa)
        return (obtido == esperado,
                f"{rotulo}: esperado {sorted(esperado)}, obtido {sorted(obtido)}")

    resultado = []
    internos = [t for p in lista for t in p["tarefas"] if re.search(r"[a-z]+-[a-z]+", t)]
    resultado.append((not internos, f"sem nomes internos no roteiro {internos or ''}"))
    glicemias = len(ids("requer_glicemia"))

    for regra in regras:
        if regra == "r1" and glicemias > 4:
            resultado.append(("lancetas" in reposicoes,
                              f"R1: {glicemias} glicemias, 4 lancetas por carga: reposição"))
        if regra == "r2":
            resultado.append(igual("Desinfetar o termômetro", ids("requer_temperatura"),
                                   "R2: desinfetar só em quem afere temperatura"))
        if regra == "r3":
            zerar = [p["nome"] for p in lista if "Zerar a balança portátil" in p["tarefas"]]
            pesagens = [p["nome"] for p in lista
                        if pacientes[p["nome"]]["requer_antropometria"] == "sim"]
            esperado = pesagens[:1]
            resultado.append((zerar == esperado,
                              f"R3: zerar uma vez, na primeira pesagem {esperado}: {zerar}"))
        if regra == "r4":
            acamados = ids("exige_avental")
            resultado.append(igual("Vestir avental descartável", acamados,
                                   "R4: avental só nos acamados"))
            resultado.append(igual("Conferir o avental antes de entrar", acamados,
                                   "R4: conferência do avental"))
            if len(acamados) > 1:
                resultado.append(("aventais" in reposicoes,
                                  "R4: 1 avental por carga, 2 acamados: reposição"))
        if regra == "r5":
            tb = ids("suspeita_tuberculose")
            resultado.append(igual("Colocar máscara N95", tb, "R5: N95 só em suspeita de TB"))
            resultado.append(igual("Conferir a N95 antes de entrar", tb, "R5: conferência"))
        if regra == "r6":
            alvo = ids("gestante", "requer_glicemia")
            resultado.append(igual("Calçar luvas de procedimento", alvo,
                                   "R6: luvas só em gestante com glicemia"))
            if alvo and plano:
                resultado.append(("medir-glicemia-capilar-luvas-gestante" in plano,
                                  "R6: o plano usa a versão da glicemia com luvas"))
        if regra == "r7":
            gasto = 2 * glicemias + len(ids("requer_temperatura"))
            if gasto > 6:
                resultado.append(("algodão" in reposicoes,
                                  f"R7: {gasto} unidades de algodão, 6 por carga: reposição"))
    return resultado


def main(argv: list[str]) -> int:
    roteiro, planilha, *regras = argv
    texto = Path(roteiro).read_text(encoding="utf-8")
    if "ROTEIRO DO TURNO" not in texto:
        print("FALHA: o arquivo não contém roteiro")
        return 1
    falhas = 0
    for passou, descricao in verificar(texto, Path(planilha), regras):
        print(f"  [{'ok' if passou else 'FALHA'}] {descricao}")
        falhas += not passou
    print(f"{falhas} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
