"""
Teste de equivalencia com o dominio estendido do Ciclo 2:

    parcial   a higienizacao escrita como modelos reproduz a higienizacao do
              estendido (projecao, sem mascara e coletor)
    completo  as tres regras sinteticas reproduzem o estendido inteiro, e o
              pipeline compilado se comporta como o pipeline do Ciclo 2

Versao rapida, com poucas instancias. O relatorio completo e:

    python -m testes.equivalencia
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from compilador import NOME_PADRAO, carregar_regras, ciclo2, compilar_dominio

from testes.equivalencia import (EXEMPLOS, acoes_equivalentes, com_capacidade,
                                 comparar_instancia, comparar_pipeline_completo,
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



# ============================================================================
#  EQUIVALENCIA COMPLETA: as tres regras sinteticas x dominio estendido
# ============================================================================


def _compilar(regras):
    ler = ciclo2.planejador().ler_sexp
    return compilar_dominio(ler(str(ciclo2.DOMINIO_LEGAL)), regras, nome=NOME_PADRAO)


def _estendido():
    return ciclo2.planejador().ler_sexp(str(ciclo2.DOMINIO_ESTENDIDO))


class TestEquivalenciaCompleta(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.regras = carregar_regras(str(EXEMPLOS / "sinteticas-ciclo2.toml"))
        cls.compilado = _compilar(cls.regras)

    def test_estrutura_igual_ao_estendido_completo(self):
        self.assertEqual(diferencas_estruturais(self.compilado, _estendido()), [])

    def test_pipeline_com_paciente_que_exige_mascara(self):
        c = comparar_pipeline_completo(self.regras, self.compilado, 2, 5)
        self.assertEqual(c.marcados, 1)
        self.assertTrue(c.equivalente, c)

    def test_pipeline_com_recursos_escassos(self):
        c = comparar_pipeline_completo(self.regras, self.compilado, 3, 3,
                                       capacidades={"alcool": 2, "mascaras": 1,
                                                    "coletor": 2})
        self.assertGreater(c.reposicoes, 0)
        self.assertTrue(c.equivalente, c)

    def test_pipeline_com_falta_de_mascara(self):
        # semente 2 tem dois pacientes que exigem mascara; com uma por carga,
        # o plano precisa repor na UBS
        c = comparar_pipeline_completo(self.regras, self.compilado, 4, 2,
                                       capacidades={"mascaras": 1},
                                       limite_segundos=120)
        self.assertEqual(c.marcados, 2)
        self.assertGreater(c.reposicoes, 0)
        self.assertTrue(c.equivalente, c)


class TestRenomeacaoDeVariaveis(unittest.TestCase):

    def setUp(self):
        self.acao = [":action", "a", ":parameters", ["?x", "-", "nivel", "?y", "-", "nivel"],
                     ":precondition", ["and", ["prox", "?y", "?x"], ["r", "?x"]],
                     ":effect", ["and", ["not", ["r", "?x"]], ["r", "?y"]]]

    def test_mesma_acao_com_outros_nomes(self):
        renomeada = [":action", "a", ":parameters", ["?c", "-", "nivel", "?c-1", "-", "nivel"],
                     ":precondition", ["and", ["r", "?c"], ["prox", "?c-1", "?c"]],
                     ":effect", ["and", ["r", "?c-1"], ["not", ["r", "?c"]]]]
        self.assertTrue(acoes_equivalentes(self.acao, renomeada))

    def test_papeis_trocados_nao_sao_equivalentes(self):
        trocada = [":action", "a", ":parameters", ["?c", "-", "nivel", "?c-1", "-", "nivel"],
                   ":precondition", ["and", ["r", "?c"], ["prox", "?c", "?c-1"]],
                   ":effect", ["and", ["r", "?c-1"], ["not", ["r", "?c"]]]]
        self.assertFalse(acoes_equivalentes(self.acao, trocada))


class TestEquivalenciaCompletaDetectaDiferencas(unittest.TestCase):
    """Controle negativo dos modelos D e E."""

    @classmethod
    def setUpClass(cls):
        cls.regras = carregar_regras(str(EXEMPLOS / "sinteticas-ciclo2.toml"))

    def _diferencas(self, regras) -> list[str]:
        return diferencas_estruturais(_compilar(regras), _estendido())

    def test_sem_o_consumo_do_coletor(self):
        difs = self._diferencas(replace(self.regras, consumos=()))
        self.assertEqual(len(difs), 1)
        self.assertIn("medir-glicemia-capilar", difs[0])

    def test_consumo_no_procedimento_errado(self):
        consumo = replace(self.regras.consumos[0], procedimento="pressao")
        difs = self._diferencas(replace(self.regras, consumos=(consumo,)))
        self.assertEqual(len(difs), 2)

    def test_sem_a_exigencia(self):
        difs = self._diferencas(replace(self.regras, exigencias=()))
        self.assertTrue(any("predicates" in d for d in difs))
        self.assertTrue(any("conferir-protecao-exigida" in d for d in difs))
        self.assertTrue(any("iniciar-visita" in d for d in difs))

    def test_custo_da_conferencia(self):
        exigencia = replace(self.regras.exigencias[0], custo=2)
        difs = self._diferencas(replace(self.regras, exigencias=(exigencia,)))
        self.assertEqual(len(difs), 1)
        self.assertIn("conferir-protecao-exigida", difs[0])

    def test_reposicao_com_nome_padrao(self):
        coletor = replace(self.regras.recursos[2], nome_reposicao=None)
        recursos = self.regras.recursos[:2] + (coletor,)
        difs = self._diferencas(replace(self.regras, recursos=recursos))
        self.assertIn("acao repor-coletor: so existe no primeiro", difs)
        self.assertIn("acao trocar-coletor: so existe no segundo", difs)

if __name__ == "__main__":
    unittest.main()
