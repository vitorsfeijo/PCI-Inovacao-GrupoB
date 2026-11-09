"""
Experimento de qualidade dos planos: quao longe do otimo fica cada metodo.

    python -m testes.qualidade_planos            # os quatro casos (cerca de 40 min)
    python -m testes.qualidade_planos --rapido   # so o caso menor, limites curtos

Precisa do Fast Downward (pip install up-fast-downward). Compara, na planilha
de avaliacao, as configuracoes do Fast Downward (primeiro plano, LAMA,
portfolio de 2023, otimo com LM-cut) com o planejamento por janelas de
tamanho 1 a 4. Custos depois da limpeza do plano. O resultado de cada
execucao vai para a saida padrao.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from compilador import ciclo2, fastdownward  # noqa: E402
from compilador.instanciacao import tarefa as criar_tarefa  # noqa: E402
from compilador.janelas import planejar_por_janelas  # noqa: E402
from compilador.limpeza import eliminar_redundantes  # noqa: E402

AVALIACAO = RAIZ / "exemplos" / "avaliacao"
PLANILHA = AVALIACAO / "microarea-avaliacao.csv"
REGRAS = sorted((AVALIACAO / "regras").glob("r*.toml"))

# (rotulo, quantas regras, pacientes ou None para todos os 10)
CASOS = [("R1–R4, 10 pacientes", 4, None),
         ("7 regras, p3 p6 p7", 7, ["p3", "p6", "p7"]),
         ("7 regras, p6 p7 p8", 7, ["p6", "p7", "p8"]),
         ("7 regras, 10 pacientes", 7, None)]
CONFIGS = [("1º plano (lama-first)", ["--alias", "lama-first"]),
           ("LAMA", ["--alias", "lama"]),
           ("portfólio 2023", ["--alias", "seq-sat-fdss-2023"]),
           ("ótimo (LM-cut)", ["--alias", "seq-opt-lmcut"])]


def preparar(pasta: Path, n_regras: int, pacientes: list[str] | None):
    """Planilha (eventualmente reduzida) + regras -> PDDL, tarefa e rota."""
    planilha = PLANILHA
    if pacientes:
        linhas = PLANILHA.read_text(encoding="utf-8").splitlines()
        planilha = pasta / "microarea.csv"
        planilha.write_text("\n".join([linhas[0]] + [l for l in linhas[1:]
                                                     if l.split(",")[0] in pacientes]) + "\n",
                            encoding="utf-8")
        (pasta / "microarea.json").write_text(
            PLANILHA.with_suffix(".json").read_text(encoding="utf-8"), encoding="utf-8")
    regras = pasta / "regras.toml"
    regras.write_text("".join(r.read_text(encoding="utf-8") for r in REGRAS[:n_regras]),
                      encoding="utf-8")
    subprocess.run([sys.executable, "-m", "compilador", "planejar", str(regras), "--dados",
                    str(planilha), "--sem-selecao", "--planejador", "ciclo2", "--estrategia",
                    "gbfs", "--limite", "0.01", "--salvar-pddl", str(pasta / "pddl")],
                   cwd=RAIZ, capture_output=True)
    dominio, problema = str(pasta / "pddl" / "dominio.pddl"), str(pasta / "pddl" / "problema.pddl")
    arvore = ciclo2.planejador().ler_sexp(problema)
    init = next(s for s in arvore if isinstance(s, list) and s and s[0] == ":init")
    seguinte = {f[1]: f[2] for f in init[1:] if isinstance(f, list) and f[0] == "proxima-parada"}
    rota, atual = [], "ubs"
    while seguinte.get(atual, "ubs-fim") != "ubs-fim":
        atual = seguinte[atual]
        rota.append(atual.replace("casa-", ""))
    return dominio, problema, criar_tarefa(dominio, problema), rota


def custo_limpo(tarefa, plano: list[str]) -> int:
    return fastdownward.validar(tarefa, eliminar_redundantes(tarefa, plano))


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m testes.qualidade_planos")
    parser.add_argument("--rapido", action="store_true")
    args = parser.parse_args()
    if not fastdownward.disponivel():
        print(f"Precisa do Fast Downward: {fastdownward.INSTALACAO}")
        return 1
    casos = CASOS[1:2] if args.rapido else CASOS
    limite = 10 if args.rapido else 60
    driver = str(fastdownward.driver())
    for rotulo, n_regras, pacientes in casos:
        with tempfile.TemporaryDirectory() as temporaria:
            pasta = Path(temporaria)
            dominio, problema, tarefa, rota = preparar(pasta, n_regras, pacientes)
            print(f"\n{rotulo} ({len(tarefa.acoes)} ações)", flush=True)
            for nome, opcoes in CONFIGS:
                lim = limite * 2 if "ótimo" in nome else limite
                inicio = time.perf_counter()
                subprocess.run([sys.executable, driver, "--overall-time-limit", str(lim),
                                "--plan-file", str(pasta / "plano"), *opcoes, dominio, problema],
                               cwd=pasta, capture_output=True)
                segundos = time.perf_counter() - inicio
                arquivo = fastdownward._ultimo_plano(pasta)
                if arquivo is None:
                    print(f"  {nome:24} sem plano em {segundos:.0f} s", flush=True)
                    continue
                custo = custo_limpo(tarefa, fastdownward._ler_plano(arquivo))
                for velho in pasta.glob("plano*"):
                    velho.unlink()
                print(f"  {nome:24} {custo} min  ({segundos:.1f} s)", flush=True)
            for k in (1, 2, 3, 4):
                r = planejar_por_janelas(tarefa, dominio, problema, rota, "acs1", tamanho=k,
                                         usar_fd=True, limite_janela=limite / 2)
                texto = (f"{custo_limpo(tarefa, r.plano)} min" if r.sucesso
                         else f"sem plano ({r.motivo})")
                print(f"  {'janelas k=' + str(k):24} {texto}  ({r.segundos:.1f} s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
