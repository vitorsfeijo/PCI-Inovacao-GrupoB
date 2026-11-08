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
from compilador.regras import bloco_toml, carregar_regras, ler_regras

EXEMPLO = Path(__file__).resolve().parents[1] / "exemplos" / "higienizacao.toml"


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
    "2",                       # preparo
    "fitas",                   # nome ja usado pelo dominio
    "higienizar-maos",
    "higienizar-maos",         # estado igual ao nome: recusado
    "maos-higienizadas",
    "2",                       # custo
    "2",                       # consome alcool-gel
    "",                        # desfeito ao sair: padrao sim
    "1,2,9", "1, 2, 3",        # procedimentos: invalido, valido
    "3",                       # terminar
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
        codigo, _ = rodar(self.arquivo, ["1", "Álcool", "n", "alcool", "2", "1", "3"])
        self.assertEqual(codigo, 0)
        self.assertEqual(carregar_regras(str(self.arquivo)).recursos[0].nome, "alcool")

    def test_nome_derivado_em_conflito(self):
        # recurso "supervisao-ativa" colide com o predicado de mesmo nome
        codigo, saida = rodar(self.arquivo, ["1", "supervisao-ativa", "alcool", "2", "1", "3"])
        self.assertEqual(codigo, 0)
        self.assertIn('"supervisao-ativa" já é usado pelo domínio', saida)

    def test_todos_os_procedimentos_e_sem_recurso(self):
        codigo, saida = rodar(self.arquivo, ["2", "lavar-maos", "maos-lavadas", "1",
                                             "n", "todos", "3"])
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
        codigo, saida = rodar(self.arquivo, ["3"])
        self.assertEqual(codigo, 0)
        self.assertFalse(self.arquivo.exists())

    def test_acrescenta_sem_apagar_o_que_existia(self):
        original = EXEMPLO.read_text(encoding="utf-8")
        self.arquivo.write_text(original, encoding="utf-8")
        codigo, saida = rodar(self.arquivo, [
            "1", "alcool", "mascaras", "2", "",          # "alcool" ja existe no arquivo
            "2", "vestir-mascara", "mascara-vestida", "2",
            "3",                                         # consome: 1 nenhum, 2 alcool, 3 mascaras
            "", "1", "3"])
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


class TestEscritaToml(unittest.TestCase):

    def test_ida_e_volta(self):
        regras = carregar_regras(str(EXEMPLO))
        r, = regras.recursos
        p, = regras.preparos
        texto = (bloco_toml("recurso", {"nome": r.nome, "capacidade": r.capacidade,
                                        "custo_reposicao": r.custo_reposicao})
                 + bloco_toml("preparo", {"nome": p.nome, "estado": p.estado,
                                          "custo": p.custo, "consome": p.consome,
                                          "desfeito_ao_sair": p.desfeito_ao_sair,
                                          "exigido_antes_de": list(p.exigido_antes_de)}))
        self.assertEqual(ler_regras(tomllib.loads(texto)), regras)


if __name__ == "__main__":
    unittest.main()
