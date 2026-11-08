"""
Testes do compilador de regras.

    cd projeto-inovacao-grupoB
    python -m unittest discover testes
"""

from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from compilador import (ErroRegra, avisos, carregar_regras, compilar_dominio,
                        compilar_problema, ler_regras)
from compilador import ciclo2
from compilador.pddl import em_linha, escrever_pddl
from compilador.regras import sugerir_nome, validar_nome

EXEMPLO = Path(__file__).resolve().parents[1] / "exemplos" / "higienizacao.toml"


def _ler(caminho) -> list:
    return ciclo2.planejador().ler_sexp(str(caminho))


def _recurso(**mudancas) -> dict:
    return {"nome": "alcool", "capacidade": 6, "custo_reposicao": 3, **mudancas}


def _preparo(**mudancas) -> dict:
    return {"nome": "higienizar-maos", "estado": "maos-higienizadas", "custo": 2,
            "consome": "alcool", "exigido_antes_de": ["pressao"], **mudancas}


def _problemas(dados: dict) -> list[str]:
    """Problemas relatados para regras que devem ser recusadas."""
    try:
        ler_regras(dados)
    except ErroRegra as erro:
        return erro.problemas
    raise AssertionError("esperava ErroRegra, mas a regra foi aceita")


def _acoes(arvore: list) -> dict[str, list]:
    return {item[1]: item for item in arvore[2:]
            if isinstance(item, list) and item and item[0] == ":action"}


def _campo(acao: list, chave: str):
    return acao[acao.index(chave) + 1]


# ============================================================================

class TestLeitura(unittest.TestCase):

    def test_exemplo_e_aceito(self):
        regras = carregar_regras(str(EXEMPLO))
        self.assertEqual([r.nome for r in regras.recursos], ["alcool"])
        self.assertEqual(regras.preparos[0].estado, "maos-higienizadas")
        self.assertEqual(avisos(regras), [])

    def test_valores_padrao_do_preparo(self):
        regras = ler_regras({"preparo": [{"nome": "a", "estado": "b", "custo": 1}]})
        preparo = regras.preparos[0]
        self.assertIsNone(preparo.consome)
        self.assertTrue(preparo.desfeito_ao_sair)
        self.assertEqual(preparo.exigido_antes_de, ())

    def test_todos_os_erros_aparecem_juntos(self):
        problemas = _problemas({
            "recurso": [_recurso(nome="Álcool Gel", capacidade="6", custo_reposicao=-1)],
            "preparo": [{"nome": "x", "custo": 1, "cor": "azul",
                         "exigido_antes_de": ["glicose"]}],
        })
        self.assertEqual(len(problemas), 6)
        texto = "\n".join(problemas)
        for trecho in ("Sugestão: \"alcool-gel\"", "sem aspas", "maior ou igual a 0",
                       "falta o campo 'estado'", "'cor' não existe", "'glicose'"):
            self.assertIn(trecho, texto)

    def test_modelo_inexistente(self):
        problemas = _problemas({"recursos": [_recurso()]})
        self.assertIn("o modelo 'recursos' não existe", problemas[0])

    def test_recurso_consumido_inexistente(self):
        problemas = _problemas({"preparo": [_preparo(consome="alcol")]})
        self.assertIn("não há recurso", problemas[0])

    def test_recurso_com_erro_nao_vira_recurso_inexistente(self):
        problemas = _problemas({"recurso": [_recurso(capacidade="6")],
                                "preparo": [_preparo()]})
        self.assertEqual(len(problemas), 1)
        self.assertIn("capacidade", problemas[0])

    def test_nomes_repetidos_entre_regras(self):
        problemas = _problemas({"recurso": [_recurso(), _recurso()]})
        self.assertEqual(problemas, ['recurso "alcool": o nome "alcool" já é usado '
                                     'pelo recurso "alcool"'])

    def test_procedimento_repetido(self):
        problemas = _problemas({"recurso": [_recurso()],
                                "preparo": [_preparo(exigido_antes_de=["pressao", "pressao"])]})
        self.assertIn("repetido", problemas[0])

    def test_booleano_com_aspas(self):
        problemas = _problemas({"recurso": [_recurso()],
                                "preparo": [_preparo(desfeito_ao_sair="true")]})
        self.assertIn("true ou false", problemas[0])

    def test_toml_quebrado_informa_linha(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as arquivo:
            arquivo.write('[[recurso]]\nnome = "alcool\n')
        try:
            with self.assertRaises(ErroRegra) as contexto:
                carregar_regras(arquivo.name)
        finally:
            os.unlink(arquivo.name)
        self.assertIn("na linha 2", str(contexto.exception))

    def test_arquivo_inexistente(self):
        with self.assertRaises(ErroRegra) as contexto:
            carregar_regras("nao-existe.toml")
        self.assertIn("não foi encontrado", str(contexto.exception))


class TestNomes(unittest.TestCase):

    def test_nomes_validos(self):
        for nome in ("alcool", "maos-higienizadas", "epi2", "a-1-b"):
            self.assertIsNone(validar_nome(nome), nome)

    def test_nomes_invalidos(self):
        for nome in ("Alcool", "álcool", "alcool gel", "-alcool", "alcool-", "a--b",
                     "1alcool", "", 3):
            self.assertIsNotNone(validar_nome(nome), nome)

    def test_sugestao(self):
        self.assertEqual(sugerir_nome("Álcool Gel"), "alcool-gel")
        self.assertEqual(sugerir_nome("Máscara  N95!"), "mascara-n95")
        self.assertEqual(sugerir_nome("123"), "")


class TestAvisos(unittest.TestCase):

    def test_regras_sem_efeito(self):
        regras = ler_regras({
            "recurso": [_recurso(nome="sabao")],
            "preparo": [{"nome": "lavar-maos", "estado": "maos-lavadas", "custo": 1},
                        {"nome": "vestir", "estado": "vestido", "custo": 1,
                         "desfeito_ao_sair": False, "exigido_antes_de": ["vacinal"]}],
        })
        texto = "\n".join(avisos(regras))
        self.assertIn("\"sabao\": nenhum preparo ou procedimento o consome", texto)
        self.assertIn("\"lavar-maos\": não é exigido", texto)
        self.assertIn("\"vestir\": como não é desfeito", texto)

    def test_arquivo_vazio(self):
        self.assertIn("nenhuma regra", avisos(ler_regras({}))[0])


class TestDominio(unittest.TestCase):

    def setUp(self):
        self.legal = _ler(ciclo2.DOMINIO_LEGAL)
        self.regras = carregar_regras(str(EXEMPLO))

    def test_dominio_de_entrada_nao_e_alterado(self):
        antes = em_linha(self.legal)
        compilar_dominio(self.legal, self.regras)
        self.assertEqual(em_linha(self.legal), antes)

    def test_higienizacao(self):
        acoes = _acoes(compilar_dominio(self.legal, self.regras))
        self.assertIn("higienizar-maos", acoes)
        self.assertIn("repor-alcool", acoes)
        self.assertIn(["maos-higienizadas", "?ag"],
                      _campo(acoes["aferir-pressao-arterial"], ":precondition"))
        self.assertNotIn(["maos-higienizadas", "?ag"],
                         _campo(acoes["verificar-caderneta-vacinal"], ":precondition"))
        for saida in ("mover", "desviar-para-ubs"):
            self.assertIn(["not", ["maos-higienizadas", "?ag"]],
                          _campo(acoes[saida], ":effect"))

    def test_nome_ja_usado_pelo_dominio(self):
        regras = ler_regras({"recurso": [_recurso(nome="fitas")],
                             "preparo": [_preparo(consome="fitas",
                                                  estado="supervisao-ativa")]})
        with self.assertRaises(ErroRegra) as contexto:
            compilar_dominio(self.legal, regras)
        problemas = contexto.exception.problemas
        self.assertEqual(len(problemas), 2)
        self.assertIn("campo 'estado'", problemas[1])

    def test_nome_derivado_ja_usado_pelo_dominio(self):
        # acao de reposicao com o nome de uma acao que o dominio ja tem
        regras = ler_regras({"recurso": [_recurso(acao_reposicao="reabastecer-fitas")],
                             "preparo": [_preparo()]})
        with self.assertRaises(ErroRegra) as contexto:
            compilar_dominio(self.legal, regras)
        self.assertIn('o nome "reabastecer-fitas" já é usado pelo domínio',
                      str(contexto.exception))

    def test_nome_derivado_coincide_entre_regras(self):
        # o recurso "supervisao" gera a acao "repor-supervisao", igual ao preparo
        problemas = _problemas({"recurso": [_recurso(nome="supervisao")],
                                "preparo": [_preparo(nome="repor-supervisao",
                                                     consome="supervisao")]})
        self.assertIn('já é usado pelo recurso "supervisao"', problemas[0])

    def test_saida_e_pddl_valido(self):
        texto = escrever_pddl(compilar_dominio(self.legal, self.regras), ["teste"])
        with tempfile.NamedTemporaryFile("w", suffix=".pddl", delete=False) as arquivo:
            arquivo.write(texto)
        try:
            dominio = ciclo2.planejador().carregar_dominio(arquivo.name)
        finally:
            os.unlink(arquivo.name)
        self.assertIn("higienizar-maos", [a.nome for a in dominio.acoes])


class TestProblema(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        ciclo2.planejador()
        from acsplan.dados import gerador
        from acsplan.geo import roteirizador
        from acsplan.logica.gerador_problema import gerar_problema

        dados = gerador.gerar(3, 3, fitas_por_carga=3)
        roteamento = roteirizador.roteirizar(dados, usar_precedencia=False)
        cls.pasta = tempfile.TemporaryDirectory()
        cls.legal = os.path.join(cls.pasta.name, "legal.pddl")
        cls.estendido = os.path.join(cls.pasta.name, "estendido.pddl")
        gerar_problema(dados, roteamento, cls.legal, dominio="legal")
        gerar_problema(dados, roteamento, cls.estendido, dominio="estendido")

    @classmethod
    def tearDownClass(cls):
        cls.pasta.cleanup()

    def _init(self, capacidade: int) -> list:
        regras = ler_regras({"recurso": [_recurso(capacidade=capacidade)],
                             "preparo": [_preparo()]})
        arvore = compilar_problema(_ler(self.legal), regras, nome_dominio="d")
        init = next(s for s in arvore[2:] if s[0] == ":init")
        return arvore, init

    def test_fatos_do_recurso(self):
        arvore, init = self._init(2)
        self.assertIn(["alcool", "n2"], init)
        self.assertIn(["nivel-maximo-alcool", "n2"], init)
        self.assertEqual(next(s for s in arvore[2:] if s[0] == ":domain"), [":domain", "d"])

    def test_cria_niveis_que_faltam(self):
        arvore, init = self._init(9)
        objetos = next(s for s in arvore[2:] if s[0] == ":objects")
        self.assertIn("n9", objetos)
        self.assertIn(["prox", "n8", "n9"], init)

    def test_recusa_problema_do_dominio_estendido(self):
        regras = carregar_regras(str(EXEMPLO))
        with self.assertRaises(ErroRegra) as contexto:
            compilar_problema(_ler(self.estendido), regras, nome_dominio="d")
        self.assertIn("domínio legal", str(contexto.exception))


if __name__ == "__main__":
    unittest.main()


# ============================================================================
#  MODELOS D (consumo) e E (exigencia)
# ============================================================================

SINTETICAS = EXEMPLO.with_name("sinteticas-ciclo2.toml")


class TestConsumoEExigencia(unittest.TestCase):

    def setUp(self):
        self.legal = _ler(ciclo2.DOMINIO_LEGAL)

    def test_exemplo_sem_avisos(self):
        regras = carregar_regras(str(SINTETICAS))
        self.assertEqual(len(regras.consumos), 1)
        self.assertEqual(len(regras.exigencias), 1)
        self.assertEqual(avisos(regras), [])

    def test_erros_de_consumo(self):
        problemas = _problemas({
            "recurso": [_recurso(nome="coletor")],
            "consumo": [{"procedimento": "glicose", "recurso": "coletor"},
                        {"procedimento": "glicemia", "recurso": "coletr"},
                        {"procedimento": "glicemia", "recurso": "coletor"},
                        {"procedimento": "glicemia", "recurso": "coletor"}],
        })
        texto = "\n".join(problemas)
        self.assertIn("'glicose' não existe", texto)
        self.assertIn('gasta "coletr", mas não há recurso', texto)
        self.assertIn("aparece mais de uma vez", texto)

    def test_erros_de_exigencia(self):
        problemas = _problemas({"exigencia": [{"nome": "protecao", "marca": "m",
                                               "preparo": "vestir"}]})
        self.assertIn('exige o preparo "vestir", mas não há preparo', problemas[0])

    def test_reposicao_com_outro_nome(self):
        regras = ler_regras({"recurso": [_recurso(nome="coletor",
                                                  acao_reposicao="trocar-coletor")],
                             "consumo": [{"procedimento": "glicemia",
                                          "recurso": "coletor"}]})
        acoes = _acoes(compilar_dominio(self.legal, regras))
        self.assertIn("trocar-coletor", acoes)
        self.assertNotIn("repor-coletor", acoes)

    def test_consumo_no_dominio(self):
        regras = ler_regras({"recurso": [_recurso(nome="coletor")],
                             "consumo": [{"procedimento": "glicemia",
                                          "recurso": "coletor"}]})
        glicemia = _acoes(compilar_dominio(self.legal, regras))["medir-glicemia-capilar"]
        self.assertIn("?coletor", _campo(glicemia, ":parameters"))
        self.assertIn(["coletor", "?coletor"], _campo(glicemia, ":precondition"))
        self.assertIn(["not", ["coletor", "?coletor"]], _campo(glicemia, ":effect"))
        self.assertIn(["coletor", "?coletor-1"], _campo(glicemia, ":effect"))

    def test_exigencia_no_dominio(self):
        acoes = _acoes(compilar_dominio(self.legal, carregar_regras(str(SINTETICAS))))
        self.assertIn("conferir-protecao-exigida", acoes)
        self.assertIn("conferir-protecao-dispensada", acoes)
        for inicio in ("iniciar-visita", "iniciar-visita-urgente", "iniciar-visita-adiavel"):
            self.assertIn(["protecao-conferida", "?ag", "?p"],
                          _campo(acoes[inicio], ":precondition"))

    def test_marca_ja_usada_pelo_dominio(self):
        regras = ler_regras({"recurso": [_recurso()], "preparo": [_preparo()],
                             "exigencia": [{"nome": "x", "marca": "urgencia-alta",
                                            "preparo": "higienizar-maos"}]})
        with self.assertRaises(ErroRegra) as contexto:
            compilar_dominio(self.legal, regras)
        self.assertIn("campo 'marca'", str(contexto.exception))


class TestProblemaComMarcas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        TestProblema.setUpClass.__func__(cls)
        cls.regras = carregar_regras(str(SINTETICAS))

    @classmethod
    def tearDownClass(cls):
        cls.pasta.cleanup()

    def test_marcas_viram_fatos(self):
        arvore = compilar_problema(_ler(self.legal), self.regras, nome_dominio="d",
                                   marcados={"exige-protecao-respiratoria": ["p2"]})
        init = next(s for s in arvore[2:] if s[0] == ":init")
        self.assertIn(["exige-protecao-respiratoria", "p2"], init)
        self.assertNotIn(["exige-protecao-respiratoria", "p1"], init)
        self.assertIn(["coletor", "n3"], init)

    def test_sem_dados_dos_pacientes(self):
        with self.assertRaises(ErroRegra) as contexto:
            compilar_problema(_ler(self.legal), self.regras, nome_dominio="d")
        self.assertIn("coluna \"exige_protecao_respiratoria\"", str(contexto.exception))

    def test_paciente_desconhecido(self):
        with self.assertRaises(ErroRegra) as contexto:
            compilar_problema(_ler(self.legal), self.regras, nome_dominio="d",
                              marcados={"exige-protecao-respiratoria": ["p9"]})
        self.assertIn("p9", str(contexto.exception))

    def test_linha_de_comando_pede_os_dados(self):
        from compilador.__main__ import main
        saida = os.path.join(self.pasta.name, "saida.pddl")
        argumentos = [str(SINTETICAS), "-o", os.devnull, "--problema", self.legal,
                      "--saida-problema", saida]
        with open(os.devnull, "w") as nulo, redirect_stderr(nulo):
            self.assertEqual(main(argumentos), 1)
        self.assertFalse(os.path.exists(saida))


class TestLinhaDeComandoComPlanilha(unittest.TestCase):
    """Planilha de exemplo do Ciclo 2 -> problema legal -> problema compilado."""

    def test_marcas_vem_da_planilha(self):
        from compilador.__main__ import main
        ciclo2.planejador()
        from acsplan.dados import carregador
        from acsplan.geo import roteirizador
        from acsplan.logica.gerador_problema import gerar_problema

        planilha = ciclo2.RAIZ_CICLO2 / "acsplan" / "dados" / "microarea_exemplo.csv"
        dados = carregador.carregar(str(planilha))
        marcados = sorted(p["id"] for p in dados["pacientes"]
                          if p.get("exige_protecao_respiratoria"))
        self.assertTrue(marcados, "a planilha de exemplo deveria ter alguém marcado")

        with tempfile.TemporaryDirectory() as pasta:
            legal = os.path.join(pasta, "legal.pddl")
            saida = os.path.join(pasta, "saida.pddl")
            gerar_problema(dados, roteirizador.roteirizar(dados), legal, dominio="legal")
            with open(os.devnull, "w") as nulo, redirect_stderr(nulo):
                codigo = main([str(SINTETICAS), "-o", os.devnull, "--problema", legal,
                               "--saida-problema", saida, "--dados", str(planilha)])
            self.assertEqual(codigo, 0)
            init = next(x for x in _ler(saida)[2:] if x[0] == ":init")
        fatos = sorted(f[1] for f in init if f[0] == "exige-protecao-respiratoria")
        self.assertEqual(fatos, marcados)
