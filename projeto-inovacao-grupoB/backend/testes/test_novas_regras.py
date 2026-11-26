from __future__ import annotations

import json
import ssl
import tempfile
import tomllib
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from compilador import ErroRegra, ciclo2, compilar_dominio, ler_regras
from compilador.dominio import acoes_que_exigem
from compilador.planejar import construir_parser, executar
from compilador.regras import regras_para_toml
from servidor import tradutor


EXEMPLO = ciclo2.EXEMPLOS / "alternativa-e-turnos.toml"
PLANILHA = ciclo2.EXEMPLOS / "avaliacao" / "microarea-avaliacao.csv"


class TestNovasRegras(unittest.TestCase):
    def test_or_preserva_condicoes_consumo_e_efeito(self):
        dados = tomllib.loads(EXEMPLO.read_text(encoding="utf-8"))
        dados["preparo"].append({"nome": "preparo-extra", "estado": "extra-feito", "custo": 1})
        dados["exigencia"] = [{"nome": "preparo-marcado", "marca": "gestante",
                               "preparo": "preparo-extra", "antes_de": ["pressao"]}]
        dados["recurso"] = [{"nome": "material", "capacidade": 4, "custo_reposicao": 1}]
        dados["consumo"] = [{"procedimento": "pressao", "recurso": "material"}]
        regras = ler_regras(dados)
        self.assertEqual(ler_regras(tomllib.loads(regras_para_toml(regras))), regras)
        legal = ciclo2.planejador().ler_sexp(str(ciclo2.DOMINIO_LEGAL))
        dominio = compilar_dominio(legal, regras)
        base = "aferir-pressao-arterial"
        acoes = {a[1]: a for a in dominio[2:] if a[0] == ":action"}
        self.assertNotIn(base, acoes)
        variantes = {n: a for n, a in acoes.items() if n.startswith(base + "-")}
        self.assertEqual(len(variantes), 4)
        efeitos = []
        exigem = acoes_que_exigem(regras)
        for nome, acao in variantes.items():
            pre = acao[acao.index(":precondition") + 1]
            opcao = "aparelho-conferido" if nome.endswith("-1") else "kit-conferido"
            outra = "kit-conferido" if opcao == "aparelho-conferido" else "aparelho-conferido"
            self.assertIn([opcao, "?ag"], pre)
            self.assertNotIn([outra, "?ag"], pre)
            self.assertIn(["material", "?material"], pre)
            marcado = "preparo-marcado" in nome
            self.assertIn(["gestante", "?p"] if marcado else ["not", ["gestante", "?p"]], pre)
            self.assertEqual(["extra-feito", "?ag"] in pre, marcado)
            self.assertEqual(nome in exigem["preparo-extra"], marcado)
            efeitos.append(acao[acao.index(":effect") + 1])
        self.assertTrue(all(efeito == efeitos[0] for efeito in efeitos))

    def test_or_recusa_referencia_inexistente(self):
        with self.assertRaisesRegex(ErroRegra, "não há preparo"):
            ler_regras({"alternativa": [{"nome": "duas-opcoes", "preparos": ["a", "b"],
                                         "antes_de": ["pressao"]}]})

    def test_dia_respeita_periodo_e_orcamento(self):
        args = construir_parser().parse_args([
            str(EXEMPLO), "--dados", str(PLANILHA), "--manha", "08:00", "240",
            "--tarde", "13:00", "240", "--estrategia", "gbfs", "--planejador", "ciclo2"])
        with patch("compilador.planejar._info"):
            resultado = executar(args)
        self.assertEqual(resultado["codigo"], 0, resultado)
        manha, tarde = resultado["turnos"]
        cedo, depois = (set(t["selecao"]["selecionados"]) for t in (manha, tarde))
        self.assertIn("p3", cedo)
        self.assertFalse(cedo & depois)
        sem_vaga = {p["id"] for p in resultado["nao_alocados"]}
        self.assertEqual(cedo | depois | sem_vaga, {f"p{i}" for i in range(1, 11)})
        self.assertFalse((cedo | depois) & sem_vaga)
        for turno in (manha, tarde):
            self.assertLessEqual(turno["custo_total"], turno["duracao_turno"])
        self.assertIn("Conferir o aparelho", resultado["texto"])

    def test_conflito_de_periodo(self):
        from compilador.turnos import alocar, configurar_turnos

        regras = ler_regras({"periodo": [
            {"nome": "cedo", "marca": "gestante", "turnos": ["manha"]},
            {"nome": "depois", "marca": "gestante", "turnos": ["tarde"]},
        ]})
        args = construir_parser().parse_args(["--manha", "08:00", "240", "--tarde", "13:00", "240"])
        dados = ciclo2.ler_dados(str(PLANILHA), ["gestante"])
        with self.assertRaisesRegex(ErroRegra, "p3.*cedo, depois"):
            alocar(dados, regras, configurar_turnos(args), sem_selecao=False)

    def test_turno_vazio_tem_plano_de_custo_zero(self):
        args = construir_parser().parse_args([
            "--instancia-sintetica", "1", "1", "--manha", "08:00", "240",
            "--tarde", "13:00", "240", "--estrategia", "janelas", "--planejador", "ciclo2"])
        with patch("compilador.planejar._info"):
            resultado = executar(args)
        self.assertEqual(resultado["codigo"], 0, resultado)
        tarde = resultado["turnos"][1]
        self.assertEqual(tarde["custo_total"], 0)
        self.assertEqual(tarde["plano"], [])


class TestTradutor(unittest.TestCase):
    def test_normaliza_nomes_e_referencias_e_preve_tempos_omitidos(self):
        sugestao = {"status": "candidata", "regras": {
            "recurso": [{"nome": "Álcool gel", "capacidade": 5}],
            "preparo": [{"nome": "Higienizar Mãos", "estado": "Mãos Higienizadas",
                         "consome": "alcool-gel"},
                        {"nome": "Lavar com água", "estado": "mãos lavadas", "custo": 2}],
            "alternativa": [{"nome": "Higiene das mãos", "antes_de": ["temperatura"],
                             "preparos": ["higienizar-maos", "Lavar com água"]}],
        }}
        with patch.object(tradutor, "consultar_modelo", return_value=sugestao):
            resultado = tradutor.traduzir({"descricao": "Regra de teste"})
        self.assertEqual(resultado["status"], "candidata", resultado)
        criadas = tomllib.loads(resultado["toml"])
        self.assertEqual(criadas["recurso"][0]["custo_reposicao"], 3)
        self.assertEqual(criadas["preparo"][0]["custo"], 0)
        self.assertEqual(criadas["preparo"][1]["custo"], 2)
        self.assertEqual(criadas["alternativa"][0]["preparos"], ["higienizar-maos", "lavar-com-agua"])
        self.assertEqual(len(resultado["observacoes"]), 2)

    def test_recurso_ainda_precisa_de_capacidade(self):
        sugestao = {"status": "candidata", "regras": {"recurso": [{"nome": "algodão"}]}}
        with patch.object(tradutor, "consultar_modelo", return_value=sugestao):
            resultado = tradutor.traduzir({"descricao": "Repor algodão na UBS"})
        self.assertEqual(resultado["status"], "invalida")
        self.assertTrue(any("capacidade" in problema for problema in resultado["problemas"]))

    def test_gemini_envia_json_e_valida_o_toml_da_resposta(self):
        sugestao = {"status": "candidata", "regras": {"periodo": [
            {"nome": "gestantes-cedo", "marca": "gestante", "turnos": ["manha"]}]}}
        texto = json.dumps(sugestao)
        resposta = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"thought": True, "text": "raciocínio"},
            {"text": texto[:40]},
            {"text": texto[40:]},
        ]}}]}
        ambiente = {"ACS_LLM_PROVEDOR": "gemini", "GEMINI_API_KEY": "chave-google",
                    "ACS_LLM_CHAVE": "chave-anterior", "ACS_LLM_URL": "http://127.0.0.1:11434/v1"}
        with (patch.dict("os.environ", ambiente, clear=True),
              patch.object(tradutor, "_contexto_tls", return_value=Mock()),
              patch.object(tradutor, "urlopen", return_value=BytesIO(
                  json.dumps(resposta).encode())) as rede):
            resultado = tradutor.traduzir({"descricao": "Gestantes só de manhã"})
        pedido = rede.call_args.args[0]
        self.assertEqual(pedido.get_method(), "POST")
        self.assertEqual(pedido.full_url, "https://generativelanguage.googleapis.com/v1beta/"
                         "models/gemini-3.5-flash-lite:generateContent")
        self.assertEqual(pedido.get_header("X-goog-api-key"), "chave-google")
        self.assertIsNone(pedido.get_header("Authorization"))
        corpo = json.loads(pedido.data)
        self.assertEqual(corpo["generationConfig"]["responseMimeType"], "application/json")
        contexto = json.loads(corpo["contents"][0]["parts"][0]["text"])
        self.assertEqual(contexto["descricao"], "Gestantes só de manhã")
        self.assertEqual(resultado["status"], "candidata")
        self.assertIn('turnos = ["manha"]', resultado["toml"])

    def test_gemini_exige_a_propria_chave(self):
        with (patch.dict("os.environ", {"ACS_LLM_PROVEDOR": "gemini",
                                         "ACS_LLM_CHAVE": "chave-anterior"}, clear=True),
              patch.object(tradutor, "urlopen") as rede):
            resultado = tradutor.traduzir({"descricao": "Gestantes só de manhã"})
        self.assertEqual(resultado["status"], "indisponivel")
        self.assertIn("GEMINI_API_KEY", resultado["mensagem"])
        rede.assert_not_called()

    def test_gemini_descarta_traducao_incompleta(self):
        resposta = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {
            "parts": [{"text": '{"status":"candidata"}'}]}}]}
        with (patch.dict("os.environ", {"ACS_LLM_PROVEDOR": "gemini", "GEMINI_API_KEY": "teste"},
                         clear=True),
              patch.object(tradutor, "_contexto_tls", return_value=Mock()),
              patch.object(tradutor, "urlopen", return_value=BytesIO(
                  json.dumps(resposta).encode()))):
            resultado = tradutor.traduzir({"descricao": "Gestantes só de manhã"})
        self.assertEqual(resultado["status"], "indisponivel")

    def test_tls_usa_certificados_do_msys2_quando_a_lista_padrao_esta_vazia(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            certificados = raiz / "usr" / "ssl" / "certs" / "ca-bundle.crt"
            certificados.parent.mkdir(parents=True)
            certificados.touch()
            contexto = Mock()
            contexto.cert_store_stats.return_value = {"x509_ca": 0}
            with (patch.dict("os.environ", {}, clear=True),
                  patch.object(tradutor.sys, "platform", "win32"),
                  patch.object(tradutor.sys, "executable", str(raiz / "ucrt64/bin/python.exe")),
                  patch.object(tradutor.ssl, "create_default_context", return_value=contexto)):
                self.assertIs(tradutor._contexto_tls(), contexto)
            contexto.load_verify_locations.assert_called_once_with(cafile=str(certificados))

    def test_erro_de_certificado_tem_mensagem_especifica(self):
        with (patch.dict("os.environ", {"ACS_LLM_MODELO": "teste", "ACS_LLM_CHAVE": "simulada"},
                         clear=True),
              patch.object(tradutor, "_contexto_tls", return_value=Mock()),
              patch.object(tradutor, "urlopen",
                           side_effect=URLError(ssl.SSLCertVerificationError()))):
            with self.assertRaisesRegex(tradutor.TraducaoIndisponivel, "certificado HTTPS"):
                tradutor.consultar_modelo({})

    def test_429_distingue_cota_de_limite_temporario(self):
        casos = [
            (b'{"error":{"code":"insufficient_quota"}}', {"Retry-After": "10"}, "cota insuficiente"),
            (b'{"error":{"code":"credit_balance_exhausted"}}', {}, "créditos da API acabaram"),
            (b'{"error":{"code":"rate_limit_exceeded"}}', {"Retry-After": "10"}, "Aguarde 10 s"),
            (b'{"error":{"type":"rate_limit_error"}}', {}, "limite temporário"),
            (b"<html>429</html>", {}, "HTTP 429"),
        ]
        for corpo, cabecalhos, mensagem in casos:
            with self.subTest(mensagem=mensagem):
                resposta = HTTPError(None, 429, "", cabecalhos, BytesIO(corpo))
                with (patch.dict("os.environ", {"ACS_LLM_MODELO": "teste",
                                                 "ACS_LLM_CHAVE": "simulada"}, clear=True),
                      patch.object(tradutor, "_contexto_tls", return_value=Mock()),
                      patch.object(tradutor, "urlopen", side_effect=resposta)):
                    resultado = tradutor.traduzir({"descricao": "Regra de teste"})
                self.assertEqual(resultado["status"], "indisponivel")
                self.assertIn(mensagem, resultado["mensagem"])

    def test_traduz_e_valida_com_preparos_existentes(self):
        dados = tomllib.loads(EXEMPLO.read_text(encoding="utf-8"))
        novas = {"alternativa": dados["alternativa"]}
        with patch.object(tradutor, "consultar_modelo",
                          return_value={"status": "candidata", "regras": novas}) as modelo:
            resultado = tradutor.traduzir({"descricao": "Usar uma das conferências",
                                           "regras": {"preparo": dados["preparo"]},
                                           "planilha": "não enviar ao provedor"})
        self.assertEqual(resultado["status"], "candidata")
        self.assertEqual(resultado["regras"], novas)
        self.assertIn("[[alternativa]]", resultado["toml"])
        contexto = modelo.call_args.args[0]
        self.assertEqual(set(contexto), {"descricao", "catalogo", "existentes"})
        self.assertEqual(contexto["existentes"]["preparo"], ["conferir-aparelho", "conferir-kit"])

    def test_descarta_saida_invalida_e_aceita_pedido_de_esclarecimento(self):
        respostas = [
            {"status": "candidata", "regras": {"consumo": [{"procedimento": [], "recurso": "x"}]}},
            {"status": "precisa_esclarecimento", "mensagem": "Qual é o procedimento?"},
        ]
        with patch.object(tradutor, "consultar_modelo", side_effect=respostas):
            pedido = {"descricao": "O procedimento gasta material"}
            self.assertEqual(tradutor.traduzir(pedido)["status"], "invalida")
            self.assertEqual(tradutor.traduzir(pedido)["status"], "precisa_esclarecimento")
