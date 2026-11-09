"""
Servidor local da interface web, so com a biblioteca padrao.

    python3 acs.py web [--porta 8000] [--sem-navegador]

Ouve apenas em 127.0.0.1 (outros computadores da rede nao alcancam) e
recusa requisicoes cujo cabecalho Host nao seja local, o que impede um site
aberto no mesmo navegador de usar a API (ataque de "DNS rebinding"). Nao
grava nada fora de pastas temporarias: salvar regras e feito pelo navegador.

Rotas da API (JSON):

    GET  /api/modelos                  modelos, campos, tipos e procedimentos
    GET  /api/exemplos                 regras e planilhas de exemplo
    GET  /api/exemplos/regras/<id>     o TOML de um exemplo
    POST /api/regras/campo             valida um campo {modelo, campo, valor}
    POST /api/regras/validar           valida o conjunto {regras}
    POST /api/regras/ler               le um TOML {toml}
    POST /api/planejar                 inicia um planejamento -> {id}
    GET  /api/tarefas/<id>             progresso e resultado

O resto e servido da pasta web/ do projeto (a interface).
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from compilador import ciclo2

from . import api
from .tarefas import Gerenciador

PASTA_WEB = ciclo2.PROJETO / "web"
TAMANHO_MAXIMO = 3_000_000           # bytes por requisicao (planilha de ate 2 MB)
HOSTS_LOCAIS = ("127.0.0.1", "localhost")

ROTAS_GET = {
    "/api/modelos": lambda _: api.modelos(),
    "/api/exemplos": lambda _: api.exemplos(),
}
ROTAS_POST = {
    "/api/regras/campo": api.validar_campo,
    "/api/regras/validar": api.validar_regras,
    "/api/regras/ler": api.ler_toml,
}


class Manipulador(BaseHTTPRequestHandler):
    server_version = "acs-web"
    tarefas: Gerenciador                  # definido em criar_servidor

    # -- respostas ---------------------------------------------------------

    def _json(self, status: int, corpo) -> None:
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def _erro(self, status: int, mensagem: str) -> None:
        self._json(status, {"erro": mensagem})

    def _host_local(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if host in HOSTS_LOCAIS:
            return True
        self._erro(HTTPStatus.FORBIDDEN, "acesso permitido só a partir deste computador")
        return False

    def _corpo(self) -> dict:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho > TAMANHO_MAXIMO:
            raise api.PedidoInvalido("pedido grande demais (máximo de 3 MB)")
        try:
            dados = json.loads(self.rfile.read(tamanho) or b"{}")
        except json.JSONDecodeError:
            raise api.PedidoInvalido("o corpo do pedido não é um JSON válido") from None
        if not isinstance(dados, dict):
            raise api.PedidoInvalido("o corpo do pedido deve ser um objeto JSON")
        return dados

    # -- GET ---------------------------------------------------------------

    def do_GET(self) -> None:
        if not self._host_local():
            return
        caminho = unquote(urlparse(self.path).path)
        try:
            if caminho in ROTAS_GET:
                return self._json(HTTPStatus.OK, ROTAS_GET[caminho](None))
            if caminho.startswith("/api/exemplos/regras/"):
                nome = caminho.removeprefix("/api/exemplos/regras/")
                return self._json(HTTPStatus.OK, api.exemplo_de_regras(nome))
            if caminho.startswith("/api/tarefas/"):
                tarefa = self.tarefas.consultar(caminho.removeprefix("/api/tarefas/"))
                if tarefa is None:
                    return self._erro(HTTPStatus.NOT_FOUND, "tarefa desconhecida")
                return self._json(HTTPStatus.OK, tarefa.como_dict())
            if caminho.startswith("/api/"):
                return self._erro(HTTPStatus.NOT_FOUND, f"rota desconhecida: {caminho}")
        except api.PedidoInvalido as erro:
            return self._erro(HTTPStatus.BAD_REQUEST, str(erro))
        self._arquivo(caminho)

    def _arquivo(self, caminho: str) -> None:
        relativo = caminho.lstrip("/") or "index.html"
        arquivo = (PASTA_WEB / relativo).resolve()
        if PASTA_WEB.resolve() not in arquivo.parents or not arquivo.is_file():
            return self._erro(HTTPStatus.NOT_FOUND, "arquivo não encontrado")
        dados = arquivo.read_bytes()
        tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(dados)

    # -- POST --------------------------------------------------------------

    def do_POST(self) -> None:
        if not self._host_local():
            return
        caminho = urlparse(self.path).path
        try:
            if caminho in ROTAS_POST:
                return self._json(HTTPStatus.OK, ROTAS_POST[caminho](self._corpo()))
            if caminho == "/api/planejar":
                tarefa = self.tarefas.criar(self._corpo())
                return self._json(HTTPStatus.ACCEPTED, {"id": tarefa.id})
            return self._erro(HTTPStatus.NOT_FOUND, f"rota desconhecida: {caminho}")
        except api.PedidoInvalido as erro:
            return self._erro(HTTPStatus.BAD_REQUEST, str(erro))

    def log_message(self, formato, *argumentos) -> None:      # silencioso
        pass


def criar_servidor(porta: int) -> ThreadingHTTPServer:
    """Servidor em 127.0.0.1; porta 0 escolhe uma livre (usado nos testes)."""
    manipulador = type("ManipuladorAcs", (Manipulador,), {"tarefas": Gerenciador()})
    return ThreadingHTTPServer(("127.0.0.1", porta), manipulador)


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="acs.py web", description="Abre a interface web (só neste computador).")
    analisador.add_argument("--porta", type=int, default=8000)
    analisador.add_argument("--sem-navegador", action="store_true",
                            help="não abre o navegador sozinho")
    args = analisador.parse_args(argv)

    servidor = None
    for porta in range(args.porta, args.porta + 10):       # porta ocupada: tenta a seguinte
        try:
            servidor = criar_servidor(porta)
            break
        except OSError:
            continue
    if servidor is None:
        print(f"Nenhuma porta livre entre {args.porta} e {args.porta + 9}.", file=sys.stderr)
        return 1
    endereco = f"http://localhost:{servidor.server_address[1]}/"
    print(f"Interface aberta em {endereco}  (Ctrl+C para encerrar)", flush=True)
    if not args.sem_navegador:
        threading.Timer(0.5, webbrowser.open, args=(endereco,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()
    return 0
