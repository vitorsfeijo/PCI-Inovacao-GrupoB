"""
Leitura e validacao do arquivo de regras (TOML).

Modelos suportados:

    A. [[recurso]]    estoque finito, reposto so na UBS
    B. [[preparo]]    algo que o ACS faz antes de atender, podendo consumir
                      um recurso e sendo desfeito ao sair da casa
    C. pre-requisito, escrito como o campo `exigido_antes_de` do preparo
    D. [[consumo]]    um procedimento gasta uma unidade de um recurso
    E. [[exigencia]]  pacientes com uma marca so podem ter a visita iniciada
                      com um preparo valendo

Validacao em tres niveis:

    1. cada campo isolado (formato, tipo, faixa): funcoes `validar_*`, que
       devolvem a mensagem de erro ou None. O assistente interativo usa as
       mesmas funcoes, campo a campo.
    2. regras entre si (nomes repetidos, referencia inexistente): `ler_regras`.
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

# Como cada procedimento aparece para quem escreve a regra.
DESCRICAO_PROCEDIMENTOS = {
    "pressao": "aferir pressão arterial",
    "glicemia": "medir glicemia capilar",
    "temperatura": "aferir temperatura axilar",
    "medicacao": "orientar a administração de medicação",
    "antropometria": "verificação antropométrica (peso e altura)",
    "vacinal": "verificar a caderneta de vacinação",
}

# Explicacao curta de cada campo: usada nas perguntas do assistente e nos
# comentarios do TOML que ele grava.
DESCRICAO_CAMPOS = {
    ("recurso", "nome"): "nome do estoque",
    ("recurso", "capacidade"): "unidades por carga",
    ("recurso", "custo_reposicao"): "minutos para repor na UBS",
    ("recurso", "acao_reposicao"): "nome da ação de reposição",
    ("recurso", "texto"): "como aparece no roteiro do ACS",
    ("preparo", "texto"): "como aparece no roteiro do ACS",
    ("exigencia", "texto"): "como aparece no roteiro do ACS",
    ("preparo", "nome"): "o que o ACS faz",
    ("preparo", "estado"): "o que passa a valer depois",
    ("preparo", "custo"): "minutos",
    ("preparo", "consome"): "recurso gasto a cada vez",
    ("preparo", "desfeito_ao_sair"): "sair da casa desfaz o estado?",
    ("preparo", "exigido_antes_de"): "procedimentos que dependem do preparo",
    ("consumo", "procedimento"): "procedimento que gasta o recurso",
    ("consumo", "recurso"): "recurso gasto, uma unidade por vez",
    ("exigencia", "nome"): "nome da conferência feita na porta",
    ("exigencia", "marca"): "marca do paciente (coluna da planilha)",
    ("exigencia", "preparo"): "preparo exigido para iniciar a visita",
    ("exigencia", "custo"): "minutos da conferência",
}

# Campos de cada modelo, na ordem em que aparecem: nome -> obrigatorio?
CAMPOS = {
    "recurso": {"nome": True, "capacidade": True, "custo_reposicao": True,
                "acao_reposicao": False, "texto": False},
    "preparo": {"nome": True, "estado": True, "custo": True, "consome": False,
                "desfeito_ao_sair": False, "exigido_antes_de": False, "texto": False},
    "consumo": {"procedimento": True, "recurso": True},
    "exigencia": {"nome": True, "marca": True, "preparo": True, "custo": False,
                  "texto": False},
}

# Tamanho maximo do texto mostrado no roteiro.
TEXTO_MAXIMO = 80

# Custo padrao da conferencia de uma exigencia, em minutos.
CUSTO_CONFERENCIA_PADRAO = 1

# Nomes PDDL: minusculas, digitos e hifen, comecando por letra.
_NOME_VALIDO = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class ErroRegra(ValueError):
    """Uma ou mais regras mal escritas. As mensagens sao para quem escreveu."""

    def __init__(self, problemas: str | list[str]) -> None:
        self.problemas = [problemas] if isinstance(problemas, str) else list(problemas)
        super().__init__("\n".join(self.problemas))


# ============================================================================
#  MODELOS
#  `nomes_gerados` lista os nomes que cada regra cria no dominio. A validacao,
#  o compilador e o assistente usam essa lista para recusar nomes repetidos.
# ============================================================================

@dataclass(frozen=True)
class Recurso:
    nome: str
    capacidade: int
    custo_reposicao: int
    nome_reposicao: str | None = None      # campo `acao_reposicao` no TOML
    texto: str | None = None               # o que repor, no roteiro do ACS

    @property
    def predicado(self) -> str:
        return self.nome

    @property
    def predicado_maximo(self) -> str:
        return f"nivel-maximo-{self.nome}"

    @property
    def acao_reposicao(self) -> str:
        return self.nome_reposicao or f"repor-{self.nome}"

    @property
    def nomes_gerados(self) -> list[str]:
        return [self.predicado, self.predicado_maximo, self.acao_reposicao]


@dataclass(frozen=True)
class Preparo:
    nome: str
    estado: str
    custo: int
    consome: str | None = None
    desfeito_ao_sair: bool = True
    exigido_antes_de: tuple[str, ...] = ()
    texto: str | None = None               # tarefa, no roteiro do ACS

    @property
    def nomes_gerados(self) -> list[str]:
        return [self.nome, self.estado]


@dataclass(frozen=True)
class Consumo:
    procedimento: str
    recurso: str


@dataclass(frozen=True)
class Exigencia:
    nome: str
    marca: str
    preparo: str
    custo: int = CUSTO_CONFERENCIA_PADRAO
    texto: str | None = None               # conferencia, no roteiro do ACS

    @property
    def predicado_conferencia(self) -> str:
        return f"{self.nome}-conferida"

    @property
    def acao_exigida(self) -> str:
        return f"conferir-{self.nome}-exigida"

    @property
    def acao_dispensada(self) -> str:
        return f"conferir-{self.nome}-dispensada"

    @property
    def campo_paciente(self) -> str:
        """Coluna da planilha de pacientes com a marca: hifens viram _."""
        return self.marca.replace("-", "_")

    @property
    def nomes_gerados(self) -> list[str]:
        return [self.marca, self.predicado_conferencia, self.acao_exigida,
                self.acao_dispensada]


@dataclass(frozen=True)
class Regras:
    recursos: tuple[Recurso, ...] = ()
    preparos: tuple[Preparo, ...] = ()
    consumos: tuple[Consumo, ...] = ()
    exigencias: tuple[Exigencia, ...] = ()

    @property
    def vazia(self) -> bool:
        return not (self.recursos or self.preparos or self.consumos or self.exigencias)


def nomes_gerados_por(modelo: str, campos: dict) -> list[str]:
    """Nomes que um bloco ainda em preenchimento vai gerar (assistente)."""
    if modelo == "recurso":
        return Recurso(campos["nome"], 1, 0, campos.get("acao_reposicao")).nomes_gerados
    if modelo == "exigencia":
        return Exigencia(campos["nome"], campos.get("marca", ""), "").nomes_gerados[1:]
    return [campos["nome"]]


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


def validar_texto(valor: Any) -> str | None:
    if not isinstance(valor, str) or not valor.strip():
        return f"deve ser um texto entre aspas, como \"Higienizar as mãos\". Recebido: {valor!r}"
    if len(valor) > TEXTO_MAXIMO:
        return f"deve ter no máximo {TEXTO_MAXIMO} caracteres (tem {len(valor)})"
    if "\n" in valor:
        return "deve caber em uma linha"
    return None


def validar_procedimento(valor: Any) -> str | None:
    if valor not in PROCEDIMENTOS:
        return (f"o procedimento {valor!r} não existe. "
                f"Os aceitos são: {', '.join(PROCEDIMENTOS)}")
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
    "acao_reposicao": validar_nome,
    "recurso": validar_nome,
    "marca": validar_nome,
    "preparo": validar_nome,
    "capacidade": lambda v: validar_inteiro(v, 1),
    "custo_reposicao": lambda v: validar_inteiro(v, 0),
    "custo": lambda v: validar_inteiro(v, 0),
    "desfeito_ao_sair": validar_booleano,
    "exigido_antes_de": validar_procedimentos,
    "procedimento": validar_procedimento,
    "texto": validar_texto,
}


# ============================================================================
#  2. LEITURA DAS REGRAS
# ============================================================================

def _rotulo(modelo: str, indice: int, tabela: dict) -> str:
    nome = tabela.get("nome")
    if isinstance(nome, str) and nome:
        return f"{modelo} \"{nome}\""
    if modelo == "consumo" and isinstance(tabela.get("procedimento"), str):
        return f"consumo de \"{tabela.get('recurso')}\" por \"{tabela['procedimento']}\""
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


def _declarados(blocos: list[dict]) -> list[str]:
    """Nomes declarados, mesmo em blocos com erro: o erro deles ja foi
    relatado, e acusar "inexistente" em quem os referencia seria enganoso."""
    return [t["nome"] for t in blocos if isinstance(t.get("nome"), str)]


def _conferir_entre_si(regras: Regras, recursos_declarados: list[str],
                       preparos_declarados: list[str], erros: list[str]) -> None:
    vistos: dict[str, tuple[object, str]] = {}   # nome -> (regra, "pelo ...")

    def reservar(regra: object, nomes: list[str], dono: str, por: str) -> None:
        for nome in nomes:
            if nome not in vistos:
                vistos[nome] = (regra, por)
                continue
            # um erro por regra basta: dois recursos "alcool" colidem tambem
            # em "repor-alcool" e "nivel-maximo-alcool", e repetir confunde
            if vistos[nome][0] is regra:
                erros.append(f"{dono}: usa o nome \"{nome}\" duas vezes")
            else:
                erros.append(f"{dono}: o nome \"{nome}\" já é usado {vistos[nome][1]}")
            return

    for r in regras.recursos:
        reservar(r, r.nomes_gerados, f"recurso \"{r.nome}\"", f"pelo recurso \"{r.nome}\"")
    for p in regras.preparos:
        reservar(p, p.nomes_gerados, f"preparo \"{p.nome}\"", f"pelo preparo \"{p.nome}\"")
    for e in regras.exigencias:
        reservar(e, e.nomes_gerados, f"exigência \"{e.nome}\"",
                 f"pela exigência \"{e.nome}\"")

    def recurso_existe(nome: str, dono: str, campo: str) -> None:
        if nome not in recursos_declarados:
            lista = ", ".join(recursos_declarados) or "nenhum"
            erros.append(f"{dono}: {campo} \"{nome}\", mas não há recurso com esse "
                         f"nome. Recursos declarados: {lista}")

    for p in regras.preparos:
        if p.consome is not None:
            recurso_existe(p.consome, f"preparo \"{p.nome}\"", "consome")

    pares: set[tuple[str, str]] = set()
    for c in regras.consumos:
        dono = f"consumo de \"{c.recurso}\" por \"{c.procedimento}\""
        recurso_existe(c.recurso, dono, "gasta")
        if (c.procedimento, c.recurso) in pares:
            erros.append(f"{dono}: aparece mais de uma vez")
        pares.add((c.procedimento, c.recurso))

    for e in regras.exigencias:
        if e.preparo not in preparos_declarados:
            lista = ", ".join(preparos_declarados) or "nenhum"
            erros.append(f"exigência \"{e.nome}\": exige o preparo \"{e.preparo}\", "
                         f"mas não há preparo com esse nome. Preparos declarados: {lista}")


def ler_regras(dados: dict) -> Regras:
    """Converte o conteudo ja lido do TOML em `Regras`, ou levanta ErroRegra."""
    erros: list[str] = []
    for chave in dados:
        if chave not in CAMPOS:
            erros.append(f"o modelo '{chave}' não existe. Os modelos disponíveis "
                         f"são: {', '.join(CAMPOS)}")

    blocos = {modelo: _blocos(dados, modelo, erros) for modelo in CAMPOS}
    validos = {modelo: [t for i, t in enumerate(lista)
                        if _ler_tabela(modelo, i, t, erros) is not None]
               for modelo, lista in blocos.items()}

    regras = Regras(
        recursos=tuple(Recurso(t["nome"], t["capacidade"], t["custo_reposicao"],
                               t.get("acao_reposicao"), t.get("texto"))
                       for t in validos["recurso"]),
        preparos=tuple(Preparo(t["nome"], t["estado"], t["custo"], t.get("consome"),
                               t.get("desfeito_ao_sair", True),
                               tuple(t.get("exigido_antes_de", [])), t.get("texto"))
                       for t in validos["preparo"]),
        consumos=tuple(Consumo(t["procedimento"], t["recurso"])
                       for t in validos["consumo"]),
        exigencias=tuple(Exigencia(t["nome"], t["marca"], t["preparo"],
                                   t.get("custo", CUSTO_CONFERENCIA_PADRAO),
                                   t.get("texto"))
                         for t in validos["exigencia"]),
    )
    _conferir_entre_si(regras, _declarados(blocos["recurso"]),
                       _declarados(blocos["preparo"]), erros)
    if erros:
        raise ErroRegra(erros)
    return regras


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


def regras_para_dados(regras: Regras) -> dict:
    """Caminho inverso de `ler_regras`: Regras -> dicionario do TOML."""
    dados: dict[str, list[dict]] = {m: [] for m in CAMPOS}
    for r in regras.recursos:
        campos = {"nome": r.nome, "capacidade": r.capacidade,
                  "custo_reposicao": r.custo_reposicao}
        if r.nome_reposicao:
            campos["acao_reposicao"] = r.nome_reposicao
        if r.texto:
            campos["texto"] = r.texto
        dados["recurso"].append(campos)
    for p in regras.preparos:
        campos = {"nome": p.nome, "estado": p.estado, "custo": p.custo}
        if p.consome:
            campos["consome"] = p.consome
        campos["desfeito_ao_sair"] = p.desfeito_ao_sair
        campos["exigido_antes_de"] = list(p.exigido_antes_de)
        if p.texto:
            campos["texto"] = p.texto
        dados["preparo"].append(campos)
    for c in regras.consumos:
        dados["consumo"].append({"procedimento": c.procedimento, "recurso": c.recurso})
    for e in regras.exigencias:
        campos = {"nome": e.nome, "marca": e.marca, "preparo": e.preparo,
                  "custo": e.custo}
        if e.texto:
            campos["texto"] = e.texto
        dados["exigencia"].append(campos)
    return {m: blocos for m, blocos in dados.items() if blocos}


# ============================================================================
#  3. AVISOS (nao impedem a compilacao)
# ============================================================================

def avisos(regras: Regras) -> list[str]:
    """Regras validas, mas que provavelmente nao fazem o que se espera."""
    resultado: list[str] = []
    if regras.vazia:
        resultado.append("o arquivo não tem nenhuma regra; o domínio sai igual ao de entrada")

    consumidos = ({p.consome for p in regras.preparos}
                  | {c.recurso for c in regras.consumos})
    for r in regras.recursos:
        if r.nome not in consumidos:
            resultado.append(f"recurso \"{r.nome}\": nenhum preparo ou procedimento o "
                             f"consome, então ele não muda nenhum plano")

    exigidos = {e.preparo for e in regras.exigencias}
    for p in regras.preparos:
        usado = bool(p.exigido_antes_de) or p.nome in exigidos
        if not usado:
            resultado.append(f"preparo \"{p.nome}\": não é exigido antes de nenhum "
                             f"procedimento nem por nenhuma exigência, então o "
                             f"planejador nunca vai fazê-lo")
        if not p.desfeito_ao_sair and usado:
            resultado.append(f"preparo \"{p.nome}\": como não é desfeito ao sair, "
                             f"basta fazê-lo uma vez no turno inteiro. Confira se é "
                             f"essa a intenção")
    return resultado


# ============================================================================
#  4. ESCRITA EM TOML (usada pelo assistente)
# ============================================================================

def _valor_toml(valor: Any) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, str):
        return '"' + valor.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(valor, (list, tuple)):
        return "[" + ", ".join(_valor_toml(v) for v in valor) + "]"
    raise TypeError(f"valor sem representacao TOML: {valor!r}")


def bloco_toml(modelo: str, campos: dict) -> str:
    """Um bloco [[modelo]] com um comentario explicando cada campo."""
    curtos = [f"{c} = {_valor_toml(v)}" for c, v in campos.items()]
    largura = max((len(t) for t in curtos if len(t) <= 40), default=0)
    linhas = [f"[[{modelo}]]"]
    for (campo, _), texto in zip(campos.items(), curtos):
        comentario = DESCRICAO_CAMPOS.get((modelo, campo), "")
        if not comentario:
            linhas.append(texto)
        elif len(texto) <= 40:
            linhas.append(f"{texto.ljust(largura)}  # {comentario}")
        else:                                   # linha longa: comentario acima
            linhas += [f"# {comentario}", texto]
    return "\n".join(linhas) + "\n"


def regras_para_toml(regras: Regras) -> str:
    return "\n".join(bloco_toml(modelo, campos)
                     for modelo, blocos in regras_para_dados(regras).items()
                     for campos in blocos)
