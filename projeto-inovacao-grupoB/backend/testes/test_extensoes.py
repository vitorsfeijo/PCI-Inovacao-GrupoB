"""
Extensoes da etapa 8: `quantidade` no consumo e exigencia por paciente num
procedimento (`antes_de`).
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from compilador import ErroRegra, ciclo2, compilar_dominio, ler_regras
from compilador.dominio import versoes_de_procedimentos
from compilador.planejar import main as planejar
from compilador.problema import marcas_dos_dados
from compilador.roteiro import legenda_para


def _legal() -> list:
    return ciclo2.planejador().ler_sexp(str(ciclo2.DOMINIO_LEGAL))


def _acoes(arvore: list) -> dict[str, list]:
    return {a[1]: a for a in arvore[2:] if isinstance(a, list) and a[0] == ":action"}


def _pre(acao: list) -> list:
    return acao[acao.index(":precondition") + 1]


def _problemas(dados: dict) -> list[str]:
    try:
        ler_regras(dados)
    except ErroRegra as erro:
        return erro.problemas
    raise AssertionError("esperava ErroRegra")


def _rodar(*argumentos: str) -> tuple[int, str, str]:
    saida, erros = io.StringIO(), io.StringIO()
    with redirect_stdout(saida), redirect_stderr(erros):
        codigo = planejar(list(argumentos))
    return codigo, saida.getvalue(), erros.getvalue()


LUVAS = {"nome": "luvas", "capacidade": 3, "custo_reposicao": 3, "texto": "luvas"}
CALCAR = {"nome": "calcar-luvas", "estado": "luvas-calcadas", "custo": 1,
          "consome": "luvas", "texto": "Calçar luvas"}
N95 = {"nome": "vestir-n95", "estado": "n95-vestida", "custo": 1, "texto": "Colocar N95"}
LUVAS_GESTANTE = {"nome": "luvas-gestante", "marca": "gestante",
                  "preparo": "calcar-luvas", "antes_de": ["glicemia"]}
N95_TB = {"nome": "n95", "marca": "suspeita-tuberculose", "preparo": "vestir-n95",
          "antes_de": ["glicemia", "pressao"]}


class TestQuantidade(unittest.TestCase):

    def test_padrao_e_um(self):
        regras = ler_regras({"recurso": [LUVAS],
                             "consumo": [{"procedimento": "glicemia", "recurso": "luvas"}]})
        self.assertEqual(regras.consumos[0].quantidade, 1)

    def test_validacao(self):
        problemas = _problemas({"recurso": [LUVAS], "consumo": [
            {"procedimento": "glicemia", "recurso": "luvas", "quantidade": 0},
            {"procedimento": "pressao", "recurso": "luvas", "quantidade": 4}]})
        texto = "\n".join(problemas)
        self.assertIn("maior ou igual a 1", texto)
        self.assertIn("gasta 4 unidades, mas o recurso só comporta 3", texto)

    def test_desce_k_niveis(self):
        regras = ler_regras({"recurso": [LUVAS], "consumo": [
            {"procedimento": "glicemia", "recurso": "luvas", "quantidade": 3}]})
        glicemia = _acoes(compilar_dominio(_legal(), regras))["medir-glicemia-capilar"]
        pre = _pre(glicemia)
        self.assertIn(["luvas", "?luvas"], pre)
        for maior, menor in (("?luvas", "?luvas-1"), ("?luvas-1", "?luvas-2"),
                             ("?luvas-2", "?luvas-3")):
            self.assertIn(["prox", menor, maior], pre)
        efeito = glicemia[glicemia.index(":effect") + 1]
        self.assertIn(["not", ["luvas", "?luvas"]], efeito)
        self.assertIn(["luvas", "?luvas-3"], efeito)

    def test_planejamento_gasta_a_quantidade_certa(self):
        # 3 pacientes que precisam de glicemia, 2 luvas por glicemia, 4 por carga:
        # o turno so fecha com uma reposicao na UBS
        ciclo2.garantir_caminho()
        from acsplan.dados import gerador
        dados = gerador.gerar(3, 1)
        for paciente in dados["pacientes"]:
            paciente["requer_glicemia"] = True
        regras_toml = ('[[recurso]]\nnome = "luvas"\ncapacidade = 4\ncusto_reposicao = 3\n'
                       '[[consumo]]\nprocedimento = "glicemia"\nrecurso = "luvas"\n'
                       'quantidade = {q}\n')
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "microarea.json"
            arquivo.write_text(json.dumps(dados), encoding="utf-8")
            resultados = {}
            for quantidade in (1, 2):
                toml = Path(pasta) / f"q{quantidade}.toml"
                toml.write_text(regras_toml.format(q=quantidade), encoding="utf-8")
                resultados[quantidade] = _rodar(str(toml), "--dados", str(arquivo),
                                                "--mostrar-plano", "--sem-selecao")
        for quantidade, (codigo, saida, info) in resultados.items():
            self.assertEqual(codigo, 0, info)
        self.assertNotIn("repor-luvas", resultados[1][1])
        self.assertIn("repor-luvas", resultados[2][1])


class TestExigenciaPorProcedimento(unittest.TestCase):

    def setUp(self):
        self.regras = ler_regras({"recurso": [LUVAS], "preparo": [CALCAR, N95],
                                  "exigencia": [LUVAS_GESTANTE, N95_TB]})
        self.acoes = _acoes(compilar_dominio(_legal(), self.regras))

    def test_validacao(self):
        problemas = _problemas({"preparo": [N95],
                                "exigencia": [{**LUVAS_GESTANTE, "preparo": "vestir-n95",
                                               "custo": 2, "texto": "x"},
                                              {**N95_TB, "antes_de": []}]})
        texto = "\n".join(problemas)
        self.assertIn("'custo' só vale para exigências no início da visita", texto)
        self.assertIn("'texto' só vale", texto)
        self.assertIn("pelo menos um procedimento", texto)

    def test_versoes(self):
        glicemias = sorted(n for n in self.acoes if n.startswith("medir-glicemia-capilar"))
        self.assertEqual(glicemias, ["medir-glicemia-capilar", "medir-glicemia-capilar-luvas-gestante",
                                     "medir-glicemia-capilar-luvas-gestante-n95",
                                     "medir-glicemia-capilar-n95"])
        self.assertIn("aferir-pressao-arterial-n95", self.acoes)
        self.assertNotIn("aferir-temperatura-axilar-n95", self.acoes)
        self.assertEqual(set(versoes_de_procedimentos(self.regras)),
                         set(glicemias[1:]) | {"aferir-pressao-arterial-n95"})

    def test_condicoes_de_cada_versao(self):
        def marcas(nome):
            pre = _pre(self.acoes[nome])
            return {m: ([m, "?p"] in pre, ["not", [m, "?p"]] in pre)
                    for m in ("gestante", "suspeita-tuberculose")}
        sim, nao = (True, False), (False, True)
        self.assertEqual(marcas("medir-glicemia-capilar"),
                         {"gestante": nao, "suspeita-tuberculose": nao})
        self.assertEqual(marcas("medir-glicemia-capilar-luvas-gestante"),
                         {"gestante": sim, "suspeita-tuberculose": nao})
        self.assertEqual(marcas("medir-glicemia-capilar-n95"),
                         {"gestante": nao, "suspeita-tuberculose": sim})
        self.assertEqual(marcas("medir-glicemia-capilar-luvas-gestante-n95"),
                         {"gestante": sim, "suspeita-tuberculose": sim})
        # o preparo e conferido no proprio procedimento, nao numa conferencia antes
        combinada = _pre(self.acoes["medir-glicemia-capilar-luvas-gestante-n95"])
        self.assertIn(["luvas-calcadas", "?ag"], combinada)
        self.assertIn(["n95-vestida", "?ag"], combinada)
        self.assertNotIn("conferir-luvas-gestante-exigida", self.acoes)

    def test_versoes_herdam_consumo(self):
        regras = ler_regras({"recurso": [LUVAS, {**LUVAS, "nome": "coletor", "texto": "c"}],
                             "preparo": [CALCAR],
                             "consumo": [{"procedimento": "glicemia", "recurso": "coletor"}],
                             "exigencia": [LUVAS_GESTANTE]})
        acoes = _acoes(compilar_dominio(_legal(), regras))
        self.assertIn(["coletor", "?coletor"],
                      _pre(acoes["medir-glicemia-capilar-luvas-gestante"]))

    def test_roteiro_mostra_a_versao_como_o_procedimento(self):
        legenda = legenda_para(self.regras)
        self.assertEqual(legenda.tarefas["medir-glicemia-capilar-luvas-gestante-n95"][0],
                         "Medir glicemia capilar")
        self.assertEqual(legenda.tarefas["calcar-luvas"][0], "Calçar luvas")


class TestMarcasDaPlanilha(unittest.TestCase):
    """O leitor de CSV do Ciclo 2 descarta colunas que nao conhece."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        original = ciclo2.PLANILHA_EXEMPLO.read_text(encoding="utf-8").splitlines()
        linhas = [original[0] + ",gestante"] + [
            linha + (",sim" if i == 1 else ",nao") for i, linha in enumerate(original[1:], 1)]
        self.planilha = Path(self.pasta.name) / "microarea.csv"
        self.planilha.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        self.regras = ler_regras({"recurso": [LUVAS], "preparo": [CALCAR],
                                  "exigencia": [LUVAS_GESTANTE]})

    def tearDown(self):
        self.pasta.cleanup()

    def test_coluna_extra_e_lida(self):
        dados = ciclo2.ler_dados(str(self.planilha), ["gestante"])
        self.assertEqual(marcas_dos_dados(dados, self.regras), {"gestante": ["p1"]})

    def test_sem_a_coluna_e_erro(self):
        dados = ciclo2.ler_dados(str(ciclo2.PLANILHA_EXEMPLO), ["gestante"])
        with self.assertRaises(ErroRegra) as contexto:
            marcas_dos_dados(dados, self.regras)
        self.assertIn('não têm a coluna "gestante"', str(contexto.exception))

    def test_planejar_com_a_planilha(self):
        with tempfile.TemporaryDirectory() as pasta:
            toml = Path(pasta) / "regras.toml"
            toml.write_text(
                '[[recurso]]\nnome = "luvas"\ncapacidade = 3\ncusto_reposicao = 3\n'
                '[[preparo]]\nnome = "calcar-luvas"\nestado = "luvas-calcadas"\ncusto = 1\n'
                'consome = "luvas"\ntexto = "Calçar luvas"\n'
                '[[exigencia]]\nnome = "luvas-gestante"\nmarca = "gestante"\n'
                'preparo = "calcar-luvas"\nantes_de = ["glicemia", "pressao"]\n',
                encoding="utf-8")
            # estrategia padrao (astar-hadd): a gbfs ignora custos e pode incluir
            # preparos inuteis no plano, que o roteiro mostraria fielmente
            codigo, roteiro, info = _rodar(str(toml), "--dados", str(self.planilha),
                                           "--sem-selecao")
        self.assertEqual(codigo, 0, info)
        # so p1 (marcado) calca luvas, e o roteiro nao mostra nomes internos
        self.assertEqual(roteiro.count("Calçar luvas"), 1)
        self.assertNotIn("luvas-gestante", roteiro)


if __name__ == "__main__":
    unittest.main()
