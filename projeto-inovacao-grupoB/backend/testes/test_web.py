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
class TestTelaDeRegras(unittest.TestCase):
    """Uma pessoa usando a tela: cria regras, erra, abre exemplo, recarrega."""

    @classmethod
    def setUpClass(cls):
        cls.servidor = criar_servidor(0)
        porta = cls.servidor.server_address[1]
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        cls.pasta = tempfile.mkdtemp(prefix="acs-capturas-")
        r = subprocess.run(
            [NODE, str(TESTES_WEB / "e2e-regras.mjs"), f"http://localhost:{porta}/", cls.pasta],
            capture_output=True, text=True, timeout=180, env={**os.environ, "CHROME": CHROME})
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


if __name__ == "__main__":
    unittest.main()
