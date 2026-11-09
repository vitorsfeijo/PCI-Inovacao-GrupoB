"""
Testes do assistente interativo, com respostas programadas.
"""

from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from compilador import ciclo2, compilar_dominio
from compilador.assistente import main
from compilador.regras import carregar_regras, ler_regras, regras_para_toml

EXEMPLO = Path(__file__).resolve().parents[2] / "exemplos" / "higienizacao.toml"
SINTETICAS = EXEMPLO.with_name("sinteticas-ciclo2.toml")


def rodar(arquivo: Path, respostas: list[str]) -> tuple[int, str]:
    """Roda o assistente. Respostas esgotadas equivalem a Ctrl+D."""
    fila = iter(respostas)
    saida: list[str] = []

    def entrada(pergunta: str) -> str:
        saida.append(pergunta)
        try:
            return next(fila)
        except StopIteration:
            raise EOFError from None

    codigo = main([str(arquivo)], entrada=entrada, escrever=saida.append)
    return codigo, "\n".join(saida)


# Sessao completa com erros de digitacao no meio.
SESSAO = [
    "1",                       # recurso
    "Álcool Gel", "s",         # nome invalido, aceita a sugestao
    "seis", "0", "4",          # capacidade: texto, zero, valido
    "",                        # custo de reposicao: padrao 3
    "",                        # acao de reposicao: aceita repor-alcool-gel
    "",                        # texto no roteiro: Enter (fica de fora)
    "2",                       # preparo
    "fitas",                   # nome ja usado pelo dominio
    "higienizar-maos",
    "higienizar-maos",         # estado igual ao nome: recusado
    "maos-higienizadas",
    "2",                       # custo
    "2",                       # consome alcool-gel
    "",                        # desfeito ao sair: padrao sim
    "1,2,9", "1, 2, 3",        # procedimentos: invalido, valido
    "Higienizar as mãos",      # texto no roteiro
    "5",                       # terminar
]


class TestAssistente(unittest.TestCase):

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.arquivo = Path(self.pasta.name) / "regras.toml"

    def tearDown(self):
        self.pasta.cleanup()

    def test_sessao_completa(self):
        codigo, saida = rodar(self.arquivo, SESSAO)
        self.assertEqual(codigo, 0)
        regras = carregar_regras(str(self.arquivo))
        recurso, = regras.recursos
        preparo, = regras.preparos
        self.assertEqual((recurso.nome, recurso.capacidade, recurso.custo_reposicao),
                         ("alcool-gel", 4, 3))
        self.assertEqual((preparo.nome, preparo.estado, preparo.custo, preparo.consome),
                         ("higienizar-maos", "maos-higienizadas", 2, "alcool-gel"))
        self.assertTrue(preparo.desfeito_ao_sair)
        self.assertEqual(preparo.exigido_antes_de, ("pressao", "glicemia", "temperatura"))
        self.assertEqual(preparo.texto, "Higienizar as mãos")
        self.assertIsNone(recurso.texto)
        # cada erro foi explicado
        self.assertIn('digite um número inteiro. Recebido: "seis"', saida)
        self.assertIn("deve ser maior ou igual a 1", saida)
        self.assertIn('"fitas" já é usado pelo domínio de entrada', saida)
        self.assertIn('já é usado pelo preparo "higienizar-maos"', saida)
        self.assertIn("use números de 1 a 6", saida)
        # e o arquivo compila
        dominio = ciclo2.planejador().ler_sexp(str(ciclo2.DOMINIO_LEGAL))
        compilar_dominio(dominio, regras)

    def test_sugestao_recusada_pergunta_de_novo(self):
        codigo, _ = rodar(self.arquivo, ["1", "Álcool", "n", "alcool", "2", "1", "", "", "5"])
        self.assertEqual(codigo, 0)
        self.assertEqual(carregar_regras(str(self.arquivo)).recursos[0].nome, "alcool")

    def test_nome_derivado_em_conflito(self):
        # recurso "supervisao-ativa" colide com o predicado de mesmo nome
        codigo, saida = rodar(self.arquivo, ["1", "supervisao-ativa", "alcool", "2", "1", "", "", "5"])
        self.assertEqual(codigo, 0)
        self.assertIn('"supervisao-ativa" já é usado pelo domínio', saida)

    def test_todos_os_procedimentos_e_sem_recurso(self):
        codigo, saida = rodar(self.arquivo, ["2", "lavar-maos", "maos-lavadas", "1",
                                             "n", "todos", "", "5"])
        self.assertEqual(codigo, 0)
        self.assertIn("Nenhum recurso declarado ainda", saida)
        preparo, = carregar_regras(str(self.arquivo)).preparos
        self.assertIsNone(preparo.consome)
        self.assertFalse(preparo.desfeito_ao_sair)
        self.assertEqual(len(preparo.exigido_antes_de), 6)
        self.assertIn("basta fazê-lo uma vez", saida)       # aviso no fim

    def test_cancelar_nao_grava(self):
        codigo, saida = rodar(self.arquivo, ["1", "alcool"])   # Ctrl+D no meio
        self.assertEqual(codigo, 1)
        self.assertIn("Nada foi gravado", saida)
        self.assertFalse(self.arquivo.exists())

    def test_terminar_sem_regras_nao_grava(self):
        codigo, saida = rodar(self.arquivo, ["5"])
        self.assertEqual(codigo, 0)
        self.assertFalse(self.arquivo.exists())

    def test_acrescenta_sem_apagar_o_que_existia(self):
        original = EXEMPLO.read_text(encoding="utf-8")
        self.arquivo.write_text(original, encoding="utf-8")
        codigo, saida = rodar(self.arquivo, [
            "1", "alcool", "mascaras", "2", "", "", "",  # "alcool" ja existe no arquivo
            "2", "vestir-mascara", "mascara-vestida", "2",
            "3",                                         # consome: 1 nenhum, 2 alcool, 3 mascaras
            "", "1", "", "5"])
        self.assertEqual(codigo, 0)
        self.assertIn('"alcool" já é usado pelo recurso "alcool"', saida)
        texto = self.arquivo.read_text(encoding="utf-8")
        self.assertTrue(texto.startswith(original))        # comentarios preservados
        regras = carregar_regras(str(self.arquivo))
        self.assertEqual([r.nome for r in regras.recursos], ["alcool", "mascaras"])
        self.assertEqual(regras.preparos[1].consome, "mascaras")

    def test_arquivo_existente_com_erro_nao_e_tocado(self):
        self.arquivo.write_text('[[recurso]]\nnome = "Álcool"\n', encoding="utf-8")
        codigo, saida = rodar(self.arquivo, [])
        self.assertEqual(codigo, 1)
        self.assertIn("tem problemas", saida)
        self.assertEqual(self.arquivo.read_text(encoding="utf-8"),
                         '[[recurso]]\nnome = "Álcool"\n')


    def test_recria_as_regras_sinteticas_do_ciclo2(self):
        """As tres regras do dominio estendido, inteiras, so respondendo perguntas."""
        codigo, saida = rodar(self.arquivo, [
            "1", "alcool", "6", "3", "", "solução alcoólica",     # recurso
            "2", "higienizar-maos", "maos-higienizadas", "2",     # preparo
            "2", "", "1,2,3,4,5", "Higienizar as mãos",           #   consome alcool
            "1", "mascaras", "2", "3", "", "máscaras",            # recurso
            "2", "vestir-mascara", "mascara-vestida", "2",        # preparo
            "3", "", "", "Colocar máscara de proteção respiratória",
            "4", "1", "protecao", "exige-protecao-respiratoria",  # exigencia na visita
            "2", "", "Conferir a proteção antes de entrar",       #   vestir-mascara, custo 1
            "1", "coletor", "3", "3", "trocar-coletor",           # recurso
            "coletor de perfurocortante",
            "3", "2", "3", "",                                    # consumo: glicemia, coletor, 1
            "5"])
        self.assertEqual(codigo, 0, saida)
        self.assertEqual(carregar_regras(str(self.arquivo)),
                         carregar_regras(str(SINTETICAS)))
        self.assertNotIn("Aviso", saida)

    def test_texto_longo_e_recusado(self):
        codigo, saida = rodar(self.arquivo, ["1", "alcool", "2", "", "", "x" * 81,
                                             "álcool em gel", "5"])
        self.assertEqual(codigo, 0)
        self.assertIn("no máximo 80 caracteres", saida)
        self.assertEqual(carregar_regras(str(self.arquivo)).recursos[0].texto,
                         "álcool em gel")

    def test_consumo_e_exigencia_exigem_declaracao_previa(self):
        codigo, saida = rodar(self.arquivo, ["3", "4", "5"])
        self.assertEqual(codigo, 0)
        self.assertIn("Nenhum recurso declarado ainda. Declare o recurso antes.", saida)
        self.assertIn("Nenhum preparo declarado ainda. Declare o preparo antes.", saida)
        self.assertFalse(self.arquivo.exists())

    def test_consumo_repetido_nao_e_adicionado(self):
        codigo, saida = rodar(self.arquivo, ["1", "coletor", "3", "", "", "",
                                             "3", "2", "1", "", "3", "2", "1", "5"])
        self.assertEqual(codigo, 0)
        self.assertIn("esse consumo já foi declarado", saida)
        self.assertEqual(len(carregar_regras(str(self.arquivo)).consumos), 1)

    def test_nomes_gerados_pela_exigencia_sao_conferidos(self):
        # "protecao" gera "protecao-conferida"; com ela ja usada, recusa
        codigo, saida = rodar(self.arquivo, [
            "2", "lavar", "protecao-conferida", "1", "n", "1", "",
            "4", "1", "protecao", "outra", "marca-x", "1", "", "", "5"])
        self.assertEqual(codigo, 0, saida)
        self.assertIn('esse nome geraria "protecao-conferida", que já é usado '
                      'pelo preparo "lavar"', saida)
        self.assertEqual(carregar_regras(str(self.arquivo)).exigencias[0].nome, "outra")


    def test_consumo_com_quantidade(self):
        codigo, saida = rodar(self.arquivo, [
            "1", "fitas-extra", "4", "", "", "",          # recurso com capacidade 4
            "3", "2", "1", "5", "2", "5"])                # glicemia gasta 5 (recusado), 2
        self.assertEqual(codigo, 0, saida)
        self.assertIn("só comporta 4 por carga", saida)
        self.assertEqual(carregar_regras(str(self.arquivo)).consumos[0].quantidade, 2)

    def test_exigencia_antes_de_procedimento(self):
        codigo, saida = rodar(self.arquivo, [
            "1", "luvas", "3", "", "", "",                           # recurso
            "2", "calcar-luvas", "luvas-calcadas", "1", "2", "", "", "",  # preparo
            "4", "2", "luvas-gestante", "gestante", "1",            # exigencia por procedimento
            "", "2",                                                 # nenhum (recusado), glicemia
            "5"])
        self.assertEqual(codigo, 0, saida)
        self.assertIn("escolha pelo menos um procedimento", saida)
        exigencia, = carregar_regras(str(self.arquivo)).exigencias
        self.assertEqual(exigencia.antes_de, ("glicemia",))
        self.assertFalse(exigencia.no_inicio_da_visita)
        self.assertNotIn("custo", self.arquivo.read_text(encoding="utf-8").split("[[exigencia]]")[1])


class TestEscritaToml(unittest.TestCase):

    def test_ida_e_volta_com_todos_os_modelos(self):
        regras = carregar_regras(str(SINTETICAS))
        self.assertEqual(ler_regras(tomllib.loads(regras_para_toml(regras))), regras)

    def test_ida_e_volta(self):
        regras = carregar_regras(str(EXEMPLO))
        self.assertEqual(ler_regras(tomllib.loads(regras_para_toml(regras))), regras)


if __name__ == "__main__":
    unittest.main()
