"""
Assistente interativo: pergunta campo a campo e grava o arquivo de regras.

    python -m compilador.assistente regras.toml

Cada resposta e validada na hora, com os mesmos validadores do compilador;
uma resposta invalida faz a mesma pergunta de novo. Nomes ja usados pelo
dominio ou por outra regra sao recusados quando digitados.

Se o arquivo ja existe, as regras novas sao ACRESCENTADAS ao fim dele, sem
reescrever o que ja estava la (inclusive comentarios). Cancelar com Ctrl+C
ou Ctrl+D nao grava nada.

A entrada e a saida sao injetaveis (`entrada`, `escrever`), para que o
assistente possa ser testado com respostas programadas.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from . import ciclo2
from .dominio import compilar_dominio
from .regras import (DESCRICAO_PROCEDIMENTOS, PROCEDIMENTOS, ErroRegra, Recurso,
                     Regras, avisos, bloco_toml, carregar_regras, ler_regras,
                     sugerir_nome, validar_inteiro, validar_nome)


class Cancelado(Exception):
    """A pessoa interrompeu o assistente."""


def _nomes_do_dominio(arvore: list) -> set[str]:
    nomes: set[str] = set()
    for item in arvore[2:]:
        if isinstance(item, list) and item and item[0] == ":predicates":
            nomes.update(p[0] for p in item[1:])
        elif isinstance(item, list) and item and item[0] == ":action":
            nomes.add(item[1])
    return nomes


def _nomes_de_recurso(nome: str) -> list[str]:
    r = Recurso(nome, 1, 0)
    return [r.predicado, r.predicado_maximo, r.acao_reposicao]


class Assistente:

    def __init__(self, dominio: list, existentes: Regras | None = None, *,
                 entrada: Callable[[str], str] = input,
                 escrever: Callable[[str], None] = print) -> None:
        self.dominio = dominio
        self.entrada = entrada
        self.escrever = escrever
        self.existentes = existentes or Regras((), ())
        self.blocos: list[tuple[str, dict]] = []

        # nome -> quem ja usa, pronto para "ja e usado <dono>"
        self.usados: dict[str, str] = {n: "pelo domínio de entrada (lei ou Ciclo 2)"
                                       for n in _nomes_do_dominio(dominio)}
        for r in self.existentes.recursos:
            self._reservar(_nomes_de_recurso(r.nome), f"pelo recurso \"{r.nome}\"")
        for p in self.existentes.preparos:
            self._reservar([p.nome, p.estado], f"pelo preparo \"{p.nome}\"")

    # ------------------------------------------------------------------
    #  perguntas basicas
    # ------------------------------------------------------------------

    def _ler(self, pergunta: str) -> str:
        try:
            return self.entrada(pergunta).strip()
        except (EOFError, KeyboardInterrupt):
            raise Cancelado from None

    def _erro(self, mensagem: str) -> None:
        self.escrever(f"  ! {mensagem}")

    def _reservar(self, nomes: list[str], dono: str) -> None:
        for nome in nomes:
            self.usados[nome] = dono

    def pedir_nome(self, pergunta: str, gerados: Callable[[str], list[str]]) -> str:
        """Nome PDDL livre, com sugestao para nomes com acento ou espaco."""
        while True:
            resposta = self._ler(f"{pergunta}: ")
            problema = validar_nome(resposta)
            if problema:
                sugestao = sugerir_nome(resposta)
                if sugestao and sugestao != resposta:
                    if self.pedir_sim_nao(f"  Nomes precisam ser em minúsculas, sem "
                                          f"acento nem espaço. Usar \"{sugestao}\"?",
                                          padrao=True):
                        resposta = sugestao
                    else:
                        continue
                else:
                    self._erro(problema)
                    continue
            conflito = next((n for n in gerados(resposta) if n in self.usados), None)
            if conflito is None:
                return resposta
            if conflito == resposta:
                self._erro(f"o nome \"{resposta}\" já é usado {self.usados[conflito]}. "
                           f"Escolha outro")
            else:
                self._erro(f"esse nome geraria \"{conflito}\", que já é usado "
                           f"{self.usados[conflito]}. Escolha outro")

    def pedir_inteiro(self, pergunta: str, minimo: int, padrao: int | None = None) -> int:
        sufixo = f" [{padrao}]" if padrao is not None else ""
        while True:
            resposta = self._ler(f"{pergunta}{sufixo}: ")
            if not resposta and padrao is not None:
                return padrao
            try:
                valor = int(resposta)
            except ValueError:
                self._erro(f"digite um número inteiro. Recebido: \"{resposta}\"")
                continue
            problema = validar_inteiro(valor, minimo)
            if problema:
                self._erro(problema)
                continue
            return valor

    def pedir_sim_nao(self, pergunta: str, padrao: bool) -> bool:
        opcoes = "[S/n]" if padrao else "[s/N]"
        while True:
            resposta = self._ler(f"{pergunta} {opcoes}: ").lower()
            if not resposta:
                return padrao
            if resposta in ("s", "sim"):
                return True
            if resposta in ("n", "nao", "não"):
                return False
            self._erro("responda s (sim) ou n (não)")

    def pedir_opcao(self, pergunta: str, opcoes: list[tuple[str, str]]) -> str:
        """Uma opcao de uma lista numerada. Devolve o valor escolhido."""
        self.escrever(pergunta)
        for numero, (_, rotulo) in enumerate(opcoes, start=1):
            self.escrever(f"  {numero}. {rotulo}")
        while True:
            resposta = self._ler("Número: ")
            if resposta.isdigit() and 1 <= int(resposta) <= len(opcoes):
                return opcoes[int(resposta) - 1][0]
            self._erro(f"digite um número de 1 a {len(opcoes)}")

    def pedir_procedimentos(self) -> list[str]:
        nomes = list(PROCEDIMENTOS)
        self.escrever("Antes de quais procedimentos o preparo é obrigatório?")
        for numero, nome in enumerate(nomes, start=1):
            self.escrever(f"  {numero}. {DESCRICAO_PROCEDIMENTOS[nome]}")
        self.escrever("Digite os números separados por vírgula (ex.: 1,2,5), "
                      "\"todos\", ou deixe vazio para nenhum.")
        while True:
            resposta = self._ler("Procedimentos: ").lower().replace(" ", "")
            if not resposta:
                return []
            if resposta == "todos":
                return nomes
            partes = [p for p in resposta.split(",") if p]
            if all(p.isdigit() and 1 <= int(p) <= len(nomes) for p in partes):
                escolhidos = sorted({int(p) for p in partes})
                return [nomes[i - 1] for i in escolhidos]
            self._erro(f"use números de 1 a {len(nomes)} separados por vírgula")

    # ------------------------------------------------------------------
    #  modelos
    # ------------------------------------------------------------------

    def _recursos_disponiveis(self) -> list[str]:
        return ([r.nome for r in self.existentes.recursos]
                + [c["nome"] for m, c in self.blocos if m == "recurso"])

    def novo_recurso(self) -> dict:
        self.escrever("\nNovo RECURSO: um estoque finito que só é reposto na UBS "
                      "(ex.: álcool, máscaras).")
        nome = self.pedir_nome("Nome do recurso", _nomes_de_recurso)
        capacidade = self.pedir_inteiro("Quantas unidades o ACS leva por carga", 1)
        custo = self.pedir_inteiro("Quantos minutos leva para repor na UBS", 0, padrao=3)
        self._reservar(_nomes_de_recurso(nome), f"pelo recurso \"{nome}\"")
        return {"nome": nome, "capacidade": capacidade, "custo_reposicao": custo}

    def novo_preparo(self) -> dict:
        self.escrever("\nNovo PREPARO: algo que o ACS faz antes de certos "
                      "procedimentos (ex.: higienizar as mãos).")
        nome = self.pedir_nome("Nome da ação (ex.: higienizar-maos)", lambda n: [n])
        self._reservar([nome], f"pelo preparo \"{nome}\"")
        estado = self.pedir_nome("O que passa a valer depois dela "
                                 "(ex.: maos-higienizadas)", lambda n: [n])
        self._reservar([estado], f"pelo preparo \"{nome}\"")
        campos: dict = {"nome": nome, "estado": estado,
                        "custo": self.pedir_inteiro("Quantos minutos leva", 0)}

        recursos = self._recursos_disponiveis()
        if recursos:
            opcoes = [("", "nenhum")] + [(r, r) for r in recursos]
            consome = self.pedir_opcao("Ela gasta algum recurso a cada vez?", opcoes)
            if consome:
                campos["consome"] = consome
        else:
            self.escrever("(Nenhum recurso declarado ainda: este preparo não gastará "
                          "recurso. Declare o recurso antes, se precisar.)")

        campos["desfeito_ao_sair"] = self.pedir_sim_nao(
            "Sair da casa desfaz o preparo (precisa repetir na próxima casa)?",
            padrao=True)
        campos["exigido_antes_de"] = self.pedir_procedimentos()
        return campos

    # ------------------------------------------------------------------
    #  fluxo principal
    # ------------------------------------------------------------------

    def regras_completas(self) -> Regras:
        dados = {"recurso": [], "preparo": []}
        for r in self.existentes.recursos:
            dados["recurso"].append({"nome": r.nome, "capacidade": r.capacidade,
                                     "custo_reposicao": r.custo_reposicao})
        for p in self.existentes.preparos:
            campos = {"nome": p.nome, "estado": p.estado, "custo": p.custo,
                      "desfeito_ao_sair": p.desfeito_ao_sair,
                      "exigido_antes_de": list(p.exigido_antes_de)}
            if p.consome:
                campos["consome"] = p.consome
            dados["preparo"].append(campos)
        for modelo, campos in self.blocos:
            dados[modelo].append(campos)
        return ler_regras(dados)

    def executar(self) -> list[tuple[str, dict]]:
        """Conduz a conversa. Devolve os blocos novos, na ordem em que vieram."""
        while True:
            escolha = self.pedir_opcao("\nO que deseja adicionar?", [
                ("recurso", "um recurso (estoque reposto na UBS)"),
                ("preparo", "um preparo (feito antes de procedimentos)"),
                ("fim", "terminar"),
            ])
            if escolha == "fim":
                return self.blocos
            campos = self.novo_recurso() if escolha == "recurso" else self.novo_preparo()
            self.blocos.append((escolha, campos))
            self.escrever(f"\nAdicionado:\n{bloco_toml(escolha, campos).rstrip()}")


def texto_dos_blocos(blocos: list[tuple[str, dict]]) -> str:
    return "\n".join(bloco_toml(modelo, campos) for modelo, campos in blocos)


CABECALHO = """\
# Regras gravadas pelo assistente do compilador de regras.
# Pode ser editado à mão; para conferir, rode:
#     python -m compilador {nome}
"""


def gravar(caminho: Path, blocos: list[tuple[str, dict]], *, acrescentar: bool) -> None:
    novos = texto_dos_blocos(blocos)
    if acrescentar:
        atual = caminho.read_text(encoding="utf-8")
        separador = "" if atual.endswith("\n\n") else ("\n" if atual.endswith("\n") else "\n\n")
        caminho.write_text(atual + separador + novos, encoding="utf-8")
    else:
        caminho.write_text(CABECALHO.format(nome=caminho.name) + "\n" + novos,
                           encoding="utf-8")


def main(argv: list[str] | None = None, *, entrada: Callable[[str], str] = input,
         escrever: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m compilador.assistente",
        description="Cria ou amplia um arquivo de regras respondendo perguntas.")
    parser.add_argument("arquivo", nargs="?", default="regras.toml",
                        help="arquivo de regras (padrão: regras.toml)")
    args = parser.parse_args(argv)
    caminho = Path(args.arquivo)

    dominio = ciclo2.planejador().ler_sexp(str(ciclo2.DOMINIO_LEGAL))
    existentes = None
    if caminho.exists():
        try:
            existentes = carregar_regras(str(caminho))
        except ErroRegra as erro:
            escrever(f"O arquivo {caminho} já existe, mas tem problemas:")
            for problema in erro.problemas:
                escrever(f"  - {problema}")
            escrever("Corrija o arquivo ou escolha outro nome.")
            return 1
        total = len(existentes.recursos) + len(existentes.preparos)
        escrever(f"O arquivo {caminho} já existe, com {total} regra(s). "
                 f"As novas serão acrescentadas ao fim dele.")
    else:
        escrever(f"As regras serão gravadas em {caminho}.")
    escrever("Para cancelar sem gravar nada, use Ctrl+C.")

    assistente = Assistente(dominio, existentes, entrada=entrada, escrever=escrever)
    try:
        blocos = assistente.executar()
    except Cancelado:
        escrever("\nCancelado. Nada foi gravado.")
        return 1

    if not blocos:
        escrever("Nenhuma regra nova. Nada foi gravado.")
        return 0

    # conferencia final, com o compilador, antes de gravar
    try:
        regras = assistente.regras_completas()
        compilar_dominio(dominio, regras)
    except ErroRegra as erro:  # nao deveria acontecer: tudo foi validado antes
        escrever("As regras não passaram na conferência final:")
        for problema in erro.problemas:
            escrever(f"  - {problema}")
        escrever("Nada foi gravado.")
        return 1

    gravar(caminho, blocos, acrescentar=existentes is not None)
    escrever(f"\nGravado em {caminho}.")
    for aviso in avisos(regras):
        escrever(f"Aviso: {aviso}")
    escrever(f"Para gerar o domínio: python -m compilador {caminho} -o dominio.pddl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
