"""
Instanciacao (grounding) com poda antecipada.

O planejador do Ciclo 2 instancia cada acao gerando TODAS as combinacoes de
objetos para os seus parametros (itertools.product) e so depois descarta as
que violam uma precondicao estatica, como (prox ?n-1 ?n). Isso cresce
exponencialmente com o numero de parametros: cada recurso gasto numa acao
acrescenta dois ou mais parametros do tipo nivel. Com as sete regras da
avaliacao, a glicemia passa a ter sete parametros de nivel e, com 11 niveis,
11^7 combinacoes por paciente e local: bilhoes, que nao terminam.

Aqui os parametros sao ligados um a um, NA MESMA ORDEM, e cada precondicao
estatica e testada assim que todas as suas variaveis estao ligadas. Como
(prox ?n-1 ?n) determina ?n-1 a partir de ?n, cada recurso deixa de
multiplicar as combinacoes por 11. Os demais passos sao copiados do
original, e a ordem de enumeracao e a mesma (lexicografica nos parametros),
entao o resultado e IDENTICO ao do Ciclo 2: as mesmas acoes, na mesma ordem,
com os mesmos identificadores de fatos. Os testes conferem isso.

A copia do Ciclo 2 em acsplan/ nao e alterada: esta e uma subclasse que
substitui so o metodo de instanciacao.
"""

from __future__ import annotations

from . import ciclo2

ciclo2.garantir_caminho()
from acsplan.logica.planejador import AcaoInstanciada, TarefaPlanejamento  # noqa: E402


def _variaveis(literal: tuple) -> list[str]:
    return [termo for termo in literal[1:] if termo.startswith("?")]


class TarefaPlanejamentoPodada(TarefaPlanejamento):
    """TarefaPlanejamento do Ciclo 2 com a instanciacao podada."""

    def _instanciar_acoes(self, estaticos: set[str]) -> list[AcaoInstanciada]:
        instanciadas: list[AcaoInstanciada] = []
        init = self.problema.init

        for esquema in self.dominio.acoes:
            nomes = [p for p, _ in esquema.parametros]
            dominios = [self.objetos_por_tipo.get(t, []) for _, t in esquema.parametros]
            posicao = {nome: i for i, nome in enumerate(nomes)}

            # cada precondicao estatica e testada no passo em que sua ultima
            # variavel e ligada; as sem variavel, antes de tudo
            positivas: list[list[tuple]] = [[] for _ in nomes]
            negativas: list[list[tuple]] = [[] for _ in nomes]
            positivas_fixas, negativas_fixas = [], []
            for literais, por_passo, fixas in (
                    (esquema.pre_positivas, positivas, positivas_fixas),
                    (esquema.pre_negativas, negativas, negativas_fixas)):
                for literal in literais:
                    if literal[0] not in estaticos:
                        continue
                    passos = [posicao[v] for v in _variaveis(literal) if v in posicao]
                    (por_passo[max(passos)] if passos else fixas).append(literal)
            if any(l not in init for l in positivas_fixas) or \
                    any(l in init for l in negativas_fixas):
                continue

            for combinacao in self._combinacoes(nomes, dominios, positivas, negativas):
                ligacao = dict(zip(nomes, combinacao))
                # daqui em diante, igual ao original
                pre_pos = [self._aplicar(lit, ligacao) for lit in esquema.pre_positivas]
                pre_neg = [self._aplicar(lit, ligacao) for lit in esquema.pre_negativas]
                adicoes = [self._aplicar(l, ligacao) for l in esquema.adicoes]
                remocoes = [self._aplicar(l, ligacao) for l in esquema.remocoes]

                custo = self._resolver_custo(esquema.custo, ligacao)
                if custo is None:
                    continue

                pre_pos_din = frozenset(self._id(f) for f in pre_pos
                                        if f[0] not in estaticos)
                pre_neg_din = frozenset(self._id(f) for f in pre_neg
                                        if f[0] not in estaticos)

                assinatura = f"{esquema.nome}({', '.join(combinacao)})"
                instanciadas.append(AcaoInstanciada(
                    assinatura,
                    pre_pos_din,
                    pre_neg_din,
                    frozenset(self._id(f) for f in adicoes),
                    frozenset(self._id(f) for f in remocoes),
                    custo,
                ))
        return instanciadas

    def _combinacoes(self, nomes, dominios, positivas, negativas):
        """Combinacoes que passam nas precondicoes estaticas, em ordem
        lexicografica (a mesma de itertools.product)."""
        init = self.problema.init
        ligacao: dict[str, str] = {}
        escolhidos: list[str] = []

        def descer(k: int):
            if k == len(nomes):
                yield tuple(escolhidos)
                return
            for objeto in dominios[k]:
                ligacao[nomes[k]] = objeto
                if any(self._aplicar(l, ligacao) not in init for l in positivas[k]):
                    continue
                if any(self._aplicar(l, ligacao) in init for l in negativas[k]):
                    continue
                escolhidos.append(objeto)
                yield from descer(k + 1)
                escolhidos.pop()
            ligacao.pop(nomes[k], None)

        return descer(0)


def tarefa(caminho_dominio: str, caminho_problema: str) -> TarefaPlanejamentoPodada:
    """Carrega domínio e problema e monta a tarefa com a instanciação podada."""
    planejador = ciclo2.planejador()
    return TarefaPlanejamentoPodada(planejador.carregar_dominio(caminho_dominio),
                                    planejador.carregar_problema(caminho_problema))
