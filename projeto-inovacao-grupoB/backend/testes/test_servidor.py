"""
Servidor e API da interface web: o servidor de verdade, numa porta livre,
chamado por HTTP como o navegador chamaria.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
import unittest
from pathlib import Path

from compilador import ciclo2
from compilador.regras import CAMPOS, TIPOS_CAMPOS, carregar_regras, ler_regras

from servidor.http import criar_servidor

SINTETICAS = ciclo2.EXEMPLOS / "sinteticas-ciclo2.toml"
AVALIACAO = ciclo2.EXEMPLOS / "avaliacao"


class TestServidor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.servidor = criar_servidor(0)
        cls.porta = cls.servidor.server_address[1]
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pedir(self, metodo: str, caminho: str, corpo=None, host: str | None = None):
        conexao = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=60)
        dados = None if corpo is None else (
            corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode("utf-8"))
        cabecalhos = {"Host": host or f"localhost:{self.porta}"}
        if dados is not None:
            cabecalhos["Content-Type"] = "application/json"
        conexao.request(metodo, caminho, body=dados, headers=cabecalhos)
        resposta = conexao.getresponse()
        texto = resposta.read().decode("utf-8")
        conexao.close()
        tipo = resposta.getheader("Content-Type") or ""
        return resposta.status, (json.loads(texto) if "json" in tipo else texto)

    def planejar(self, pedido: dict, prazo: float = 120) -> dict:
        status, corpo = self.pedir("POST", "/api/planejar", pedido)
        self.assertEqual(status, 202, corpo)
        fim = time.time() + prazo
        while time.time() < fim:
            _, tarefa = self.pedir("GET", f"/api/tarefas/{corpo['id']}")
            if tarefa["estado"] in ("pronta", "erro"):
                return tarefa
            time.sleep(0.2)
        self.fail("o planejamento não terminou no prazo")

    # -- modelos e exemplos --------------------------------------------------

    def test_modelos_descrevem_todos_os_campos(self):
        status, corpo = self.pedir("GET", "/api/modelos")
        self.assertEqual(status, 200)
        self.assertEqual([m["id"] for m in corpo["modelos"]], list(CAMPOS))
        for modelo in corpo["modelos"]:
            self.assertEqual([c["id"] for c in modelo["campos"]], list(CAMPOS[modelo["id"]]))
            for campo in modelo["campos"]:
                self.assertIn(campo["tipo"], ("nome", "inteiro", "booleano", "texto",
                                              "procedimento", "procedimentos", "referencia"))
        self.assertEqual(len(corpo["procedimentos"]), 6)

    def test_todo_campo_tem_tipo(self):
        for modelo, campos in CAMPOS.items():
            for campo in campos:
                self.assertIn((modelo, campo), TIPOS_CAMPOS)

    def test_exemplos(self):
        _, lista = self.pedir("GET", "/api/exemplos")
        nomes = [r["id"] for r in lista["regras"]]
        self.assertIn("sinteticas-ciclo2", nomes)
        self.assertIn("r6-luvas-gestante", nomes)
        self.assertEqual({p["id"] for p in lista["planilhas"]}, {"exemplo-ciclo2", "avaliacao"})
        status, exemplo = self.pedir("GET", "/api/exemplos/regras/sinteticas-ciclo2")
        self.assertEqual(status, 200)
        self.assertEqual(exemplo["toml"], SINTETICAS.read_text(encoding="utf-8"))
        status, _ = self.pedir("GET", "/api/exemplos/regras/nao-existe")
        self.assertEqual(status, 400)

    # -- regras ----------------------------------------------------------------

    def test_validar_campo(self):
        _, ok = self.pedir("POST", "/api/regras/campo",
                           {"modelo": "recurso", "campo": "capacidade", "valor": 4})
        self.assertIsNone(ok["erro"])
        _, ruim = self.pedir("POST", "/api/regras/campo",
                             {"modelo": "recurso", "campo": "nome", "valor": "Álcool Gel"})
        self.assertIn("não serve como nome", ruim["erro"])
        self.assertEqual(ruim["sugestao"], "alcool-gel")
        _, zero = self.pedir("POST", "/api/regras/campo",
                             {"modelo": "recurso", "campo": "capacidade", "valor": 0})
        self.assertIn("maior ou igual a 1", zero["erro"])
        status, _ = self.pedir("POST", "/api/regras/campo",
                               {"modelo": "recurso", "campo": "cor", "valor": 1})
        self.assertEqual(status, 400)

    def test_ler_e_validar_ida_e_volta(self):
        texto = SINTETICAS.read_text(encoding="utf-8")
        _, lido = self.pedir("POST", "/api/regras/ler", {"toml": texto})
        self.assertTrue(lido["ok"], lido)
        _, validado = self.pedir("POST", "/api/regras/validar", {"regras": lido["regras"]})
        self.assertTrue(validado["ok"], validado)
        self.assertEqual(validado["avisos"], [])
        import tomllib
        self.assertEqual(ler_regras(tomllib.loads(validado["toml"])),
                         carregar_regras(str(SINTETICAS)))

    def test_validar_acusa_problemas_e_dominio(self):
        _, resposta = self.pedir("POST", "/api/regras/validar", {"regras": {
            "recurso": [{"nome": "fitas", "capacidade": 3, "custo_reposicao": 1}],
            "preparo": [{"nome": "x", "estado": "y", "custo": 1, "consome": "nada"}]}})
        self.assertFalse(resposta["ok"])
        texto = "\n".join(resposta["problemas"])
        self.assertIn("consome \"nada\"", texto)
        _, dominio = self.pedir("POST", "/api/regras/validar", {"regras": {
            "recurso": [{"nome": "fitas", "capacidade": 3, "custo_reposicao": 1}]}})
        self.assertIn("já é usado pelo domínio", "\n".join(dominio["problemas"]))

    def test_toml_quebrado(self):
        _, resposta = self.pedir("POST", "/api/regras/ler", {"toml": "[[recurso]\n"})
        self.assertFalse(resposta["ok"])

    # -- planejar --------------------------------------------------------------

    def test_planejar_com_regras(self):
        tarefa = self.planejar({"regras_toml": SINTETICAS.read_text(encoding="utf-8"),
                                "planilha": {"sintetica": [4, 2]}})
        self.assertEqual(tarefa["estado"], "pronta", tarefa)
        r = tarefa["resultado"]
        self.assertEqual(r["codigo"], 0)
        self.assertEqual(len(r["paradas"]), 4)
        tarefas = [t for p in r["paradas"] for t in p["tarefas"]]
        self.assertIn("Colocar máscara de proteção respiratória", tarefas)
        self.assertTrue(all(p["paciente"]["lat"] is not None for p in r["paradas"]))
        self.assertIn("ubs", r["pontos"])
        self.assertTrue(any(m.startswith("[4] Plano") for m in tarefa["mensagens"]))
        # caminhos internos do servidor nao aparecem para quem usa a interface
        self.assertIn("Regras: regras.toml", tarefa["mensagens"])
        self.assertEqual(r["regras"], "regras.toml")
        self.assertFalse(any(ciclo2.PROJETO.as_posix() in m or "/tmp" in m
                             for m in tarefa["mensagens"]))

    def test_adiados_tambem_tem_nome_e_coordenadas(self):
        tarefa = self.planejar({"planilha": {"exemplo": "exemplo-ciclo2"},
                                "opcoes": {"max_pacientes": 3}})
        r = tarefa["resultado"]
        self.assertEqual(r["origem"], "backend/acsplan/dados/microarea_exemplo.csv")
        self.assertEqual(len(r["selecao"]["adiados"]), 7)
        for paciente in r["selecao"]["adiados"] + r["selecao"]["selecionados"]:
            self.assertIsNotNone(r["pontos"][paciente]["lat"])
            self.assertTrue(r["pontos"][paciente]["nome"])

    def test_planejar_planilha_enviada_com_marcas(self):
        regras = (AVALIACAO / "regras" / "r6-luvas-gestante.toml").read_text(encoding="utf-8")
        planilha = (AVALIACAO / "microarea-avaliacao.csv").read_text(encoding="utf-8")
        tarefa = self.planejar({"regras_toml": regras, "planilha": {"csv": planilha},
                                "opcoes": {"max_pacientes": 4, "planejador": "ciclo2"}})
        self.assertEqual(tarefa["estado"], "pronta", tarefa)
        self.assertEqual(tarefa["resultado"]["codigo"], 0, tarefa["resultado"])

    def test_planejar_falha_vem_estruturada(self):
        tarefa = self.planejar({"regras_toml": "[[recurso]]\nnome = \"Álcool\"\n",
                                "planilha": {"exemplo": "exemplo-ciclo2"}})
        self.assertEqual(tarefa["estado"], "pronta")
        self.assertEqual(tarefa["resultado"]["falha"]["tipo"], "erro")

    def test_pedidos_invalidos(self):
        for pedido in ({"planilha": {"outra": 1}},
                       {"planilha": {"exemplo": "nao-existe"}},
                       {"opcoes": {"cor": "azul"}},
                       {"opcoes": {"estrategia": "magica"}},
                       {"opcoes": {"limite": "muito"}},
                       {"planilha": {"sintetica": [3]}}):
            status, corpo = self.pedir("POST", "/api/planejar", pedido)
            self.assertEqual(status, 400, (pedido, corpo))
            self.assertIn("erro", corpo)

    # -- seguranca e arquivos ------------------------------------------------

    def test_host_de_fora_e_recusado(self):
        status, _ = self.pedir("GET", "/api/modelos", host="malicioso.example:80")
        self.assertEqual(status, 403)
        status, _ = self.pedir("POST", "/api/regras/ler", {"toml": ""},
                               host="malicioso.example")
        self.assertEqual(status, 403)

    def test_arquivos_da_interface_e_travessia(self):
        status, pagina = self.pedir("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("<html", pagina)
        for caminho in ("/../README.md", "/%2e%2e/README.md", "/../backend/compilador/regras.py"):
            status, _ = self.pedir("GET", caminho)
            self.assertEqual(status, 404, caminho)

    def test_politica_de_conteudo_e_leaflet_local(self):
        conexao = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=10)
        conexao.request("GET", "/", headers={"Host": f"localhost:{self.porta}"})
        resposta = conexao.getresponse()
        resposta.read()
        politica = resposta.getheader("Content-Security-Policy") or ""
        conexao.close()
        self.assertIn("default-src 'self'", politica)
        self.assertIn("script-src 'self'", politica)            # nenhum script de fora
        self.assertIn("img-src 'self' data: https://tile.openstreetmap.org", politica)
        status, leaflet = self.pedir("GET", "/vendor/leaflet/leaflet.js")
        self.assertEqual(status, 200)
        self.assertIn("1.9.4", leaflet[:400])

    def test_json_invalido_e_rota_desconhecida(self):
        status, _ = self.pedir("POST", "/api/regras/ler", b"{nao e json")
        self.assertEqual(status, 400)
        status, _ = self.pedir("GET", "/api/nada")
        self.assertEqual(status, 404)
        status, _ = self.pedir("GET", "/api/tarefas/999999")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
