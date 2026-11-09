"""
Operacoes da API, como funcoes puras: recebem e devolvem dicionarios
(serializaveis em JSON), sem nada de HTTP. O servidor (http.py) so traduz
requisicoes em chamadas a estas funcoes; os testes as chamam direto.

Tudo reaproveita o compilador: as mesmas descricoes de campo, os mesmos
validadores e as mesmas mensagens do assistente e da linha de comando.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from compilador import ciclo2
from compilador.dominio import compilar_dominio
from compilador.regras import (CAMPOS, DESCRICAO_CAMPOS, DESCRICAO_MODELOS,
                               DESCRICAO_PROCEDIMENTOS, PROCEDIMENTOS, TIPOS_CAMPOS,
                               VALIDADORES, ErroRegra, avisos, ler_regras,
                               regras_para_dados, regras_para_toml, sugerir_nome)


class PedidoInvalido(ValueError):
    """O pedido nao tem o formato esperado (vira erro 400)."""


# ----------------------------------------------------------------------------
#  modelos
# ----------------------------------------------------------------------------

def modelos() -> dict:
    """Tudo o que uma interface precisa para montar os formularios."""
    return {
        "modelos": [
            {"id": modelo,
             "titulo": DESCRICAO_MODELOS[modelo][0],
             "descricao": DESCRICAO_MODELOS[modelo][1],
             "campos": [{"id": campo,
                         "obrigatorio": obrigatorio,
                         "descricao": DESCRICAO_CAMPOS.get((modelo, campo), ""),
                         **TIPOS_CAMPOS[(modelo, campo)]}
                        for campo, obrigatorio in CAMPOS[modelo].items()]}
            for modelo in CAMPOS
        ],
        "procedimentos": [{"id": p, "descricao": DESCRICAO_PROCEDIMENTOS[p]}
                          for p in PROCEDIMENTOS],
    }


# ----------------------------------------------------------------------------
#  regras
# ----------------------------------------------------------------------------

def validar_campo(pedido: dict) -> dict:
    """Valida UM campo, como o assistente faz a cada resposta.
    Pedido: {"modelo", "campo", "valor"}. Resposta: {"erro", "sugestao"}."""
    modelo, campo = pedido.get("modelo"), pedido.get("campo")
    if (modelo, campo) not in TIPOS_CAMPOS:
        raise PedidoInvalido(f"campo desconhecido: {modelo}.{campo}")
    valor = pedido.get("valor")
    erro = VALIDADORES[campo](valor)
    sugestao = None
    if erro and TIPOS_CAMPOS[(modelo, campo)]["tipo"] in ("nome", "referencia") \
            and isinstance(valor, str):
        sugestao = sugerir_nome(valor) or None
    return {"erro": erro, "sugestao": sugestao}


def validar_regras(pedido: dict) -> dict:
    """Valida o conjunto inteiro, inclusive contra o dominio legal.
    Pedido: {"regras": {"recurso": [...], "preparo": [...], ...}}.
    Resposta: {"ok", "problemas", "avisos", "toml"}."""
    dados = pedido.get("regras")
    if not isinstance(dados, dict):
        raise PedidoInvalido("o pedido precisa de 'regras', um objeto por modelo")
    dados = {modelo: blocos for modelo, blocos in dados.items() if blocos}
    try:
        regras = ler_regras(dados)
        legal = ciclo2.planejador().ler_sexp(str(ciclo2.DOMINIO_LEGAL))
        compilar_dominio(legal, regras)
    except ErroRegra as erro:
        return {"ok": False, "problemas": erro.problemas, "avisos": [], "toml": None}
    return {"ok": True, "problemas": [], "avisos": avisos(regras),
            "toml": regras_para_toml(regras)}


def ler_toml(pedido: dict) -> dict:
    """Le um arquivo de regras (o texto do TOML) para os formularios.
    Resposta: {"ok", "regras", "problemas"}."""
    texto = pedido.get("toml")
    if not isinstance(texto, str):
        raise PedidoInvalido("o pedido precisa de 'toml', o texto do arquivo")
    try:
        regras = ler_regras(tomllib.loads(texto))
    except tomllib.TOMLDecodeError as erro:
        return {"ok": False, "regras": {}, "problemas": [
            f"o arquivo não segue o formato TOML: {erro}"]}
    except ErroRegra as erro:
        return {"ok": False, "regras": {}, "problemas": erro.problemas}
    return {"ok": True, "regras": regras_para_dados(regras), "problemas": []}


# ----------------------------------------------------------------------------
#  exemplos
# ----------------------------------------------------------------------------

def _primeira_linha_de_comentario(arquivo: Path) -> str:
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") and linha.strip("# ").strip():
            return linha.strip("# ").strip()
    return ""


def _arquivos_de_regras() -> dict[str, Path]:
    pastas = [ciclo2.EXEMPLOS, ciclo2.EXEMPLOS / "avaliacao" / "regras"]
    return {arquivo.stem: arquivo for pasta in pastas
            for arquivo in sorted(pasta.glob("*.toml"))}


PLANILHAS = {
    "exemplo-ciclo2": ("Planilha de exemplo do Ciclo 2 (10 pacientes)",
                       lambda: ciclo2.PLANILHA_EXEMPLO),
    "avaliacao": ("Planilha de avaliação (10 pacientes, com as marcas das regras novas)",
                  lambda: ciclo2.EXEMPLOS / "avaliacao" / "microarea-avaliacao.csv"),
}


def exemplos() -> dict:
    return {
        "regras": [{"id": nome, "descricao": _primeira_linha_de_comentario(arquivo)}
                   for nome, arquivo in _arquivos_de_regras().items()],
        "planilhas": [{"id": chave, "descricao": descricao}
                      for chave, (descricao, _) in PLANILHAS.items()],
    }


def exemplo_de_regras(nome: str) -> dict:
    arquivos = _arquivos_de_regras()
    if nome not in arquivos:
        raise PedidoInvalido(f"exemplo de regras desconhecido: {nome}")
    return {"id": nome, "toml": arquivos[nome].read_text(encoding="utf-8")}


def caminho_da_planilha(chave: str) -> Path:
    if chave not in PLANILHAS:
        raise PedidoInvalido(f"planilha de exemplo desconhecida: {chave}")
    return PLANILHAS[chave][1]()
