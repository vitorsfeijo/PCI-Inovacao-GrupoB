"""
Escrita de arvores PDDL (listas aninhadas) como texto legivel.

A leitura usa o parser do Ciclo 2 (`ler_sexp`), que devolve listas de
strings. Aqui fazemos o caminho inverso, quebrando linhas so quando a
expressao nao cabe na largura.
"""

from __future__ import annotations

from typing import Any

LARGURA = 80


def em_linha(no: Any) -> str:
    if isinstance(no, str):
        return no
    return "(" + " ".join(em_linha(filho) for filho in no) + ")"


def formatar(no: Any, recuo: int = 0) -> str:
    """Formata `no`, supondo que ele comeca na coluna `recuo`."""
    texto = em_linha(no)
    if isinstance(no, str) or recuo + len(texto) <= LARGURA or not no:
        return texto
    if all(isinstance(filho, str) for filho in no):
        return _quebrar_palavras(no, recuo)

    cabeca, *resto = no
    dentro = recuo + 2
    linhas = ["(" + formatar(cabeca, recuo + 1)]
    # nome logo depois da palavra-chave fica na mesma linha: "(:action mover"
    if (isinstance(cabeca, str) and cabeca.startswith(":") and resto
            and isinstance(resto[0], str) and not resto[0].startswith(":")):
        linhas[0] += " " + resto.pop(0)
    i = 0
    while i < len(resto):
        item = resto[i]
        # palavra-chave seguida do seu valor, na mesma linha: ":effect (and ..."
        if isinstance(item, str) and item.startswith(":") and i + 1 < len(resto):
            valor = formatar(resto[i + 1], dentro + len(item) + 1)
            linhas.append(" " * dentro + item + " " + valor)
            i += 2
        else:
            linhas.append(" " * dentro + formatar(item, dentro))
            i += 1
    return "\n".join(linhas) + ")"


def _quebrar_palavras(palavras: list[str], recuo: int) -> str:
    """Lista so de nomes (ex.: parametros tipados): quebra como texto corrido."""
    linhas = ["(" + palavras[0]]
    for palavra in palavras[1:]:
        coluna = (recuo if len(linhas) == 1 else 0) + len(linhas[-1])
        if coluna + 1 + len(palavra) + 1 > LARGURA:
            linhas.append(" " * (recuo + 1) + palavra)
        else:
            linhas[-1] += " " + palavra
    return "\n".join(linhas) + ")"


def escrever_dominio(arvore: list, cabecalho: list[str]) -> str:
    """Texto completo do dominio, com uma linha em branco entre as secoes."""
    _, nome, *secoes = arvore
    partes = [";; " + linha if linha else ";;" for linha in cabecalho]
    partes.append("")
    partes.append(f"(define {em_linha(nome)}")
    for secao in secoes:
        partes.append("")
        partes.append("  " + formatar(secao, 2))
    partes.append(")")
    return "\n".join(partes) + "\n"
