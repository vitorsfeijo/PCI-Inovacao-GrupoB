"""
Roteiro do turno para o ACS, incluindo as acoes criadas pelas regras.

Adaptado de `saida/roteiro.py` do Ciclo 2 (que nao foi copiado para
acsplan/). La, o texto de cada acao esta fixo no codigo, entao uma acao
criada por uma regra nova nao apareceria no roteiro. Aqui o texto vem da
propria regra (campo `texto`), e o restante segue os mesmos principios:

- Uma parada por bloco, numerada, sem identificadores internos.
- So o que muda a conduta. Acoes internas do modelo (inicio de visita,
  conferencias dispensadas, retorno a rota) nao aparecem.
- Reposicoes aparecem agrupadas na linha do desvio ate a unidade.
- Tarefas sempre na mesma ordem de trabalho, nao na ordem interna do plano.
- Tempos acumulados em minutos, para o ACS se situar no turno.

Os minutos vem do custo de cada acao instanciada na tarefa de planejamento,
entao o total do roteiro bate com o custo do plano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .dominio import versoes_de_procedimentos
from .regras import Regras

# Acoes do dominio legal que viram tarefa, e a ordem de trabalho de cada uma.
TAREFAS_BASE = {
    "acionar-supervisao": ("Acionar o enfermeiro da equipe (acompanhamento obrigatório)", 0),
    "aferir-pressao-arterial": ("Aferir pressão arterial", 40),
    "medir-glicemia-capilar": ("Medir glicemia capilar", 41),
    "aferir-temperatura-axilar": ("Aferir temperatura axilar", 42),
    "verificacao-antropometrica": ("Verificação antropométrica (peso e altura)", 43),
    "orientar-administracao-medicacao": ("Orientar a administração da medicação", 44),
    "verificar-caderneta-vacinal": ("Conferir a caderneta de vacinação", 45),
    "registrar-encaminhamento": ("Encaminhar o paciente à unidade de referência", 50),
    "registrar-visita": ("Registrar a visita no sistema", 51),
}

# Ordem das tarefas criadas por regras, entre a supervisao e os procedimentos.
ORDEM_PREPARO_DE_EXIGENCIA = 10    # ex.: colocar a mascara
ORDEM_CONFERENCIA = 20             # ex.: conferir a protecao antes de entrar
ORDEM_PREPARO = 30                 # ex.: higienizar as maos

OCULTAS_BASE = {"mover", "iniciar-visita", "iniciar-visita-urgente",
                "iniciar-visita-adiavel", "retornar-a-rota"}

REPOSICOES_BASE = {"reabastecer-fitas": "fitas de glicemia"}

DESVIO = "desviar-para-ubs"

_ARGS = re.compile(r"^([a-z0-9-]+)\((.*)\)$")


def legivel(nome: str) -> str:
    """'higienizar-maos' -> 'Higienizar maos' (quando a regra nao tem texto)."""
    texto = nome.replace("-", " ")
    return texto[:1].upper() + texto[1:]


@dataclass
class Legenda:
    """Como cada acao do plano aparece no roteiro."""
    tarefas: dict[str, tuple[str, int]] = field(default_factory=dict)
    reposicoes: dict[str, str] = field(default_factory=dict)
    ocultas: set[str] = field(default_factory=set)
    # acoes sem paciente que pertencem a proxima visita (preparacao para ela)
    preparacao: set[str] = field(default_factory=set)


def legenda_para(regras: Regras) -> Legenda:
    legenda = Legenda(tarefas=dict(TAREFAS_BASE), reposicoes=dict(REPOSICOES_BASE),
                      ocultas=set(OCULTAS_BASE))
    for r in regras.recursos:
        legenda.reposicoes[r.acao_reposicao] = r.texto or r.nome.replace("-", " ")

    exigidos = {e.preparo for e in regras.exigencias}
    for p in regras.preparos:
        ordem = ORDEM_PREPARO_DE_EXIGENCIA if p.nome in exigidos else ORDEM_PREPARO
        legenda.tarefas[p.nome] = (p.texto or legivel(p.nome), ordem)
    for e in regras.exigencias:
        if not e.no_inicio_da_visita:
            continue
        texto = e.texto or f"Conferir {e.nome.replace('-', ' ')} antes de entrar"
        legenda.tarefas[e.acao_exigida] = (texto, ORDEM_CONFERENCIA)
        legenda.ocultas.add(e.acao_dispensada)
    # versoes de um procedimento (exigencias com antes_de) aparecem como ele
    for versao, base in versoes_de_procedimentos(regras).items():
        legenda.tarefas[versao] = legenda.tarefas[base]

    legenda.preparacao = ({"acionar-supervisao", DESVIO} | set(legenda.reposicoes)
                          | {p.nome for p in regras.preparos})
    return legenda


def _partes(acao: str) -> tuple[str, list[str]]:
    m = _ARGS.match(acao.strip())
    if not m:
        return acao.strip(), []
    return m.group(1), [a.strip() for a in m.group(2).split(",") if a.strip()]


def montar(plano: list[str], dados: dict, custos: dict[str, int],
           legenda: Legenda) -> list[dict]:
    """
    Agrupa o plano em paradas. `custos` leva cada passo do plano (como o
    planejador o escreve) ao seu custo em minutos.

    Regra de atribuicao, a mesma do Ciclo 2: toda acao que menciona um
    paciente pertence a ele; as acoes de preparacao sem paciente (acionar
    supervisao, preparos, desvios, reposicoes) pertencem ao paciente da
    proxima acao que mencione um, porque preparam o atendimento seguinte.
    """
    por_id = {p["id"]: p for p in dados["pacientes"]}

    eventos: list[dict] = []
    minutos = 0
    for passo in plano:
        nome, args = _partes(passo)
        minutos += custos.get(passo, 0)
        dono = next((a for a in args if a in por_id), None)
        eventos.append({"nome": nome, "minutos": minutos, "dono": dono})

    seguinte: str | None = None
    for evento in reversed(eventos):
        if evento["dono"] is not None:
            seguinte = evento["dono"]
        elif evento["nome"] in legenda.preparacao:
            evento["dono"] = seguinte

    paradas: list[dict] = []
    indice: dict[str, dict] = {}
    for evento in eventos:
        if not evento["nome"].startswith("iniciar-visita"):
            continue
        dono = evento["dono"]
        if dono is None or dono in indice:
            continue
        parada = {"ordem": len(paradas) + 1, "paciente": por_id.get(dono),
                  "tarefas": [], "desvio_ubs": False, "repor": [],
                  "minutos_chegada": evento["minutos"]}
        paradas.append(parada)
        indice[dono] = parada

    for evento in eventos:
        parada = indice.get(evento["dono"] or "")
        nome = evento["nome"]
        if parada is None or nome in legenda.ocultas:
            continue
        if nome == DESVIO:
            parada["desvio_ubs"] = True
        elif nome in legenda.reposicoes:
            item = legenda.reposicoes[nome]
            if item not in parada["repor"]:
                parada["repor"].append(item)
        else:
            tarefa = legenda.tarefas.get(nome, (legivel(nome), 99))
            if tarefa not in parada["tarefas"]:
                parada["tarefas"].append(tarefa)

    for parada in paradas:
        parada["tarefas"] = [texto for texto, _ in
                             sorted(parada["tarefas"], key=lambda t: t[1])]
    return paradas


def imprimir(paradas: list[dict], dados: dict, *, custo_total: int,
             orcamento: int | None = None, largura: int = 66) -> str:
    """Roteiro pronto para imprimir ou enviar ao ACS."""
    linhas: list[str] = []
    add = linhas.append
    ubs = dados["ubs"].get("nome", "Unidade Básica de Saúde")

    add("=" * largura)
    add("  ROTEIRO DO TURNO")
    add(f"  Saída e retorno: {ubs}")
    add(f"  {len(paradas)} visitas  |  duração estimada: {custo_total} min")
    if orcamento is not None and custo_total > orcamento:
        add(f"  ATENÇÃO: excede em {custo_total - orcamento} min o orçamento de "
            f"{orcamento} min")
    add("=" * largura)

    for parada in paradas:
        paciente = parada["paciente"] or {}
        nome = paciente.get("nome", paciente.get("id", "?"))
        grupo = (paciente.get("grupo") or "").replace("_", " ")
        add("")
        add(f"  {parada['ordem']}. {nome}" + (f"  ({grupo})" if grupo else ""))
        add(f"     início aprox.: {parada['minutos_chegada']} min de turno")
        if parada["desvio_ubs"]:
            itens = ", ".join(parada["repor"] or ["material"])
            add(f"     >> PASSAR NA UNIDADE ANTES desta visita: repor {itens}")
        for tarefa in parada["tarefas"] or ["Visita de acompanhamento, sem procedimento previsto"]:
            add(f"     [ ] {tarefa}")

    add("")
    add("-" * largura)
    add("  Marque cada item ao concluir. Se não for possível realizar algum")
    add("  procedimento, registre a ocorrência e comunique a equipe antes de")
    add("  seguir para a próxima visita.")
    add("-" * largura)
    return "\n".join(linhas)
