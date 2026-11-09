"""
Conferencia do teste com usuario (etapa 8.5).

    python3 acs.py conferir-teste SESSAO.toml --tarefa t1 [--registro SESSAO.jsonl]

Compara as regras escritas pela pessoa com o gabarito da tarefa
(exemplos/avaliacao/teste-usuario/gabarito-tN.toml), IGNORANDO os nomes e
os textos escolhidos: so importa o que define o comportamento (custos,
capacidades, se e desfeito ao sair, antes de que procedimentos, a marca do
paciente). Referencias entre regras, como "o preparo consome aquele recurso",
sao comparadas pelo conteudo do recurso referenciado, nao pelo nome.

Com --registro, resume tambem a sessao gravada pelo assistente: tempo,
perguntas respondidas e respostas recusadas.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from compilador.regras import ErroRegra, Regras, carregar_regras  # noqa: E402

GABARITOS = RAIZ.parent / "exemplos" / "avaliacao" / "teste-usuario"


def _recurso(r) -> dict:
    return {"capacidade": r.capacidade, "custo de reposição": r.custo_reposicao}


def _preparo(p, recursos) -> dict:
    return {"custo": p.custo,
            "desfeito ao sair": p.desfeito_ao_sair,
            "exigido antes de": sorted(p.exigido_antes_de),
            "consome": _recurso(recursos[p.consome]) if p.consome else None}


def forma(regras: Regras) -> dict[str, list[dict]]:
    """As regras sem nomes nem textos, so com o que define o comportamento."""
    recursos = {r.nome: r for r in regras.recursos}
    preparos = {p.nome: p for p in regras.preparos}
    return {
        "recurso": [_recurso(r) for r in regras.recursos],
        "preparo": [_preparo(p, recursos) for p in regras.preparos],
        "consumo": [{"procedimento": c.procedimento, "quantidade": c.quantidade,
                     "recurso": _recurso(recursos[c.recurso])} for c in regras.consumos],
        "exigencia": [{"marca": e.marca,
                       "quando": ("início da visita" if e.no_inicio_da_visita
                                  else f"antes de {', '.join(sorted(e.antes_de))}"),
                       "custo da conferência": e.custo if e.no_inicio_da_visita else None,
                       "preparo": _preparo(preparos[e.preparo], recursos)}
                      for e in regras.exigencias],
    }


def _diferencas_entre(esperado: dict, obtido: dict, prefixo: str = "") -> list[str]:
    difs = []
    for campo in esperado:
        a, b = esperado[campo], obtido.get(campo)
        if isinstance(a, dict) and isinstance(b, dict):
            difs += _diferencas_entre(a, b, f"{prefixo}{campo} → ")
        elif a != b:
            difs.append(f"{prefixo}{campo}: esperado {a!r}, escrito {b!r}")
    return difs


def comparar(escrito: Regras, gabarito: Regras) -> list[str]:
    """Lista de diferencas em linguagem simples; vazia se a regra esta certa."""
    difs = []
    fe, fg = forma(escrito), forma(gabarito)
    for modelo in fg:
        sobra = list(fe[modelo])
        faltam = []
        for item in fg[modelo]:
            if item in sobra:
                sobra.remove(item)
            else:
                faltam.append(item)
        for esperado, obtido in zip(faltam, sobra):
            difs += [f"{modelo}: {d}" for d in _diferencas_entre(esperado, obtido)]
        for esperado in faltam[len(sobra):]:
            difs.append(f"{modelo}: faltou um {modelo} ({esperado})")
        for obtido in sobra[len(faltam):]:
            difs.append(f"{modelo}: sobrou um {modelo} que o gabarito não tem ({obtido})")
    return difs


def resumo_do_registro(arquivo: Path) -> dict:
    eventos = [json.loads(l) for l in arquivo.read_text(encoding="utf-8").splitlines() if l]
    fim = next((e for e in reversed(eventos) if e["tipo"] == "fim"), None)
    return {
        "tempo (s)": eventos[-1]["t"] if eventos else 0,
        "respostas": sum(e["tipo"] == "resposta" for e in eventos),
        "recusas": sum(e["tipo"] == "recusa" for e in eventos),
        "textos das recusas": [e["texto"].strip(" !") for e in eventos if e["tipo"] == "recusa"],
        "cancelou": any(e["tipo"] == "fim" and e["texto"] == "cancelado" for e in eventos),
        "terminou": fim is not None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="acs.py conferir-teste")
    parser.add_argument("sessao", help="arquivo .toml gravado na tarefa")
    parser.add_argument("--tarefa", required=True, choices=["t1", "t2", "t3"])
    parser.add_argument("--registro", help="arquivo .jsonl gravado pelo assistente")
    args = parser.parse_args(argv)

    gabarito = carregar_regras(str(GABARITOS / f"gabarito-{args.tarefa}.toml"))
    try:
        escrito = carregar_regras(args.sessao)
    except ErroRegra as erro:
        print(f"{args.tarefa}: a regra não pôde ser lida: {erro}")
        return 1

    difs = comparar(escrito, gabarito)
    print(f"{args.tarefa}: {'CERTA' if not difs else f'{len(difs)} diferença(s)'}")
    for d in difs:
        print(f"  - {d}")
    if args.registro:
        resumo = resumo_do_registro(Path(args.registro))
        print(f"  tempo: {resumo['tempo (s)']:.0f} s | respostas: {resumo['respostas']} | "
              f"recusas: {resumo['recusas']}" + (" | CANCELOU" if resumo["cancelou"] else ""))
        for texto in resumo["textos das recusas"]:
            print(f"    recusa: {texto}")
    return 0 if not difs else 1


if __name__ == "__main__":
    sys.exit(main())
