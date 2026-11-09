"""
Testes do roteiro do ACS e do comando `python3 acs.py planejar`.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from compilador import ciclo2, ler_regras
from compilador.planejar import main as planejar
from compilador.regras import carregar_regras
from compilador.roteiro import legenda_para, legivel, montar

EXEMPLOS = Path(__file__).resolve().parents[2] / "exemplos"
SINTETICAS = EXEMPLOS / "sinteticas-ciclo2.toml"


def rodar(*argumentos: str) -> tuple[int, str, str]:
    saida, erros = io.StringIO(), io.StringIO()
    with redirect_stdout(saida), redirect_stderr(erros):
        codigo = planejar(list(argumentos))
    return codigo, saida.getvalue(), erros.getvalue()


class TestLegenda(unittest.TestCase):

    def test_textos_das_regras(self):
        legenda = legenda_para(carregar_regras(str(SINTETICAS)))
        self.assertEqual(legenda.tarefas["higienizar-maos"][0], "Higienizar as mãos")
        self.assertEqual(legenda.tarefas["conferir-protecao-exigida"][0],
                         "Conferir a proteção antes de entrar")
        self.assertEqual(legenda.reposicoes["trocar-coletor"], "coletor de perfurocortante")
        self.assertIn("conferir-protecao-dispensada", legenda.ocultas)

    def test_sem_texto_usa_o_nome(self):
        regras = ler_regras({
            "recurso": [{"nome": "sabao-liquido", "capacidade": 2, "custo_reposicao": 1}],
            "preparo": [{"nome": "lavar-maos", "estado": "maos-lavadas", "custo": 1,
                         "consome": "sabao-liquido", "exigido_antes_de": ["vacinal"]}],
            "exigencia": [{"nome": "avental", "marca": "exige-avental",
                           "preparo": "lavar-maos"}],
        })
        legenda = legenda_para(regras)
        self.assertEqual(legenda.tarefas["lavar-maos"][0], "Lavar maos")
        self.assertEqual(legenda.reposicoes["repor-sabao-liquido"], "sabao liquido")
        self.assertEqual(legenda.tarefas["conferir-avental-exigida"][0],
                         "Conferir avental antes de entrar")
        self.assertEqual(legivel("vestir-avental"), "Vestir avental")

    def test_ordem_de_trabalho(self):
        legenda = legenda_para(carregar_regras(str(SINTETICAS)))
        ordem = {nome: legenda.tarefas[nome][1] for nome in (
            "acionar-supervisao", "vestir-mascara", "conferir-protecao-exigida",
            "higienizar-maos", "aferir-pressao-arterial", "registrar-visita")}
        self.assertEqual(sorted(ordem, key=ordem.get), list(ordem))


class TestMontar(unittest.TestCase):
    """Plano escrito a mao, no formato do planejador."""

    def setUp(self):
        self.dados = {"ubs": {"id": "ubs", "nome": "UBS"},
                      "pacientes": [{"id": "p1", "nome": "Ana"},
                                    {"id": "p2", "nome": "Bia"}]}
        self.legenda = legenda_para(carregar_regras(str(SINTETICAS)))
        self.plano = [
            "mover(acs1, ubs, casa-p1)",
            "acionar-supervisao(acs1, n2, n1)",
            "conferir-protecao-dispensada(acs1, p1, casa-p1)",
            "iniciar-visita(acs1, p1, casa-p1)",
            "higienizar-maos(acs1, n6, n5)",
            "aferir-pressao-arterial(acs1, p1, casa-p1)",
            "registrar-visita(acs1, p1, casa-p1)",
            "mover(acs1, casa-p1, casa-p2)",
            "desviar-para-ubs(acs1, casa-p2, ubs-fim)",
            "repor-mascaras(acs1, ubs-fim, n0, n2)",
            "retornar-a-rota(acs1, ubs-fim, casa-p2)",
            "vestir-mascara(acs1, n2, n1)",
            "conferir-protecao-exigida(acs1, p2, casa-p2)",
            "iniciar-visita(acs1, p2, casa-p2)",
            "registrar-visita(acs1, p2, casa-p2)",
        ]
        self.custos = {passo: 1 for passo in self.plano}

    def test_paradas(self):
        primeira, segunda = montar(self.plano, self.dados, self.custos, self.legenda)
        self.assertEqual(primeira["paciente"]["nome"], "Ana")
        self.assertEqual(primeira["tarefas"], [
            "Acionar o enfermeiro da equipe (acompanhamento obrigatório)",
            "Higienizar as mãos", "Aferir pressão arterial",
            "Registrar a visita no sistema"])
        self.assertFalse(primeira["desvio_ubs"])
        # o desvio e a reposicao pertencem a visita seguinte
        self.assertTrue(segunda["desvio_ubs"])
        self.assertEqual(segunda["repor"], ["máscaras"])
        self.assertEqual(segunda["tarefas"], [
            "Colocar máscara de proteção respiratória",
            "Conferir a proteção antes de entrar",
            "Registrar a visita no sistema"])
        self.assertEqual(primeira["minutos_chegada"], 4)   # 4o passo do plano
        self.assertEqual(segunda["minutos_chegada"], 14)


class TestComandoPlanejar(unittest.TestCase):

    def test_turno_com_mascara(self):
        codigo, roteiro, info = rodar(str(SINTETICAS), "--instancia-sintetica", "4", "2")
        self.assertEqual(codigo, 0, info)
        self.assertEqual(roteiro.count("Colocar máscara de proteção respiratória"), 2)
        self.assertEqual(roteiro.count("Conferir a proteção antes de entrar"), 2)
        self.assertIn("Higienizar as mãos", roteiro)
        self.assertNotIn("conferir", roteiro)              # nada de nomes internos
        self.assertIn("4 visitas  |  duração estimada: 145 min", roteiro)
        self.assertIn("[4] Plano:", info)

    def test_sem_regras_usa_so_o_dominio_legal(self):
        codigo, roteiro, info = rodar("--instancia-sintetica", "4", "2")
        self.assertEqual(codigo, 0, info)
        self.assertNotIn("Higienizar", roteiro)
        self.assertIn("nenhuma (só o domínio legal)", info)

    def test_salva_roteiro_e_pddl(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "roteiro.txt"
            pddl = Path(pasta) / "pddl"
            codigo, roteiro, info = rodar(str(SINTETICAS), "--instancia-sintetica", "3", "1",
                                          "--salvar", str(arquivo),
                                          "--salvar-pddl", str(pddl))
            self.assertEqual(codigo, 0, info)
            self.assertEqual(roteiro, "")
            self.assertIn("ROTEIRO DO TURNO", arquivo.read_text(encoding="utf-8"))
            self.assertTrue((pddl / "dominio.pddl").exists())
            self.assertIn("exige-protecao-respiratoria",
                          (pddl / "dominio.pddl").read_text(encoding="utf-8"))
            self.assertTrue((pddl / "problema.pddl").exists())

    def test_planilha_de_exemplo(self):
        # mesmo modo de busca do `acsplan roteiro --estrategia astar-hadd` do
        # Ciclo 2, sem a limpeza (que o Ciclo 2 nao tem): o mesmo turno que ele
        # da com o dominio estendido
        codigo, roteiro, info = rodar(str(SINTETICAS), "--orcamento", "240",
                                      "--estrategia", "astar-hadd", "--sem-limpeza",
                                      "--planejador", "ciclo2")
        self.assertEqual(codigo, 0, info)
        self.assertIn("6 visitas  |  duração estimada: 262 min", roteiro)
        self.assertIn("ATENÇÃO: excede em 22 min o orçamento de 240 min", roteiro)

    def test_regras_com_erro(self):
        with tempfile.TemporaryDirectory() as pasta:
            ruim = Path(pasta) / "ruim.toml"
            ruim.write_text('[[recurso]]\nnome = "Álcool"\n', encoding="utf-8")
            codigo, roteiro, info = rodar(str(ruim))
        self.assertEqual(codigo, 1)
        self.assertIn("Erro:", info)
        self.assertEqual(roteiro, "")

    def test_busca_interrompida_nao_e_turno_impossivel(self):
        codigo, _, info = rodar(str(SINTETICAS), "--instancia-sintetica", "4", "2",
                                "--estrategia", "astar-hmax", "--limite", "0.000001",
                                "--planejador", "ciclo2")
        self.assertEqual(codigo, 1)
        self.assertIn("NÃO mostra que o turno é impossível", info)

    def test_turno_impossivel(self):
        # sem curso tecnico, o ACS nao pode fazer os procedimentos do par. 4o
        ciclo2.garantir_caminho()
        from acsplan.dados import gerador
        dados = gerador.gerar(3, 1)
        dados["agente"]["curso_tecnico_concluido"] = False
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "microarea.json"
            arquivo.write_text(json.dumps(dados), encoding="utf-8")
            codigo, _, info = rodar(str(SINTETICAS), "--dados", str(arquivo))
        self.assertEqual(codigo, 1)
        self.assertIn("nenhuma sequência de ações cumpre as regras", info)


AVALIACAO = EXEMPLOS / "avaliacao"
PLANILHA_AVALIACAO = AVALIACAO / "microarea-avaliacao.csv"


class TestCorrecoesDaAvaliacao(unittest.TestCase):
    """Falhas achadas ao testar as regras novas no turno completo. Estes testes
    fixam o planejador do Ciclo 2, cujo comportamento eles verificam."""

    def test_limpeza_retira_equipamento_vestido_a_toa(self):
        # com h_add, o plano vestia avental em quem nao precisava e ia a UBS
        # repor; a limpeza retira essas acoes
        regra = str(AVALIACAO / "regras" / "r4-avental.toml")
        comum = (regra, "--dados", str(PLANILHA_AVALIACAO), "--sem-selecao",
                 "--estrategia", "astar-hadd", "--mostrar-plano", "--planejador", "ciclo2")
        _, sujo, _ = rodar(*comum, "--sem-limpeza")
        codigo, limpo, info = rodar(*comum)
        self.assertEqual(codigo, 0, info)
        self.assertIn("ações redundantes retiradas", info)
        # contado no PLANO: no roteiro, a atribuicao de cada preparo a visita
        # em que e usado ja esconderia os vestires inuteis (mas nao o tempo)
        vestir = lambda t: t.split("PLANO COMPLETO")[1].count("vestir-avental(")
        self.assertGreater(vestir(sujo), 2)
        self.assertEqual(vestir(limpo), 2)                               # os 2 acamados
        duracao = lambda t: int(t.split("duração estimada: ")[1].split()[0])
        self.assertLess(duracao(limpo), duracao(sujo))

    def test_preparo_aparece_onde_e_usado(self):
        # o plano zera a balanca logo no inicio, mas o roteiro mostra a tarefa
        # na primeira visita com antropometria
        codigo, roteiro, info = rodar(str(AVALIACAO / "regras" / "r3-balanca.toml"),
                                      "--dados", str(PLANILHA_AVALIACAO), "--sem-selecao",
                                      "--estrategia", "astar-hadd", "--mostrar-plano",
                                      "--planejador", "ciclo2")
        self.assertEqual(codigo, 0, info)
        plano = roteiro.split("PLANO COMPLETO")[1]
        # o plano zera a balanca antes de chegar a casa da Paciente 10...
        self.assertLess(plano.index("zerar-balanca"), plano.index("casa-p10"))
        # ... mas o roteiro mostra a tarefa na visita dela, a primeira pesagem
        visita = roteiro.split("  3. ")[1].split("\n\n")[0]
        self.assertIn("Paciente 10", visita)
        self.assertIn("Zerar a balança portátil", visita)
        self.assertEqual(roteiro.split("PLANO COMPLETO")[0].count("Zerar a balança"), 1)

    def test_auto_recorre_ao_h_add(self):
        codigo, _, info = rodar(str(SINTETICAS), "--orcamento", "240", "--limite", "0.02",
                                "--planejador", "ciclo2")
        self.assertIn("planejando por janelas", info)

    def test_auto_e_otimo_quando_h_max_termina(self):
        codigo, roteiro, info = rodar(str(SINTETICAS), "--instancia-sintetica", "3", "1",
                                      "--planejador", "ciclo2")
        self.assertEqual(codigo, 0, info)
        self.assertIn("astar-hmax, ótimo", info)


class TestDespachoDeComandos(unittest.TestCase):

    def test_python_m_compilador_planejar(self):
        from compilador.__main__ import main
        saida, erros = io.StringIO(), io.StringIO()
        with redirect_stdout(saida), redirect_stderr(erros):
            codigo = main(["planejar", str(SINTETICAS), "--instancia-sintetica", "2", "1"])
        self.assertEqual(codigo, 0, erros.getvalue())
        self.assertIn("ROTEIRO DO TURNO", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
