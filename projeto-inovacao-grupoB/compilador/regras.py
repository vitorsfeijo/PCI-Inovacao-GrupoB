"""
Leitura e validacao do arquivo de regras (TOML).

Modelos suportados:

    A. [[recurso]]  estoque finito, reposto so na UBS
    B. [[preparo]]  algo que o ACS faz antes de atender, podendo consumir
                    um recurso e sendo desfeito ao sair da casa
    C. pre-requisito, escrito como o campo `exigido_antes_de` do preparo

Validacao em tres niveis:

    1. cada campo isolado (formato, tipo, faixa): funcoes `validar_*`, que
       devolvem a mensagem de erro ou None. O assistente interativo usa as
       mesmas funcoes, campo a campo.
    2. regras entre si (nomes repetidos, recurso inexistente): `ler_regras`.
    3. regras contra o dominio (nome ja usado no PDDL): no compilador, que e
       quem conhece o dominio.

Os erros sao acumulados e devolvidos todos juntos, para que quem escreveu a
regra corrija tudo de uma vez. As mensagens sao para quem nao programa:
dizem o que esta errado e qual e o valor aceito.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from typing import Any

# Nome usado na regra -> acao do dominio legal.
PROCEDIMENTOS = {
    "pressao": "aferir-pressao-arterial",
    "glicemia": "medir-glicemia-capilar",
    "temperatura": "aferir-temperatura-axilar",
    "medicacao": "orientar-administracao-medicacao",
    "antropometria": "verificacao-antropometrica",
    "vacinal": "verificar-caderneta-vacinal",
}

# Campos de cada modelo: nome -> obrigatorio?
CAMPOS = {
    "recurso": {"nome": True, "capacidade": True, "custo_reposicao": True},
    "preparo": {"nome": True, "estado": True, "custo": True, "consome": False,
                "desfeito_ao_sair": False, "exigido_antes_de": False},
}

# Nomes PDDL: minusculas, digitos e hifen, comecando por letra.
_NOME_VALIDO = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class ErroRegra(ValueError):
    """Uma ou mais regras mal escritas. As mensagens sao para quem escreveu."""

    def __init__(self, problemas: str | list[str]) -> None:
        self.problemas = [problemas] if isinstance(problemas, str) else list(problemas)
        super().__init__("\n".join(self.problemas))


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


# ============================================================================
#  1. VALIDADORES DE CAMPO (devolvem a mensagem de erro, ou None)
# ============================================================================

def validar_nome(valor: Any) -> str | None:
    if not isinstance(valor, str):
        return f"deve ser um texto entre aspas, como \"maos-higienizadas\". Recebido: {valor!r}"
    if not _NOME_VALIDO.match(valor):
        dica = ""
        sugestao = sugerir_nome(valor)
        if sugestao and sugestao != valor:
            dica = f" Sugestão: \"{sugestao}\"."
        return (f"\"{valor}\" não serve como nome. Use só letras minúsculas sem "
                f"acento e números, com hífen entre as palavras, começando por "
                f"letra (ex.: \"maos-higienizadas\").{dica}")
    return None


def validar_inteiro(valor: Any, minimo: int) -> str | None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        return f"deve ser um número inteiro, sem aspas. Recebido: {valor!r}"
    if valor < minimo:
        return f"deve ser maior ou igual a {minimo}. Recebido: {valor}"
    return None


def validar_booleano(valor: Any) -> str | None:
    if not isinstance(valor, bool):
        return f"deve ser true ou false, sem aspas. Recebido: {valor!r}"
    return None


def validar_procedimentos(valor: Any) -> str | None:
    if not isinstance(valor, list):
        return (f"deve ser uma lista entre colchetes, como [\"pressao\", \"glicemia\"]. "
                f"Recebido: {valor!r}")
    invalidos = [p for p in valor if p not in PROCEDIMENTOS]
    if invalidos:
        nomes = ", ".join(repr(p) for p in invalidos)
        return (f"procedimento(s) inexistente(s): {nomes}. "
                f"Os aceitos são: {', '.join(PROCEDIMENTOS)}")
    repetidos = sorted({p for p in valor if valor.count(p) > 1})
    if repetidos:
        return f"procedimento(s) repetido(s): {', '.join(repetidos)}"
    return None


def sugerir_nome(texto: str) -> str:
    """'Álcool Gel' -> 'alcool-gel'. Usado nas dicas e no assistente."""
    import unicodedata
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    partes = re.findall(r"[a-z0-9]+", sem_acento.lower())
    nome = "-".join(partes)
    return nome if _NOME_VALIDO.match(nome) else ""


# Validador de cada campo. Os inteiros levam o minimo aceito.
VALIDADORES = {
    "nome": validar_nome,
    "estado": validar_nome,
    "consome": validar_nome,
    "capacidade": lambda v: validar_inteiro(v, 1),
    "custo_reposicao": lambda v: validar_inteiro(v, 0),
    "custo": lambda v: validar_inteiro(v, 0),
    "desfeito_ao_sair": validar_booleano,
    "exigido_antes_de": validar_procedimentos,
}


# ============================================================================
#  2. LEITURA DAS REGRAS
# ============================================================================

def _rotulo(modelo: str, indice: int, tabela: dict) -> str:
    nome = tabela.get("nome")
    if isinstance(nome, str) and nome:
        return f"{modelo} \"{nome}\""
    return f"{modelo} nº {indice + 1}"


def _ler_tabela(modelo: str, indice: int, tabela: dict, erros: list[str]) -> dict | None:
    """Confere os campos de um bloco e devolve os valores validos (ou None)."""
    rotulo = _rotulo(modelo, indice, tabela)
    campos = CAMPOS[modelo]
    antes = len(erros)

    for campo, obrigatorio in campos.items():
        if obrigatorio and campo not in tabela:
            erros.append(f"{rotulo}: falta o campo '{campo}'")
    for campo in tabela:
        if campo not in campos:
            erros.append(f"{rotulo}: o campo '{campo}' não existe neste modelo. "
                         f"Os campos de {modelo} são: {', '.join(campos)}")
        else:
            problema = VALIDADORES[campo](tabela[campo])
            if problema:
                erros.append(f"{rotulo}, campo '{campo}': {problema}")
    return None if len(erros) > antes else tabela


def _blocos(dados: dict, modelo: str, erros: list[str]) -> list[dict]:
    valor = dados.get(modelo, [])
    if not isinstance(valor, list) or not all(isinstance(t, dict) for t in valor):
        erros.append(f"cada {modelo} deve começar com uma linha [[{modelo}]] "
                     f"(colchetes duplos), um bloco para cada {modelo}")
        return []
    return valor


def _conferir_entre_si(recursos: list[Recurso], preparos: list[Preparo],
                       recursos_declarados: list[str], erros: list[str]) -> None:
    vistos: dict[str, str] = {}

    def reservar(nome: str, dono: str) -> None:
        if nome in vistos:
            erros.append(f"{dono}: o nome \"{nome}\" já é usado por {vistos[nome]}")
        else:
            vistos[nome] = dono

    for r in recursos:
        reservar(r.nome, f"recurso \"{r.nome}\"")
    for p in preparos:
        reservar(p.nome, f"preparo \"{p.nome}\"")
        reservar(p.estado, f"o estado do preparo \"{p.nome}\"")

    # recursos com erro tambem contam como declarados: o problema deles ja foi
    # relatado, e acusar "recurso inexistente" aqui seria enganoso
    for p in preparos:
        if p.consome is not None and p.consome not in recursos_declarados:
            declarados = ", ".join(recursos_declarados) or "nenhum"
            erros.append(f"preparo \"{p.nome}\": consome \"{p.consome}\", mas não há "
                         f"recurso com esse nome. Recursos declarados: {declarados}")


def ler_regras(dados: dict) -> Regras:
    """Converte o conteudo ja lido do TOML em `Regras`, ou levanta ErroRegra."""
    erros: list[str] = []
    for chave in dados:
        if chave not in CAMPOS:
            erros.append(f"o modelo '{chave}' não existe. Os modelos disponíveis "
                         f"são: {', '.join(CAMPOS)}")

    recursos: list[Recurso] = []
    blocos_recurso = _blocos(dados, "recurso", erros)
    recursos_declarados = [t["nome"] for t in blocos_recurso
                           if isinstance(t.get("nome"), str)]
    for i, tabela in enumerate(blocos_recurso):
        if (t := _ler_tabela("recurso", i, tabela, erros)) is not None:
            recursos.append(Recurso(t["nome"], t["capacidade"], t["custo_reposicao"]))

    preparos: list[Preparo] = []
    for i, tabela in enumerate(_blocos(dados, "preparo", erros)):
        if (t := _ler_tabela("preparo", i, tabela, erros)) is not None:
            preparos.append(Preparo(
                nome=t["nome"], estado=t["estado"], custo=t["custo"],
                consome=t.get("consome"),
                desfeito_ao_sair=t.get("desfeito_ao_sair", True),
                exigido_antes_de=tuple(t.get("exigido_antes_de", []))))

    _conferir_entre_si(recursos, preparos, recursos_declarados, erros)
    if erros:
        raise ErroRegra(erros)
    return Regras(tuple(recursos), tuple(preparos))


def _traduzir_erro_toml(erro: tomllib.TOMLDecodeError) -> str:
    linha = getattr(erro, "lineno", None)
    coluna = getattr(erro, "colno", None)
    if linha is None:
        casamento = re.search(r"line (\d+), column (\d+)", str(erro))
        if casamento:
            linha, coluna = int(casamento.group(1)), int(casamento.group(2))
    onde = f" na linha {linha}, coluna {coluna}" if linha else ""
    detalhe = getattr(erro, "msg", None) or re.sub(r"\s*\(at .*\)$", "", str(erro))
    return (f"o arquivo não segue o formato TOML{onde}. Confira aspas, colchetes "
            f"e o sinal de igual nessa linha. (Detalhe técnico: {detalhe})")


def carregar_regras(caminho: str) -> Regras:
    """Le um arquivo TOML de regras."""
    try:
        with open(caminho, "rb") as arquivo:
            dados = tomllib.load(arquivo)
    except FileNotFoundError:
        raise ErroRegra(f"o arquivo {caminho} não foi encontrado") from None
    except tomllib.TOMLDecodeError as erro:
        raise ErroRegra(_traduzir_erro_toml(erro)) from None
    return ler_regras(dados)


# ============================================================================
#  3. AVISOS (nao impedem a compilacao)
# ============================================================================

def avisos(regras: Regras) -> list[str]:
    """Regras validas, mas que provavelmente nao fazem o que se espera."""
    resultado: list[str] = []
    if not regras.recursos and not regras.preparos:
        resultado.append("o arquivo não tem nenhuma regra; o domínio sai igual ao de entrada")

    consumidos = {p.consome for p in regras.preparos}
    for r in regras.recursos:
        if r.nome not in consumidos:
            resultado.append(f"recurso \"{r.nome}\": nenhum preparo o consome, então "
                             f"ele não muda nenhum plano")
    for p in regras.preparos:
        if not p.exigido_antes_de:
            resultado.append(f"preparo \"{p.nome}\": não é exigido antes de nenhum "
                             f"procedimento, então o planejador nunca vai fazê-lo "
                             f"(preencha 'exigido_antes_de')")
        if not p.desfeito_ao_sair and p.exigido_antes_de:
            resultado.append(f"preparo \"{p.nome}\": como não é desfeito ao sair, "
                             f"basta fazê-lo uma vez no turno inteiro. Confira se é "
                             f"essa a intenção")
    return resultado
