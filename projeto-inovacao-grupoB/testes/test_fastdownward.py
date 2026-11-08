"""
Fast Downward como planejador opcional.

Os testes que precisam dele sao pulados quando o pacote nao esta instalado.
Para roda-los:

    pip install up-fast-downward
    python -m unittest testes.test_fastdownward
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from compilador import ciclo2, fastdownward
from compilador.instanciacao import tarefa as criar_tarefa
from compilador.planejar import main as planejar

RAIZ = Path(__file__).resolve().parents[1]
AVALIACAO = RAIZ / "exemplos" / "avaliacao"
PLANILHA = AVALIACAO / "microarea-avaliacao.csv"
REGRAS = sorted((AVALIACAO / "regras").glob("*.toml"))

com_fd = unittest.skipUnless(fastdownward.disponivel(),
                             f"Fast Downward não instalado ({fastdownward.INSTALACAO})")


def rodar(*argumentos: str) -> tuple[int, str, str]:
    saida, erros = io.StringIO(), io.StringIO()
    with redirect_stdout(saida), redirect_stderr(erros):
        codigo = planejar(list(argumentos))
    return codigo, saida.getvalue(), erros.getvalue()


def pddl(pasta: str, *regras: Path) -> tuple[str, str]:
    """Gera domínio e problema da planilha de avaliação (10 pacientes)."""
    toml = Path(pasta) / "regras.toml"
    toml.write_text("".join(r.read_text(encoding="utf-8") for r in regras), encoding="utf-8")
    saida = Path(pasta) / "pddl"
    argumentos = ([str(toml)] if regras else []) + [
        "--dados", str(PLANILHA), "--sem-selecao", "--planejador", "ciclo2",
        "--estrategia", "gbfs", "--limite", "0.01", "--salvar-pddl", str(saida)]
    rodar(*argumentos)
    return str(saida / "dominio.pddl"), str(saida / "problema.pddl")


class TestSemFastDownward(unittest.TestCase):

    @unittest.skipIf(fastdownward.disponivel(), "o Fast Downward está instalado")
    def test_exigir_sem_ter_e_erro(self):
        codigo, _, info = rodar("--instancia-sintetica", "2", "1",
                                "--planejador", "fast-downward")
        self.assertEqual(codigo, 1)
        self.assertIn("pip install up-fast-downward", info)

    @unittest.skipIf(fastdownward.disponivel(), "o Fast Downward está instalado")
    def test_auto_cai_no_ciclo2(self):
        codigo, _, info = rodar("--instancia-sintetica", "2", "1")
        self.assertEqual(codigo, 0, info)
        self.assertIn("usando o planejador do Ciclo 2", info)

    def test_forcar_o_ciclo2(self):
        codigo, _, info = rodar("--instancia-sintetica", "2", "1", "--planejador", "ciclo2")
        self.assertEqual(codigo, 0, info)
        self.assertIn("Busca: planejador do Ciclo 2", info)


@com_fd
class TestComFastDownward(unittest.TestCase):

    def test_otimo_igual_ao_h_max(self):
        # ótimos medidos com o h_max do Ciclo 2: sem regra 386, R4 395 (10 pacientes)
        for regras, otimo in (((), 386), ((REGRAS[3],), 395)):
            with tempfile.TemporaryDirectory() as pasta:
                dominio, problema = pddl(pasta, *regras)
                tarefa = criar_tarefa(dominio, problema)
                r = fastdownward.resolver(dominio, problema, tarefa,
                                          configuracao=fastdownward.OTIMO, limite_segundos=60)
            self.assertTrue(r.sucesso, r.motivo)
            self.assertEqual(r.custo, otimo)

    def test_sete_regras_dez_pacientes(self):
        # o caso em que o planejador do Ciclo 2 não termina
        with tempfile.TemporaryDirectory() as pasta:
            dominio, problema = pddl(pasta, *REGRAS)
            tarefa = criar_tarefa(dominio, problema)
            r = fastdownward.resolver(dominio, problema, tarefa,
                                      configuracao=fastdownward.PRIMEIRO, limite_segundos=60)
        self.assertTrue(r.sucesso, r.motivo)
        self.assertEqual(fastdownward.validar(tarefa, r.plano), r.custo)
        self.assertLess(r.segundos, 30)

    def test_planejar_e_roteiro(self):
        from testes.roteiros_avaliacao import verificar
        with tempfile.TemporaryDirectory() as pasta:
            toml = Path(pasta) / "todas.toml"
            toml.write_text("".join(r.read_text(encoding="utf-8") for r in REGRAS),
                            encoding="utf-8")
            codigo, roteiro, info = rodar(str(toml), "--dados", str(PLANILHA),
                                          "--sem-selecao", "--estrategia", "gbfs",
                                          "--mostrar-plano")
        self.assertEqual(codigo, 0, info)
        self.assertIn("Busca: Fast Downward", info)
        falhas = [d for ok, d in verificar(roteiro, PLANILHA,
                                           ["r1", "r2", "r3", "r4", "r5", "r6", "r7"]) if not ok]
        self.assertEqual(falhas, [])

    def test_turno_impossivel_e_provado(self):
        ciclo2.garantir_caminho()
        from acsplan.dados import gerador
        dados = gerador.gerar(3, 1)
        dados["agente"]["curso_tecnico_concluido"] = False
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "microarea.json"
            arquivo.write_text(json.dumps(dados), encoding="utf-8")
            codigo, _, info = rodar("--dados", str(arquivo))
        self.assertEqual(codigo, 1)
        self.assertIn("nenhuma sequência de ações cumpre as regras", info)


if __name__ == "__main__":
    unittest.main()
