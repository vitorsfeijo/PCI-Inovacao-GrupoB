"""
Leitura do arquivo de regras (TOML) para estruturas Python.

Modelos suportados nesta etapa:

    A. [[recurso]]  estoque finito, reposto so na UBS
    B. [[preparo]]  algo que o ACS faz antes de atender, podendo consumir
                    um recurso e sendo desfeito ao sair da casa
    C. pre-requisito, escrito como o campo `exigido_antes_de` do preparo

Esta etapa so confere o formato de cada campo. As conferencias que cruzam
regras com o dominio (nomes repetidos, recurso inexistente etc.) ficam no
compilador, que e quem conhece o dominio.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass

# Nome usado na regra -> acao do dominio legal.
PROCEDIMENTOS = {
    "pressao": "aferir-pressao-arterial",
    "glicemia": "medir-glicemia-capilar",
    "temperatura": "aferir-temperatura-axilar",
    "medicacao": "orientar-administracao-medicacao",
    "antropometria": "verificacao-antropometrica",
    "vacinal": "verificar-caderneta-vacinal",
}

# Nomes PDDL: minusculas, digitos e hifen, comecando por letra.
_NOME_VALIDO = re.compile(r"^[a-z][a-z0-9-]*$")


class ErroRegra(ValueError):
    """Regra mal escrita. A mensagem e para quem escreveu a regra."""


@dataclass(frozen=True)
class Recurso:
    nome: str
    capacidade: int
    custo_reposicao: int

    @property
    def predicado(self) -> str:
        return self.nome

    @property
    def predicado_maximo(self) -> str:
        return f"nivel-maximo-{self.nome}"

    @property
    def acao_reposicao(self) -> str:
        return f"repor-{self.nome}"


@dataclass(frozen=True)
class Preparo:
    nome: str
    estado: str
    custo: int
    consome: str | None
    desfeito_ao_sair: bool
    exigido_antes_de: tuple[str, ...]


@dataclass(frozen=True)
class Regras:
    recursos: tuple[Recurso, ...]
    preparos: tuple[Preparo, ...]


# ----------------------------------------------------------------------------
#  leitura de campos
# ----------------------------------------------------------------------------

def _onde(modelo: str, indice: int, tabela: dict) -> str:
    nome = tabela.get("nome")
    return f"{modelo} '{nome}'" if isinstance(nome, str) else f"{modelo} n. {indice + 1}"


def _nome(valor, onde: str, campo: str) -> str:
    if not isinstance(valor, str) or not _NOME_VALIDO.match(valor):
        raise ErroRegra(
            f"{onde}: o campo '{campo}' deve ser um nome em minusculas, sem "
            f"acento nem espaco, usando hifen para separar palavras "
            f"(ex.: 'maos-higienizadas'). Recebido: {valor!r}")
    return valor


def _inteiro(valor, onde: str, campo: str, minimo: int) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < minimo:
        raise ErroRegra(f"{onde}: o campo '{campo}' deve ser um numero inteiro "
                        f"maior ou igual a {minimo}. Recebido: {valor!r}")
    return valor


def _conferir_campos(tabela: dict, onde: str, obrigatorios: set[str],
                     opcionais: set[str]) -> None:
    faltando = sorted(obrigatorios - tabela.keys())
    if faltando:
        raise ErroRegra(f"{onde}: falta(m) o(s) campo(s) {', '.join(faltando)}")
    desconhecidos = sorted(tabela.keys() - obrigatorios - opcionais)
    if desconhecidos:
        validos = ", ".join(sorted(obrigatorios | opcionais))
        raise ErroRegra(f"{onde}: campo(s) desconhecido(s) {', '.join(desconhecidos)}. "
                        f"Os campos validos sao: {validos}")


def _ler_recurso(tabela: dict, indice: int) -> Recurso:
    onde = _onde("recurso", indice, tabela)
    _conferir_campos(tabela, onde, {"nome", "capacidade", "custo_reposicao"}, set())
    return Recurso(
        nome=_nome(tabela["nome"], onde, "nome"),
        capacidade=_inteiro(tabela["capacidade"], onde, "capacidade", 1),
        custo_reposicao=_inteiro(tabela["custo_reposicao"], onde, "custo_reposicao", 0),
    )


def _ler_preparo(tabela: dict, indice: int) -> Preparo:
    onde = _onde("preparo", indice, tabela)
    _conferir_campos(tabela, onde, {"nome", "estado", "custo"},
                     {"consome", "desfeito_ao_sair", "exigido_antes_de"})

    consome = tabela.get("consome")
    if consome is not None:
        consome = _nome(consome, onde, "consome")

    desfeito = tabela.get("desfeito_ao_sair", True)
    if not isinstance(desfeito, bool):
        raise ErroRegra(f"{onde}: o campo 'desfeito_ao_sair' deve ser true ou false. "
                        f"Recebido: {desfeito!r}")

    exigido = tabela.get("exigido_antes_de", [])
    if not isinstance(exigido, list):
        raise ErroRegra(f"{onde}: o campo 'exigido_antes_de' deve ser uma lista, "
                        f"como [\"pressao\", \"glicemia\"]. Recebido: {exigido!r}")
    for procedimento in exigido:
        if procedimento not in PROCEDIMENTOS:
            raise ErroRegra(f"{onde}: o procedimento {procedimento!r} nao existe. "
                            f"Os validos sao: {', '.join(PROCEDIMENTOS)}")
    if len(set(exigido)) != len(exigido):
        raise ErroRegra(f"{onde}: 'exigido_antes_de' tem procedimento repetido")

    return Preparo(
        nome=_nome(tabela["nome"], onde, "nome"),
        estado=_nome(tabela["estado"], onde, "estado"),
        custo=_inteiro(tabela["custo"], onde, "custo", 0),
        consome=consome,
        desfeito_ao_sair=desfeito,
        exigido_antes_de=tuple(exigido),
    )


def _lista_de_tabelas(dados: dict, chave: str) -> list[dict]:
    valor = dados.get(chave, [])
    if not isinstance(valor, list) or not all(isinstance(t, dict) for t in valor):
        raise ErroRegra(f"'{chave}' deve ser escrito como [[{chave}]], "
                        f"um bloco para cada {chave}")
    return valor


def ler_regras(dados: dict) -> Regras:
    """Converte o conteudo ja lido do TOML em `Regras`."""
    modelos = {"recurso", "preparo"}
    desconhecidos = sorted(dados.keys() - modelos)
    if desconhecidos:
        raise ErroRegra(f"modelo(s) desconhecido(s): {', '.join(desconhecidos)}. "
                        f"Os modelos disponiveis sao: {', '.join(sorted(modelos))}")
    return Regras(
        recursos=tuple(_ler_recurso(t, i)
                       for i, t in enumerate(_lista_de_tabelas(dados, "recurso"))),
        preparos=tuple(_ler_preparo(t, i)
                       for i, t in enumerate(_lista_de_tabelas(dados, "preparo"))),
    )


def carregar_regras(caminho: str) -> Regras:
    """Le um arquivo TOML de regras."""
    with open(caminho, "rb") as arquivo:
        try:
            dados = tomllib.load(arquivo)
        except tomllib.TOMLDecodeError as erro:
            raise ErroRegra(f"o arquivo {caminho} nao e um TOML valido: {erro}") from None
    return ler_regras(dados)
