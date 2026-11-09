"""
Planejamentos em segundo plano.

Planejar pode levar de segundos a um minuto, entao a API nao espera: cria uma
tarefa, devolve o numero dela, e a interface acompanha o progresso (as mesmas
mensagens que o terminal mostra) ate o resultado chegar.

O pedido e traduzido para os MESMOS argumentos da linha de comando e passa
pelo mesmo analisador (planejar.construir_parser): opcoes invalidas sao
recusadas do mesmo jeito, sem uma segunda validacao para manter.
"""

from __future__ import annotations

import itertools
import tempfile
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from compilador.planejar import com_mensagens, construir_parser, executar

from .api import PedidoInvalido, caminho_da_planilha

# Opcoes aceitas pela API -> como viram argumentos da linha de comando.
OPCOES_VALOR = {"orcamento": "--orcamento", "max_pacientes": "--max-pacientes",
                "estrategia": "--estrategia", "planejador": "--planejador",
                "limite": "--limite", "janela": "--janela", "metodo": "--metodo",
                "semente": "--semente"}
OPCOES_SIM_NAO = {"sem_selecao": "--sem-selecao", "sem_limpeza": "--sem-limpeza",
                  "sem_precedencia": "--sem-precedencia"}
LIMITE_MAXIMO = 300.0          # segundos de busca, no maximo, por pedido
TAMANHO_MAXIMO_PLANILHA = 2_000_000
SIMULTANEAS = 2                # planejamentos ao mesmo tempo (usam muito processador)
GUARDADAS = 50                 # tarefas antigas mantidas para consulta


def argumentos(pedido: dict, pasta: Path) -> list[str]:
    """Pedido da API -> argumentos do `planejar` (grava regras e planilha em `pasta`)."""
    argv: list[str] = []
    regras = pedido.get("regras_toml")
    if regras:
        if not isinstance(regras, str):
            raise PedidoInvalido("'regras_toml' deve ser o texto do arquivo de regras")
        (pasta / "regras.toml").write_text(regras, encoding="utf-8")
        argv.append(str(pasta / "regras.toml"))

    planilha = pedido.get("planilha") or {"exemplo": "exemplo-ciclo2"}
    if "exemplo" in planilha:
        argv += ["--dados", str(caminho_da_planilha(planilha["exemplo"]))]
    elif "csv" in planilha:
        texto = planilha["csv"]
        if not isinstance(texto, str) or len(texto) > TAMANHO_MAXIMO_PLANILHA:
            raise PedidoInvalido("'csv' deve ser o texto da planilha, com até 2 MB")
        (pasta / "pacientes.csv").write_text(texto, encoding="utf-8")
        argv += ["--dados", str(pasta / "pacientes.csv")]
    elif "sintetica" in planilha:
        try:
            n, semente = (int(x) for x in planilha["sintetica"])
        except (TypeError, ValueError):
            raise PedidoInvalido("'sintetica' deve ser [pacientes, semente]") from None
        argv += ["--instancia-sintetica", str(n), str(semente)]
    else:
        raise PedidoInvalido("'planilha' deve ter 'exemplo', 'csv' ou 'sintetica'")

    opcoes = pedido.get("opcoes") or {}
    desconhecidas = set(opcoes) - set(OPCOES_VALOR) - set(OPCOES_SIM_NAO)
    if desconhecidas:
        raise PedidoInvalido(f"opções desconhecidas: {', '.join(sorted(desconhecidas))}")
    for chave, opcao in OPCOES_VALOR.items():
        if opcoes.get(chave) not in (None, ""):
            valor = opcoes[chave]
            if chave == "limite":
                try:
                    valor = min(float(valor), LIMITE_MAXIMO)
                except (TypeError, ValueError):
                    raise PedidoInvalido("'limite' deve ser um número de segundos") from None
            argv += [opcao, str(valor)]
    for chave, opcao in OPCOES_SIM_NAO.items():
        if opcoes.get(chave):
            argv.append(opcao)
    return argv


def analisar(argv: list[str]):
    """Os argumentos passam pelo analisador da linha de comando, que, em vez
    de encerrar o programa num erro, recusa o pedido."""
    analisador = construir_parser()

    def recusar(mensagem: str):
        raise PedidoInvalido(f"opção inválida: {mensagem}")

    analisador.error = recusar
    return analisador.parse_args(argv)


@dataclass
class Tarefa:
    id: str
    estado: str = "na fila"            # na fila, rodando, pronta, erro
    mensagens: list[str] = field(default_factory=list)
    resultado: dict | None = None
    erro: str | None = None
    criada: float = field(default_factory=time.time)

    def como_dict(self) -> dict:
        return {"id": self.id, "estado": self.estado, "mensagens": list(self.mensagens),
                "resultado": self.resultado, "erro": self.erro}


class Gerenciador:
    def __init__(self) -> None:
        self._tarefas: dict[str, Tarefa] = {}
        self._trava = threading.Lock()
        self._vagas = threading.Semaphore(SIMULTANEAS)
        self._contador = itertools.count(1)

    def criar(self, pedido: dict) -> Tarefa:
        # erros de formato aparecem ja na criacao (erro 400), nao na tarefa
        with tempfile.TemporaryDirectory() as conferencia:
            analisar(argumentos(pedido, Path(conferencia)))
        tarefa = Tarefa(id=str(next(self._contador)))
        with self._trava:
            self._tarefas[tarefa.id] = tarefa
            antigas = sorted(self._tarefas.values(), key=lambda t: t.criada)[:-GUARDADAS]
            for velha in antigas:
                if velha.estado in ("pronta", "erro"):
                    del self._tarefas[velha.id]
        threading.Thread(target=self._rodar, args=(tarefa, pedido), daemon=True).start()
        return tarefa

    def consultar(self, identificador: str) -> Tarefa | None:
        with self._trava:
            return self._tarefas.get(identificador)

    def _rodar(self, tarefa: Tarefa, pedido: dict) -> None:
        with self._vagas:
            tarefa.estado = "rodando"
            com_mensagens(tarefa.mensagens.append)
            try:
                with tempfile.TemporaryDirectory() as pasta:
                    args = analisar(argumentos(pedido, Path(pasta)))
                    tarefa.resultado = executar(args)
                tarefa.estado = "pronta"
            except Exception as erro:     # nao derruba o servidor; vai para a tarefa
                tarefa.erro = f"{type(erro).__name__}: {erro}"
                tarefa.mensagens.append(traceback.format_exc(limit=3))
                tarefa.estado = "erro"
