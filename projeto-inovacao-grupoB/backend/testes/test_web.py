"""
Interface web: a logica da tela (com `node --test`) e um teste de ponta a ponta
num Chrome sem janela, contra o servidor de verdade. Os dois sao pulados se
o computador nao tiver Node (>= 22) ou Chrome; o resto da suite nao depende deles.

O navegador usado no teste de ponta a ponta pode ser escolhido com a variavel
de ambiente CHROME (ex.: CHROME=chromium python3 acs.py testes).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

from compilador import ciclo2
from servidor.http import criar_servidor

WEB = ciclo2.PROJETO / "web"
TESTES_WEB = WEB / "testes"


def _node() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        versao = subprocess.run([node, "--version"], capture_output=True, text=True,
                                timeout=10).stdout.strip()
        principal = int(versao.lstrip("v").split(".")[0])
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return node if principal >= 22 else None          # WebSocket global veio no Node 22


def _chrome() -> str | None:
    escolhido = os.environ.get("CHROME")
    if escolhido:
        return shutil.which(escolhido) or (escolhido if os.path.exists(escolhido) else None)
    for nome in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(nome):
            return shutil.which(nome)
    return None


NODE = _node()
CHROME = _chrome()


@unittest.skipUnless(NODE, "Node 22 ou mais novo não encontrado")
class TestLogicaDaTela(unittest.TestCase):

    def test_node_test(self):
        arquivos = sorted(str(p) for p in TESTES_WEB.glob("*.test.mjs"))
        self.assertTrue(arquivos)
        r = subprocess.run([NODE, "--test", *arquivos], capture_output=True, text=True,
                           timeout=120, cwd=WEB)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


@unittest.skipUnless(NODE and CHROME, "precisa de Node 22+ e Chrome/Chromium")
class CenarioNoNavegador(unittest.TestCase):
    """Sobe o servidor, roda um cenario de web/testes/ no Chrome e guarda o
    relato; cada teste confere uma parte dele."""

    CENARIO = ""
    PRAZO = 180

    @classmethod
    def setUpClass(cls):
        cls.servidor = criar_servidor(0)
        porta = cls.servidor.server_address[1]
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        cls.pasta = tempfile.mkdtemp(prefix="acs-capturas-")
        r = subprocess.run(
            [NODE, str(TESTES_WEB / cls.CENARIO), f"http://localhost:{porta}/", cls.pasta],
            capture_output=True, text=True, timeout=cls.PRAZO,
            env={**os.environ, "CHROME": CHROME})
        cls.saida = r.stdout + r.stderr
        try:
            cls.relato = json.loads(r.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            cls.relato = {"ok": False, "erro": f"saída inesperada: {cls.saida[-2000:]}"}

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        if cls.relato.get("ok"):
            shutil.rmtree(cls.pasta, ignore_errors=True)  # na falha, as capturas ficam

    def setUp(self):
        self.assertTrue(self.relato.get("ok"),
                        f"{self.relato.get('erro')} (capturas em {self.pasta})")


class TestTelaDeRegras(CenarioNoNavegador):
    """Uma pessoa usando a tela: cria regras, erra, abre exemplo, recarrega."""

    CENARIO = "e2e-regras.mjs"

    def test_percorreu_todos_os_passos(self):
        self.assertEqual(self.relato["passos"],
                         ["recurso", "preparo", "renomear", "erro", "exemplo", "rascunho"])
        self.assertEqual(self.relato["selo_inicial"], "Sem regras")

    def test_nome_invalido_traz_sugestao(self):
        self.assertIn("alcool-gel", self.relato["erro_do_nome"])

    def test_regras_validas_viram_toml(self):
        previa = self.relato["previa_valida"]
        self.assertIn("[[recurso]]", previa)
        self.assertIn('nome = "alcool-gel"', previa)
        self.assertIn("[[preparo]]", previa)
        self.assertIn('consome = "alcool-gel"', previa)
        self.assertTrue(self.relato["baixar_habilitado"])

    def test_renomear_recurso_atualiza_o_preparo(self):
        self.assertIn('consome = "alcool"', self.relato["previa_renomeada"])
        self.assertNotIn("alcool-gel", self.relato["previa_renomeada"])

    def test_erro_aparece_no_campo_no_cartao_e_bloqueia_download(self):
        self.assertIn("problema", self.relato["selo_com_erro"])
        self.assertTrue(any("capacidade" in p for p in self.relato["problemas"]))
        self.assertTrue(self.relato["cartao_com_erro"])
        self.assertTrue(self.relato["erro_no_campo"])
        self.assertFalse(self.relato["baixar_com_erro"])

    def test_exemplo_aberto_e_identico_ao_arquivo(self):
        import tomllib
        from compilador.regras import carregar_regras, ler_regras
        da_tela = ler_regras(tomllib.loads(self.relato["previa_exemplo"]))
        do_arquivo = carregar_regras(str(ciclo2.EXEMPLOS / "sinteticas-ciclo2.toml"))
        self.assertEqual(da_tela, do_arquivo)
        self.assertEqual(self.relato["quando_marcado"], "visita")

    def test_tema_escuro_e_celular(self):
        self.assertEqual(self.relato["fundo_escuro"], "rgb(18, 22, 28)")
        self.assertFalse(self.relato["rolagem_horizontal"])
        self.assertLess(self.relato["altura_exemplos_celular"], 60)


class TestTelaDePlanejamento(CenarioNoNavegador):
    """Planeja de verdade pela tela: sem regras, com regras e com uma planilha
    a que falta uma coluna."""

    CENARIO = "e2e-planejar.mjs"
    PRAZO = 400

    def test_percorreu_todos_os_passos(self):
        self.assertEqual(self.relato["passos"], ["sem-regras", "com-regras", "impressao", "falha"])
        self.assertTrue(self.relato["aba_pelo_endereco"])
        self.assertEqual(self.relato["endereco_planejar"], "#planejar")

    def test_sem_regras_a_opcao_da_equipe_fica_desabilitada(self):
        self.assertIn("nenhuma regra", self.relato["situacao_sem_regras"])
        self.assertTrue(self.relato["equipe_desabilitada"])

    def test_preenchimento_errado_nem_vai_ao_servidor(self):
        self.assertIn("pelo menos 1", self.relato["erro_preenchimento"])
        self.assertTrue(self.relato["detalhe_sintetica_visivel"])

    def test_roteiro_sem_regras(self):
        self.assertEqual(self.relato["estado_sem_regras"], "roteiro")
        self.assertEqual(self.relato["paradas_sem_regras"], 4)
        self.assertEqual(self.relato["adiados_sem_regras"], 6)
        self.assertIn("Só com as normas da lei", self.relato["origem_sem_regras"])
        self.assertRegex(self.relato["hora_primeira"], r"chegada ≈ 08:\d\d \(\d+ min de turno\)")

    def test_roteiro_com_as_regras_da_tela_de_regras(self):
        self.assertIn("7 regras válidas", self.relato["situacao_com_regras"])
        self.assertTrue(self.relato["equipe_marcada"])
        self.assertEqual(self.relato["estado_com_regras"], "roteiro")
        self.assertEqual(self.relato["paradas_com_regras"], 4)
        self.assertIn("Com as regras da equipe", self.relato["origem_com_regras"])
        self.assertIn("Higienizar as mãos", self.relato["tarefas_com_regras"])

    def test_impressao_mostra_so_o_roteiro(self):
        self.assertEqual(self.relato["impressao"],
                         {"formulario": "none", "cabecalho": "none", "roteiro": "block"})
        self.assertFalse(self.relato["rolagem_horizontal"])

    def test_planilha_sem_coluna_explica_o_erro(self):
        self.assertEqual(self.relato["nome_csv"], "pacientes.csv · 10 pacientes")
        self.assertEqual(self.relato["fonte_csv"], "csv")
        self.assertEqual(self.relato["estado_falha"], "falha")
        self.assertIn("As regras ou a planilha têm problemas", self.relato["falha"])
        self.assertIn("exige_protecao_respiratoria", self.relato["falha"])


if __name__ == "__main__":
    unittest.main()
