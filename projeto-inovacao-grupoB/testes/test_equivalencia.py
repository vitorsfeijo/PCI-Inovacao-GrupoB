"""
Teste de equivalencia: a higienizacao escrita como modelos reproduz a
higienizacao do dominio estendido do Ciclo 2.

Versao rapida, com poucas instancias. O relatorio completo e:

    python -m testes.equivalencia
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from compilador import carregar_regras

from testes.equivalencia import (EXEMPLOS, com_capacidade, comparar_instancia,
                                 diferencas_estruturais, preparar_dominios)

MANTER = {"higienizacao"}


class TestEquivalenciaHigienizacao(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.regras = carregar_regras(str(EXEMPLOS / "higienizacao.toml"))
        cls.compilado, cls.estendido = preparar_dominios(cls.regras, MANTER)

    def test_estrutura_igual(self):
        self.assertEqual(diferencas_estruturais(self.compilado, self.estendido), [])

    def test_projecao_remove_as_outras_regras(self):
        texto = str(self.estendido)
        for trecho in ("mascara", "coletor", "protecao"):
            self.assertNotIn(trecho, texto)

    def test_comportamento_com_alcool_suficiente(self):
        c = comparar_instancia(self.regras, self.compilado, self.estendido, 3, 3)
        self.assertTrue(c.equivalente, c)
        self.assertEqual(c.reposicoes, 0)

    def test_comportamento_com_falta_de_alcool(self):
        regras = com_capacidade(self.regras, 2)
        c = comparar_instancia(regras, self.compilado, self.estendido, 3, 1)
        self.assertTrue(c.equivalente, c)
        self.assertGreater(c.reposicoes, 0)


class TestEquivalenciaDetectaDiferencas(unittest.TestCase):
    """Controle negativo: regras alteradas de proposito NAO podem passar."""

    @classmethod
    def setUpClass(cls):
        cls.regras = carregar_regras(str(EXEMPLOS / "higienizacao.toml"))

    def _diferencas(self, **mudancas) -> list[str]:
        preparo = replace(self.regras.preparos[0], **mudancas)
        regras = replace(self.regras, preparos=(preparo,))
        compilado, estendido = preparar_dominios(regras, MANTER)
        return diferencas_estruturais(compilado, estendido)

    def test_procedimento_a_menos(self):
        difs = self._diferencas(exigido_antes_de=("pressao", "glicemia", "medicacao",
                                                  "antropometria"))
        self.assertEqual(len(difs), 1)
        self.assertIn("aferir-temperatura-axilar", difs[0])

    def test_nao_desfeito_ao_sair(self):
        difs = self._diferencas(desfeito_ao_sair=False)
        self.assertEqual(len(difs), 2)

    def test_custo_diferente(self):
        difs = self._diferencas(custo=3)
        self.assertEqual(len(difs), 1)
        self.assertIn("custo", difs[0])

    def test_custo_diferente_muda_o_comportamento(self):
        preparo = replace(self.regras.preparos[0], custo=3)
        regras = replace(self.regras, preparos=(preparo,))
        compilado, estendido = preparar_dominios(regras, MANTER)
        c = comparar_instancia(regras, compilado, estendido, 3, 3)
        self.assertFalse(c.equivalente)


if __name__ == "__main__":
    unittest.main()
