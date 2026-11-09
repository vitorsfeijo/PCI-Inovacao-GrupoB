"""
A instanciacao podada (compilador/instanciacao.py) precisa dar EXATAMENTE o
mesmo resultado que a do Ciclo 2: mesmas acoes, na mesma ordem, com os
mesmos identificadores de fatos. Os casos aqui sao pequenos o bastante para
a instanciacao original terminar.
"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from compilador import (NOME_PADRAO, carregar_regras, ciclo2, compilar_dominio,
                        gerar_problema_com_regras, ler_regras)
from compilador.instanciacao import TarefaPlanejamentoPodada
from compilador.pddl import escrever_pddl
from compilador.regras import regras_para_dados

RAIZ = Path(__file__).resolve().parents[1]
REGRAS = sorted((RAIZ.parent / "exemplos" / "avaliacao" / "regras").glob("*.toml"))


def _juntar(arquivos) -> object:
    dados: dict = {}
    for arquivo in arquivos:
        for modelo, blocos in regras_para_dados(carregar_regras(str(arquivo))).items():
            dados.setdefault(modelo, []).extend(blocos)
    return ler_regras(dados)


class TestInstanciacaoIdentica(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.planejador = ciclo2.planejador()
        from acsplan.dados import gerador
        from acsplan.geo import roteirizador
        from acsplan.logica.gerador_problema import gerar_problema
        cls.gerador, cls.roteirizador = gerador, roteirizador
        cls.gerar_problema = staticmethod(gerar_problema)
        cls.pasta = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.pasta.cleanup()

    def _dados(self, n: int, semente: int) -> dict:
        dados = self.gerador.gerar(n, semente)
        for i, paciente in enumerate(dados["pacientes"]):   # marcas das regras novas
            paciente["gestante"] = i % 2 == 0
            paciente["suspeita_tuberculose"] = i == 1
            paciente["exige_avental"] = i % 3 == 0
            paciente["requer_glicemia"] = paciente["requer_glicemia"] or i == 0
        return dados

    def _comparar(self, regras, n: int, semente: int, *, estendido: bool = False):
        dados = self._dados(n, semente)
        roteamento = self.roteirizador.roteirizar(dados, usar_precedencia=True)
        problema = os.path.join(self.pasta.name, "problema.pddl")
        if estendido:
            dominio = str(ciclo2.DOMINIO_ESTENDIDO)
            self.gerar_problema(dados, roteamento, problema, dominio="estendido")
        else:
            dominio = os.path.join(self.pasta.name, "dominio.pddl")
            legal = self.planejador.ler_sexp(str(ciclo2.DOMINIO_LEGAL))
            Path(dominio).write_text(escrever_pddl(
                compilar_dominio(legal, regras, nome=NOME_PADRAO), ["teste"]), encoding="utf-8")
            gerar_problema_com_regras(dados, roteamento, regras, problema,
                                      nome_dominio=NOME_PADRAO)
        d = self.planejador.carregar_dominio(dominio)
        p = self.planejador.carregar_problema(problema)
        inicio = time.perf_counter()
        original = self.planejador.TarefaPlanejamento(d, p)
        meio = time.perf_counter()
        podada = TarefaPlanejamentoPodada(d, p)
        fim = time.perf_counter()
        self.assertGreater(len(original.acoes), 0)
        self.assertEqual(podada.acoes, original.acoes)                 # mesma ordem
        self.assertEqual(podada._fato_por_id, original._fato_por_id)   # mesmos ids
        self.assertEqual(podada.estado_inicial, original.estado_inicial)
        self.assertEqual(podada.objetivo_pos, original.objetivo_pos)
        return meio - inicio, fim - meio

    def test_dominio_legal(self):
        self._comparar(ler_regras({}), 3, 1)

    def test_dominio_estendido_do_ciclo2(self):
        self._comparar(None, 3, 2, estendido=True)

    def test_regras_sinteticas_compiladas(self):
        self._comparar(carregar_regras(str(RAIZ.parent / "exemplos" / "sinteticas-ciclo2.toml")), 3, 2)

    def test_quantidade_r7(self):
        original, podada = self._comparar(carregar_regras(str(REGRAS[6])), 2, 1)
        self.assertLess(podada, original)

    def test_regras_r1_a_r6_juntas(self):
        self._comparar(_juntar(REGRAS[:6]), 2, 1)


class TestInstanciacaoEscala(unittest.TestCase):

    def test_sete_regras_dez_pacientes(self):
        # a instanciacao original passaria de 4 bilhoes de combinacoes aqui
        planejador = ciclo2.planejador()
        dados = ciclo2.ler_dados(str(RAIZ.parent / "exemplos" / "avaliacao" / "microarea-avaliacao.csv"),
                                 ["gestante", "suspeita_tuberculose", "exige_avental"])
        from acsplan.geo import roteirizador
        regras = _juntar(REGRAS)
        with tempfile.TemporaryDirectory() as pasta:
            dominio, problema = os.path.join(pasta, "d.pddl"), os.path.join(pasta, "p.pddl")
            legal = planejador.ler_sexp(str(ciclo2.DOMINIO_LEGAL))
            Path(dominio).write_text(escrever_pddl(compilar_dominio(legal, regras), ["t"]),
                                     encoding="utf-8")
            gerar_problema_com_regras(dados, roteirizador.roteirizar(dados), regras, problema,
                                      nome_dominio=NOME_PADRAO)
            inicio = time.perf_counter()
            tarefa = TarefaPlanejamentoPodada(planejador.carregar_dominio(dominio),
                                              planejador.carregar_problema(problema))
        self.assertLess(time.perf_counter() - inicio, 30)
        self.assertGreater(len(tarefa.acoes), 0)


if __name__ == "__main__":
    unittest.main()
