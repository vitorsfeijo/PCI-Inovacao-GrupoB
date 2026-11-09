"""
Teste com usuario (8.5): registro da sessao no assistente e conferidor.
As sessoes aqui sao participantes simulados, com nomes diferentes dos do
gabarito (que devem ser aceitos) e erros de proposito (que devem aparecer).
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from compilador.assistente import main as assistente
from compilador.regras import carregar_regras

from testes.teste_usuario import GABARITOS, comparar, main as conferir, resumo_do_registro

# Respostas de um participante, tarefa por tarefa (fluxo atual do assistente).
SESSOES = {
    "t1": ["2", "ligar o tablet", "s", "tablet-ligado", "2", "n", "6", "", "5"],
    "t2": ["1", "lencos", "10", "3", "", "",
           "2", "higienizar-manguito", "manguito-higienizado", "1", "2", "", "1", "", "5"],
    "t3": ["1", "luvas", "6", "3", "", "",
           "2", "calcar-luvas", "luvas-calcadas", "1", "2", "", "", "",
           "4", "2", "luvas-ferida", "ferida-exposta", "1", "5", "5"],
}


def simular(pasta: Path, tarefa: str, respostas: list[str]) -> tuple[Path, Path]:
    toml, registro = pasta / f"{tarefa}.toml", pasta / f"{tarefa}.jsonl"
    fila = iter(respostas)

    def entrada(_pergunta: str) -> str:
        try:
            return next(fila)
        except StopIteration:
            raise EOFError from None

    codigo = assistente([str(toml), "--registro", str(registro)],
                        entrada=entrada, escrever=lambda _t: None)
    assert codigo == 0, f"a sessão simulada de {tarefa} não terminou"
    return toml, registro


class TestTesteComUsuario(unittest.TestCase):

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.dir = Path(self.pasta.name)

    def tearDown(self):
        self.pasta.cleanup()

    def test_tres_tarefas_certas_com_outros_nomes(self):
        for tarefa, respostas in SESSOES.items():
            toml, registro = simular(self.dir, tarefa, respostas)
            saida = io.StringIO()
            with redirect_stdout(saida):
                codigo = conferir([str(toml), "--tarefa", tarefa, "--registro", str(registro)])
            self.assertEqual(codigo, 0, saida.getvalue())
            self.assertIn(f"{tarefa}: CERTA", saida.getvalue())

    def test_registro_conta_recusas(self):
        # "ligar o tablet" tem espaço: o assistente recusa e oferece a sugestão
        _, registro = simular(self.dir, "t1", ["2", "ligar o tablet", "n", "ligar-tablet",
                                               "tablet-ligado", "2", "n", "6", "", "5"])
        resumo = resumo_do_registro(registro)
        self.assertGreaterEqual(resumo["respostas"], 9)
        self.assertTrue(resumo["terminou"])
        self.assertFalse(resumo["cancelou"])
        eventos = [json.loads(l) for l in registro.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all({"t", "tipo", "texto"} <= e.keys() for e in eventos))

    def test_recusa_de_valor_invalido(self):
        respostas = list(SESSOES["t2"])
        respostas[2:3] = ["dez", "10"]                     # capacidade: texto, depois número
        _, registro = simular(self.dir, "t2", respostas)
        resumo = resumo_do_registro(registro)
        self.assertEqual(resumo["recusas"], 1)
        self.assertIn("digite um número inteiro", resumo["textos das recusas"][0])

    def test_erros_sao_apontados(self):
        respostas = list(SESSOES["t2"])
        respostas[2] = "8"                                 # capacidade errada
        respostas[12] = "1,4"                              # procedimento a mais
        toml, _ = simular(self.dir, "t2", respostas)
        difs = comparar(carregar_regras(str(toml)),
                        carregar_regras(str(GABARITOS / "gabarito-t2.toml")))
        texto = "\n".join(difs)
        self.assertIn("capacidade: esperado 10, escrito 8", texto)
        self.assertIn("exigido antes de: esperado ['pressao'], escrito ['medicacao', 'pressao']",
                      texto)

    def test_exigencia_no_lugar_errado(self):
        # T3 feita como exigência no início da visita, e não antes da pesagem
        respostas = list(SESSOES["t3"])
        respostas[15:] = ["1", "luvas-ferida", "ferida-exposta", "1", "", "", "5"]
        toml, _ = simular(self.dir, "t3", respostas)
        difs = comparar(carregar_regras(str(toml)),
                        carregar_regras(str(GABARITOS / "gabarito-t3.toml")))
        self.assertTrue(any("quando: esperado 'antes de antropometria', escrito "
                            "'início da visita'" in d for d in difs), difs)

    def test_cancelar_fica_registrado(self):
        toml, registro = self.dir / "t1.toml", self.dir / "t1.jsonl"
        fila = iter(["2", "ligar-tablet"])

        def entrada(_):
            try:
                return next(fila)
            except StopIteration:
                raise EOFError from None
        assistente([str(toml), "--registro", str(registro)], entrada=entrada,
                   escrever=lambda _t: None)
        self.assertTrue(resumo_do_registro(registro)["cancelou"])
        self.assertFalse(toml.exists())


if __name__ == "__main__":
    unittest.main()
