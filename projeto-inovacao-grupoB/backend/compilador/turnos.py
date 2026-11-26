"""Alocação de pacientes e planejamento separado das duas saídas da UBS."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from .problema import marcas_dos_dados
from .regras import ErroRegra, Regras

ROTULOS = {"manha": "Manhã", "tarde": "Tarde"}


@dataclass(frozen=True)
class Turno:
    id: str
    inicio: str
    duracao: int
    max_pacientes: int | None


def configurar_turnos(args) -> tuple[Turno, ...]:
    valores = [getattr(args, nome, None) for nome in ROTULOS]
    maximos = [getattr(args, f"max_pacientes_{nome}", None) for nome in ROTULOS]
    if not any(valores) and all(m is None for m in maximos):
        return ()
    if not all(valores):
        raise ErroRegra("informe início e duração dos dois turnos (--manha e --tarde)")
    if args.orcamento is not None:
        raise ErroRegra("informe a duração em --manha e --tarde quando planejar o dia")

    turnos = []
    fim_anterior = 0
    for nome, (inicio, duracao), maximo in zip(ROTULOS, valores, maximos):
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", inicio, flags=re.ASCII):
            raise ErroRegra(f"{ROTULOS[nome]}: use um horário no formato HH:MM")
        try:
            minutos = int(duracao)
        except (ValueError, TypeError):
            raise ErroRegra(f"{ROTULOS[nome]}: a duração deve ser inteira") from None
        horas, minuto = map(int, inicio.split(":"))
        comeco = horas * 60 + minuto
        fim = comeco + minutos
        if minutos <= 0 or comeco < fim_anterior or fim > 24 * 60:
            raise ErroRegra("os turnos devem ter duração positiva, estar na ordem "
                            "manhã/tarde e não se sobrepor ou ultrapassar o dia")
        if (nome == "manha" and fim > 12 * 60) or (nome == "tarde" and comeco < 12 * 60):
            raise ErroRegra("a manhã deve terminar até 12:00 e a tarde deve começar a partir de 12:00")
        maximo = args.max_pacientes if maximo is None else maximo
        if maximo is not None and maximo < 1:
            raise ErroRegra(f"{ROTULOS[nome]}: o máximo de pacientes deve ser positivo")
        turnos.append(Turno(nome, inicio, minutos, maximo))
        fim_anterior = fim
    return tuple(turnos)


def alocar(dados: dict, regras: Regras, turnos: tuple[Turno, ...], *, sem_selecao: bool):
    from acsplan.dados import modelos
    from acsplan.selecao.politica import ATRASO_INADIAVEL_DIAS, MINUTOS_ESTIMADOS_POR_PACIENTE

    pacientes = dados["pacientes"]
    colunas = dados.get("_colunas_pacientes", set().union(*(p.keys() for p in pacientes)))
    ausentes = [p for p in regras.periodos if p.campo_paciente not in colunas]
    if ausentes:
        raise ErroRegra([f'período "{p.nome}": falta a coluna "{p.campo_paciente}" nos dados'
                         for p in ausentes])
    intervalo = dados.get("_meta", {}).get("intervalo_maximo_padrao_dias",
                                          modelos.INTERVALO_MAXIMO_PADRAO_DIAS)
    inadiaveis = {p["id"] for p in pacientes
                  if modelos.atraso_em_dias(p, intervalo) >= ATRASO_INADIAVEL_DIAS}
    grupos = {t.id: [] for t in turnos}
    limites = {}
    for t in turnos:
        estimado = max(1, t.duracao // MINUTOS_ESTIMADOS_POR_PACIENTE)
        limites[t.id] = min(estimado, t.max_pacientes or estimado)

    ordenados = sorted(pacientes, key=lambda p: (p["id"] not in inadiaveis,
                       -modelos.escore_urgencia(p, intervalo), p["id"]))
    elegiveis = {}
    for p in ordenados:
        aplicaveis = [r for r in regras.periodos if p.get(r.campo_paciente)]
        permitidos = set(grupos).intersection(*(r.turnos for r in aplicaveis))
        if not permitidos:
            nomes = ", ".join(r.nome for r in aplicaveis)
            raise ErroRegra(f'paciente "{p["id"]}": regras de período incompatíveis ({nomes})')
        elegiveis[p["id"]] = permitidos

    # Reserve espaço aos pacientes com um único período possível.
    pendentes = {}
    for p in sorted(ordenados, key=lambda p: (p["id"] not in inadiaveis,
                                               len(elegiveis[p["id"]]))):
        pid = p["id"]
        vagas = [t for t in turnos if t.id in elegiveis[pid]
                 and (sem_selecao or pid in inadiaveis or len(grupos[t.id]) < limites[t.id])]
        if vagas:
            escolhido = min(vagas, key=lambda t: len(grupos[t.id]) / limites[t.id])
            grupos[escolhido.id].append(p)
        else:
            periodos = " ou ".join(ROTULOS[t.id].lower() for t in turnos if t.id in elegiveis[pid])
            pendentes[pid] = f"sem vaga na estimativa de {periodos}"

    ordem = {p["id"]: i for i, p in enumerate(ordenados)}
    for grupo in grupos.values():
        grupo.sort(key=lambda p: ordem[p["id"]])
    return grupos, inadiaveis, pendentes


def planejar_dia(args, dados: dict, regras: Regras, turnos: tuple[Turno, ...],
                 planejar_turno, informar) -> dict:
    marcas_dos_dados(dados, regras)
    grupos, inadiaveis, pendentes = alocar(dados, regras, turnos, sem_selecao=args.sem_selecao)
    resultados = []
    colunas = dados.get("_colunas_pacientes", set().union(*(p.keys() for p in dados["pacientes"])))
    for turno in turnos:
        rotulo = ROTULOS[turno.id]
        informar(f"\n[{rotulo}] Início {turno.inicio} · {turno.duracao} min")
        candidatos = grupos[turno.id]
        opcoes = argparse.Namespace(**vars(args))
        opcoes.orcamento = turno.duracao
        opcoes.sem_selecao = True
        if opcoes.salvar_pddl:
            opcoes.salvar_pddl = Path(opcoes.salvar_pddl) / turno.id

        while True:
            resultado = planejar_turno(opcoes, {**dados, "pacientes": candidatos,
                                               "_colunas_pacientes": colunas})
            if resultado["codigo"] != 0 or resultado["custo_total"] <= turno.duracao:
                break
            removivel = next((p for p in reversed(candidatos)
                              if p["id"] not in inadiaveis), None)
            if args.sem_selecao or removivel is None:
                mensagem = (f'O roteiro encontrado tem {resultado["custo_total"]} min '
                            f'e ultrapassa os {turno.duracao} min de {rotulo.lower()}.')
                resultado = {"codigo": 1, "falha": {"tipo": "orcamento",
                             "mensagens": [mensagem]}}
                break
            candidatos.remove(removivel)
            motivo = f"o roteiro ultrapassava a duração do turno da {rotulo.lower()}"
            pendentes[removivel["id"]] = motivo
            informar(f'    {removivel["id"]} ficou sem alocação: {motivo}.')
        if resultado["codigo"] != 0:
            for p in candidatos:
                pendentes[p["id"]] = f"sem roteiro para o turno da {rotulo.lower()}"
        resultados.append({**resultado, "turno": turno.id, "rotulo": rotulo,
                           "inicio": turno.inicio, "duracao_turno": turno.duracao})

    nao_alocados = [{"id": p["id"], "nome": p.get("nome") or p["id"],
                     "motivo": pendentes[p["id"]], "inadiavel": p["id"] in inadiaveis}
                    for p in dados["pacientes"] if p["id"] in pendentes]
    textos = []
    for r in resultados:
        cabecalho = f'{r["rotulo"].upper()} · {r["inicio"]} · {r["duracao_turno"]} min'
        corpo = r["texto"] if r["codigo"] == 0 else "\n".join(r["falha"]["mensagens"])
        textos.append(f"{cabecalho}\n{corpo}")
    if nao_alocados:
        textos.append("SEM ALOCAÇÃO NO DIA\n" + "\n".join(
            f'- {p["nome"]}{" (inadiável)" if p["inadiavel"] else ""}: {p["motivo"]}'
            for p in nao_alocados))
    return {"codigo": int(any(r["codigo"] for r in resultados)), "turnos": resultados,
            "nao_alocados": nao_alocados, "texto": "\n\n".join(textos)}
