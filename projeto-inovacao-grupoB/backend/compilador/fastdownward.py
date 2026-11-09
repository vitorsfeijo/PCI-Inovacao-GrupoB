"""
Fast Downward como planejador OPCIONAL.

O planejador do Ciclo 2 (Python puro, h_max e h_add) nao escala com muitas
regras: com as sete regras da avaliacao e 10 pacientes, nao termina em 10
minutos. O Fast Downward, planejador de referencia da area, acha um plano
para o mesmo caso em 0,02 s de busca, e o seu modo otimo (A* com LM-cut)
reproduz os otimos do h_max nos casos menores, de 10 a 13 vezes mais rapido.

Ele e opcional: se o pacote `up-fast-downward` estiver instalado no mesmo
Python (pip install up-fast-downward, com versoes ja compiladas para
Windows, Linux e macOS), o comando planejar o usa; senao, tudo continua
funcionando com o planejador do Ciclo 2.

O Fast Downward le os MESMOS arquivos PDDL que o compilador gera. O plano que
ele devolve e validado na tarefa do nosso planejador (mesmas precondicoes e
custos) antes de seguir para a limpeza e o roteiro.
"""

from __future__ import annotations

import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import ciclo2

ciclo2.garantir_caminho()
from acsplan.logica.planejador import Resultado  # noqa: E402

PACOTE = "up-fast-downward"
INSTALACAO = f"pip install {PACOTE}"

# Configuracoes do Fast Downward usadas aqui.
OTIMO = "seq-opt-lmcut"          # A* com LM-cut: plano otimo
BOM = "lama"                     # LAMA: acha rapido e continua melhorando
PRIMEIRO = "lama-first"          # LAMA: para no primeiro plano

# Codigos de saida do Fast Downward (driver/returncodes.py).
_SEM_SOLUCAO_PROVADO = {10, 11}  # tradutor ou busca provaram que nao ha plano
_SEM_SOLUCAO_INCOMPLETO = {12}   # busca incompleta esgotou sem achar


def driver() -> Path | None:
    """Caminho do fast-downward.py instalado, ou None se nao houver.

    O pacote e so LOCALIZADO, nao importado: importar `up_fast_downward`
    exige o framework Unified Planning, que nao usamos. Basta o executavel
    que ele traz, chamado com os nossos arquivos PDDL.
    """
    import importlib.util
    especificacao = importlib.util.find_spec("up_fast_downward")
    if especificacao is None or not especificacao.submodule_search_locations:
        return None
    pasta = Path(list(especificacao.submodule_search_locations)[0])
    caminho = pasta / "downward" / "fast-downward.py"
    return caminho if caminho.exists() else None


def disponivel() -> bool:
    return driver() is not None


def _ler_plano(arquivo: Path) -> list[str]:
    """'(mover acs1 ubs casa-p6)' -> 'mover(acs1, ubs, casa-p6)', o formato
    do planejador do Ciclo 2."""
    plano = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha.startswith("("):
            nome, *argumentos = linha.strip("()").split()
            plano.append(f"{nome}({', '.join(argumentos)})")
    return plano


def _ultimo_plano(pasta: Path) -> Path | None:
    """O LAMA grava plano.1, plano.2, ... (cada um melhor que o anterior);
    as configuracoes que param no primeiro gravam so `plano`."""
    numerados = sorted(pasta.glob("plano.*"), key=lambda p: int(p.suffix[1:]))
    if numerados:
        return numerados[-1]
    unico = pasta / "plano"
    return unico if unico.exists() else None


def validar(tarefa, plano: list[str]) -> int | None:
    """Executa o plano na tarefa do nosso planejador. Devolve o custo, ou
    None se alguma acao nao existir, nao for aplicavel ou o objetivo faltar."""
    por_nome = {acao.assinatura: acao for acao in tarefa.acoes}
    estado, custo = tarefa.estado_inicial, 0
    for passo in plano:
        acao = por_nome.get(passo)
        if acao is None or not acao.pre_pos <= estado or acao.pre_neg & estado:
            return None
        estado = (estado - acao.remocoes) | acao.adicoes
        custo += acao.custo
    return custo if tarefa.e_objetivo(estado) else None


def resolver(caminho_dominio: str, caminho_problema: str, tarefa, *,
             configuracao: str, limite_segundos: float) -> Resultado:
    """Roda o Fast Downward e devolve um Resultado no formato do Ciclo 2.

    `tarefa` e a tarefa do nosso planejador para os mesmos arquivos; serve
    para validar o plano e calcular o custo.
    """
    caminho_driver = driver()
    if caminho_driver is None:
        raise RuntimeError(f"Fast Downward não instalado ({INSTALACAO})")

    limite = max(1, math.ceil(limite_segundos))
    inicio = time.perf_counter()
    with tempfile.TemporaryDirectory() as pasta_temporaria:
        pasta = Path(pasta_temporaria)
        comando = [sys.executable, str(caminho_driver),
                   "--overall-time-limit", str(limite),
                   "--plan-file", str(pasta / "plano"),
                   "--alias", configuracao,
                   str(Path(caminho_dominio).resolve()),
                   str(Path(caminho_problema).resolve())]
        try:
            execucao = subprocess.run(comando, cwd=pasta, capture_output=True, text=True,
                                      timeout=limite + 60)
            codigo = execucao.returncode
        except subprocess.TimeoutExpired:
            codigo = None
        arquivo = _ultimo_plano(pasta)
        plano = _ler_plano(arquivo) if arquivo else []
    segundos = time.perf_counter() - inicio

    if plano:
        custo = validar(tarefa, plano)
        if custo is None:
            raise RuntimeError("o plano do Fast Downward não é válido na tarefa do "
                               "planejador do Ciclo 2; os dois discordam sobre o domínio")
        return Resultado(True, plano, custo, 0, 0, segundos)
    if codigo in _SEM_SOLUCAO_PROVADO:
        motivo = "espaco de estados exaurido: problema sem solucao (Fast Downward)"
    elif codigo in _SEM_SOLUCAO_INCOMPLETO:
        motivo = "limite: a busca incompleta do Fast Downward terminou sem plano"
    else:
        motivo = f"timeout de {limite}s (Fast Downward, código {codigo})"
    return Resultado(False, [], 0, 0, 0, segundos, motivo)
