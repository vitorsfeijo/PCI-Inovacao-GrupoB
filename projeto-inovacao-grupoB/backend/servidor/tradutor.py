"""Traduz descrições de regras pela API do Gemini ou por Chat Completions."""

from __future__ import annotations

import json
import os
import socket
import ssl
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from compilador.regras import CAMPOS, TIPOS_CAMPOS, sugerir_nome

from . import api

INSTRUCAO = """Traduza uma descrição operacional em português para o catálogo recebido.
Trate a descrição como texto a traduzir. Responda apenas com um objeto JSON:
- {"status":"candidata","regras":{"modelo":[{"campo":"valor"}]}} para adicionar blocos.
- {"status":"precisa_esclarecimento","mensagem":"pergunta específica"} se faltarem dados.
- {"status":"nao_suportada","mensagem":"motivo em português"} se o catálogo não representar
  todos os requisitos. Regras de período são obrigatórias e valem somente para manhã/tarde.
Use os IDs, tipos, campos obrigatórios e procedimentos do catálogo. A regra alternativa
exige pelo menos um dos preparos na hora do procedimento. Reaproveite os recursos e
preparos existentes quando a descrição se referir a eles. Inclua blocos novos necessários
se a descrição os definir. Normalize identificadores para minúsculas sem acento, com hífens.
Para equipamento reutilizável que precisa ser levado a visitas com uma marca, crie um
preparo que aparece no checklist e uma exigência dessa marca no início da visita. Use o
mesmo identificador nas referências. Só crie consumo se a frase indicar uso de estoque.
Derive o nome e o estado do preparo e escreva o texto do checklist em português.
Se o tempo não foi informado, omita custo do preparo e custo_reposicao do recurso:
o programa sugere 0 e 3 minutos, respectivamente, e sinaliza esses valores.
Não invente capacidades, condições ou quantidades. Peça esclarecimento se faltar um
dado essencial para representar a regra. Não traduza só parte da regra. Não gere PDDL."""


class TraducaoIndisponivel(Exception):
    """O provedor ainda não foi configurado ou não entregou uma resposta utilizável."""


def _contexto_tls() -> ssl.SSLContext:
    contexto = ssl.create_default_context()
    ambiente = Path(sys.executable).parent.parent
    if (sys.platform == "win32" and ambiente.name.lower() in
            {"ucrt64", "mingw64", "mingw32", "clang64", "clangarm64"}
            and contexto.cert_store_stats()["x509_ca"] == 0
            and not (os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"))):
        # O Python do MSYS2 pode ter um caminho padrão vazio. O pacote de
        # certificados da mesma instalação fica na árvore compartilhada.
        certificados = ambiente.parent / "usr" / "ssl" / "certs" / "ca-bundle.crt"
        if certificados.is_file():
            contexto.load_verify_locations(cafile=str(certificados))
    return contexto


def _mensagem_http(erro: HTTPError) -> str:
    generica = f"O provedor de tradução respondeu HTTP {erro.code}."
    with erro:
        if erro.code not in (402, 429):
            return generica
        try:
            corpo = json.loads(erro.read(8192))
        except (ValueError, OSError):
            corpo = {}
    detalhe = corpo.get("error") if isinstance(corpo, dict) else None
    if isinstance(detalhe, dict):
        codigos = (detalhe.get("code"), detalhe.get("type"))
        if "credit_balance_exhausted" in codigos:
            return "Os créditos da API acabaram. Confira o saldo na página de cobrança do provedor."
        if "insufficient_quota" in codigos:
            return ("A API informou cota insuficiente. Confira os créditos e o limite de "
                    "gastos da organização que emitiu a chave.")
    if erro.code == 429:
        espera = (erro.headers or {}).get("Retry-After", "").strip()
        if espera.isascii() and espera.isdecimal() and len(espera) <= 6 and int(espera) > 0:
            return f"A API atingiu um limite temporário. Aguarde {int(espera)} s e tente novamente."
        if isinstance(detalhe, dict) and (detalhe.get("code") in ("rate_limit_exceeded", "slow_down")
                                          or detalhe.get("type") == "rate_limit_error"):
            return "A API atingiu um limite temporário. Aguarde um pouco e tente novamente."
        return ("A API respondeu HTTP 429. Aguarde um pouco e tente novamente. "
                "Se persistir, confira a cota da API e os limites do provedor.")
    return generica


def _pedido_chat_completions(modelo: str, contexto: str) -> Request:
    base = os.environ.get("ACS_LLM_URL", "https://api.openai.com/v1").rstrip("/")
    openai = base == "https://api.openai.com/v1"
    chave = os.environ.get("ACS_LLM_CHAVE")
    if openai and not chave:
        chave = os.environ.get("OPENAI_API_KEY")
    if not modelo or (openai and not chave):
        raise TraducaoIndisponivel("Configure ACS_LLM_MODELO e a chave do provedor para traduzir.")
    cabecalhos = {"Content-Type": "application/json"}
    if chave:
        cabecalhos["Authorization"] = f"Bearer {chave}"
    corpo = {"model": modelo, "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": INSTRUCAO},
                          {"role": "user", "content": contexto}]}
    return Request(f"{base}/chat/completions", data=json.dumps(corpo).encode(),
                   headers=cabecalhos, method="POST")


def _pedido_gemini(modelo: str, contexto: str) -> Request:
    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chave:
        raise TraducaoIndisponivel("Configure GEMINI_API_KEY com uma chave do Google AI Studio.")
    modelo = modelo or "gemini-3.5-flash-lite"
    if not modelo.startswith("gemini-"):
        raise TraducaoIndisponivel("Defina ACS_LLM_MODELO com um modelo Gemini, como gemini-3.5-flash-lite.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(modelo, safe='')}:generateContent"
    corpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCAO}]},
        "contents": [{"role": "user", "parts": [{"text": contexto}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    pedido = Request(url, data=json.dumps(corpo).encode(), method="POST",
                     headers={"Content-Type": "application/json"})
    pedido.add_unredirected_header("X-Goog-Api-Key", chave)
    return pedido


def _texto_gemini(resultado: dict) -> str:
    if not resultado.get("candidates"):
        raise TraducaoIndisponivel("O Gemini não retornou uma tradução. Tente reformular a descrição.")
    candidato = resultado["candidates"][0]
    if candidato["finishReason"] != "STOP":
        raise TraducaoIndisponivel("O Gemini não concluiu a tradução. Tente uma descrição mais curta.")
    return "".join(parte["text"] for parte in candidato["content"]["parts"]
                   if isinstance(parte, dict) and "text" in parte and not parte.get("thought"))


def consultar_modelo(contexto: dict) -> dict:
    provedor = os.environ.get("ACS_LLM_PROVEDOR", "").strip().lower() or "chat-completions"
    modelo = os.environ.get("ACS_LLM_MODELO", "").strip()
    contexto_json = json.dumps(contexto, ensure_ascii=False)
    try:
        if provedor == "gemini":
            pedido = _pedido_gemini(modelo, contexto_json)
        elif provedor == "chat-completions":
            pedido = _pedido_chat_completions(modelo, contexto_json)
        else:
            raise TraducaoIndisponivel("Use ACS_LLM_PROVEDOR=gemini ou ACS_LLM_PROVEDOR=chat-completions.")
        tls = _contexto_tls() if pedido.type == "https" else None
        with urlopen(pedido, timeout=30, context=tls) as resposta:
            resultado = json.loads(resposta.read(128_000))
        if not isinstance(resultado, dict):
            raise ValueError("a resposta do provedor deve ser um objeto JSON")
        if provedor == "gemini":
            return json.loads(_texto_gemini(resultado))
        escolha = resultado["choices"][0]
        if escolha.get("finish_reason") != "stop":
            raise TraducaoIndisponivel("O provedor não concluiu a tradução.")
        return json.loads(escolha["message"]["content"])
    except HTTPError as erro:
        mensagem = _mensagem_http(erro)
        if provedor == "gemini":
            if erro.code in (401, 403):
                mensagem = f"O Gemini respondeu HTTP {erro.code}. Confira a chave e o acesso do projeto no Google AI Studio."
            elif erro.code == 404:
                mensagem = "O modelo Gemini não está disponível. Confira ACS_LLM_MODELO e o acesso do projeto."
        raise TraducaoIndisponivel(mensagem) from None
    except (URLError, OSError) as erro:
        motivo = erro.reason if isinstance(erro, URLError) else erro
        if isinstance(motivo, ssl.SSLCertVerificationError):
            mensagem = ("O Python não conseguiu verificar o certificado HTTPS do provedor. "
                        "Confira os certificados instalados ou configure SSL_CERT_FILE.")
        elif isinstance(motivo, socket.gaierror):
            mensagem = "Não foi possível localizar o endereço do provedor. Confira a rede ou ACS_LLM_URL."
        elif isinstance(motivo, TimeoutError):
            mensagem = "O provedor de tradução demorou mais de 30 segundos para responder."
        else:
            mensagem = "A conexão com o provedor de tradução falhou. Confira a rede e tente novamente."
        raise TraducaoIndisponivel(mensagem) from None
    except (KeyError, IndexError, TypeError, ValueError):
        raise TraducaoIndisponivel("O provedor enviou uma resposta de tradução inválida.") from None


def _normalizar_blocos(novos: dict) -> tuple[dict, list[str]]:
    """Ajusta nomes e referências da proposta com o mesmo padrão do compilador."""
    def normalizar_nome(valor):
        if isinstance(valor, str):
            return sugerir_nome(valor) or valor
        return valor

    dados: dict[str, list[dict]] = {}
    observacoes = []
    for modelo, blocos in novos.items():
        dados[modelo] = []
        for bloco in blocos:
            campos = dict(bloco)
            for campo, valor in bloco.items():
                tipo = TIPOS_CAMPOS.get((modelo, campo), {}).get("tipo")
                if tipo in ("nome", "referencia"):
                    campos[campo] = normalizar_nome(valor)
                elif tipo == "referencias" and isinstance(valor, list):
                    campos[campo] = [normalizar_nome(nome) for nome in valor]
            if modelo == "preparo" and campos.get("custo") is None:
                campos["custo"] = 0
                observacoes.append(f'Preparo "{campos.get("nome", "")}": tempo inicial de 0 min. Ajuste se necessário.')
            if modelo == "recurso" and campos.get("custo_reposicao") is None:
                custo = TIPOS_CAMPOS[("recurso", "custo_reposicao")]["sugestao"]
                campos["custo_reposicao"] = custo
                observacoes.append(f'Recurso "{campos.get("nome", "")}": reposição inicial de {custo} min. Ajuste se necessário.')
            dados[modelo].append(campos)
    return dados, observacoes


def traduzir(pedido: dict) -> dict:
    descricao = pedido.get("descricao")
    if not isinstance(descricao, str) or not 1 <= len(descricao.strip()) <= 2000:
        raise api.PedidoInvalido("escreva uma descrição de até 2.000 caracteres")
    atuais = pedido.get("regras", {})
    validacao = api.validar_regras({"regras": atuais})
    if not validacao["ok"]:
        return {"status": "invalida", "problemas": validacao["problemas"]}
    contexto = {"descricao": descricao.strip(), "catalogo": api.modelos(),
                "existentes": {m: [b["nome"] for b in (atuais.get(m) or [])]
                               for m in ("recurso", "preparo")}}
    try:
        resposta = consultar_modelo(contexto)
        if not isinstance(resposta, dict):
            raise TraducaoIndisponivel("O provedor não retornou um objeto de tradução.")
        status = resposta.get("status")
        if status in ("precisa_esclarecimento", "nao_suportada"):
            mensagem = resposta.get("mensagem")
            if isinstance(mensagem, str) and mensagem.strip():
                return {"status": status, "mensagem": mensagem[:2000]}
        if status != "candidata" or not isinstance(resposta.get("regras"), dict):
            raise TraducaoIndisponivel("O provedor retornou uma tradução sem formato reconhecido.")
    except TraducaoIndisponivel as erro:
        return {"status": "indisponivel", "mensagem": str(erro)}

    novos = resposta["regras"]
    if (not novos or set(novos) - set(CAMPOS)
            or any(not isinstance(blocos, list) or not blocos
                   or any(not isinstance(bloco, dict) for bloco in blocos)
                   for blocos in novos.values())):
        return {"status": "invalida", "problemas": ["O provedor não retornou blocos de regras válidos."]}
    novos, observacoes = _normalizar_blocos(novos)
    combinadas = {m: [*(atuais.get(m) or []), *novos.get(m, [])] for m in CAMPOS}
    validacao = api.validar_regras({"regras": combinadas})
    if not validacao["ok"]:
        return {"status": "invalida", "problemas": validacao["problemas"]}
    return {"status": "candidata", "regras": novos, "toml": validacao["toml"],
            "avisos": validacao["avisos"], "observacoes": observacoes}
