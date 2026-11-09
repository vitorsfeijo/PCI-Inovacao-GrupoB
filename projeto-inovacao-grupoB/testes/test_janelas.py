"""
Planejamento por janelas (compilador/janelas.py) e o seu uso no `auto`.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from compilador import ciclo2, fastdownward
from compilador.instanciacao import tarefa as criar_tarefa
from compilador.janelas import planejar_por_janelas
from compilador.planejar import main as planejar

RAIZ = Path(__file__).resolve().parents[1]
SINTETICAS = RAIZ / "exemplos" / "sinteticas-ciclo2.toml"
AVALIACAO = RAIZ / "exemplos" / "avaliacao"
REGRAS = sorted((AVALIACAO / "regras").glob("r*.toml"))


def rodar(*argumentos: str) -> tuple[int, str, str]:
    saida, erros = io.StringIO(), io.StringIO()
    with redirect_stdout(saida), redirect_stderr(erros):
        codigo = planejar(list(argumentos))
    return codigo, saida.getvalue(), erros.getvalue()


def cenario(pasta: str, *args: str):
    """Grava domínio e problema e devolve (tarefa, caminhos, rota)."""
    saida = Path(pasta) / "pddl"
    rodar(*args, "--planejador", "ciclo2", "--estrategia", "gbfs", "--limite", "0.01",
          "--salvar-pddl", str(saida))
    dominio, problema = str(saida / "dominio.pddl"), str(saida / "problema.pddl")
    arvore = ciclo2.planejador().ler_sexp(problema)
    init = next(s for s in arvore if isinstance(s, list) and s and s[0] == ":init")
    seguinte = {f[1]: f[2] for f in init[1:] if isinstance(f, list) and f[0] == "proxima-parada"}
    rota, atual = [], "ubs"
    while seguinte.get(atual, "ubs-fim") != "ubs-fim":
        atual = seguinte[atual]
        rota.append(atual.replace("casa-", ""))
    return criar_tarefa(dominio, problema), (dominio, problema), rota


class TestJanelasSemFastDownward(unittest.TestCase):

    def test_plano_valido_e_perto_do_otimo(self):
        with tempfile.TemporaryDirectory() as pasta:
            tarefa, caminhos, rota = cenario(pasta, str(SINTETICAS),
                                             "--instancia-sintetica", "4", "2")
            r = planejar_por_janelas(tarefa, *caminhos, rota, "acs1", tamanho=2,
                                     usar_fd=False, limite_janela=30)
            otimo = ciclo2.planejador().resolver(tarefa, "astar-hmax", limite_segundos=60)
        self.assertTrue(r.sucesso, r.motivo)
        self.assertEqual(fastdownward.validar(tarefa, r.plano), r.custo)
        self.assertTrue(otimo.sucesso)
        self.assertGreaterEqual(r.custo, otimo.custo)
        self.assertLessEqual(r.custo, otimo.custo * 1.1)

    def test_estrategia_janelas_na_linha_de_comando(self):
        codigo, roteiro, info = rodar(str(SINTETICAS), "--instancia-sintetica", "3", "1",
                                      "--planejador", "ciclo2", "--estrategia", "janelas",
                                      "--janela", "2")
        self.assertEqual(codigo, 0, info)
        self.assertIn("janelas (k=2)", info)
        self.assertIn("ROTEIRO DO TURNO", roteiro)


class TestAutoEscolheOMelhor(unittest.TestCase):

    def test_beco_sem_saida_das_janelas_cai_no_plano_global(self):
        # simula as janelas caindo num beco sem saida (ex.: supervisao esgotada)
        from acsplan.logica.planejador import Resultado
        falha = Resultado(False, [], 0, 0, 0, 0.0, "objetivo inalcancavel (deteccao na relaxacao)")
        with mock.patch("compilador.planejar.planejar_por_janelas", return_value=falha):
            codigo, roteiro, info = rodar(str(SINTETICAS), "--orcamento", "240",
                                          "--planejador", "ciclo2", "--limite", "8")
        self.assertEqual(codigo, 0, info)
        self.assertIn("janelas (k=1): sem plano", info)
        self.assertIn("astar-hadd", info.split("[4] Plano")[1])
        self.assertIn("ROTEIRO DO TURNO", roteiro)


@unittest.skipUnless(fastdownward.disponivel(),
                     f"Fast Downward não instalado ({fastdownward.INSTALACAO})")
class TestJanelasComFastDownward(unittest.TestCase):

    def test_r1_a_r4_quase_otimo(self):
        # ótimo provado (LM-cut, 31 s): 401 min
        with tempfile.TemporaryDirectory() as pasta:
            toml = Path(pasta) / "r1r4.toml"
            toml.write_text("".join(r.read_text(encoding="utf-8") for r in REGRAS[:4]),
                            encoding="utf-8")
            tarefa, caminhos, rota = cenario(pasta, str(toml), "--dados",
                                             str(AVALIACAO / "microarea-avaliacao.csv"),
                                             "--sem-selecao")
            r = planejar_por_janelas(tarefa, *caminhos, rota, "acs1", tamanho=3,
                                     usar_fd=True, limite_janela=30)
        self.assertTrue(r.sucesso, r.motivo)
        self.assertEqual(fastdownward.validar(tarefa, r.plano), r.custo)
        self.assertLessEqual(r.custo, 405)


if __name__ == "__main__":
    unittest.main()
