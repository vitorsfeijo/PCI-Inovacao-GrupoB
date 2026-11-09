# Compilador de regras para o planejador de visitas do ACS

Projeto em Ciência e Inovação (INF99003), Ciclo 3, Grupo B.
Luis Henrique Caselani Macedo Junior · Manuela Cristina Zen Dalmonte · Vítor Santana Feijó

> **[HOWTORUN.md](HOWTORUN.md):** como instalar, escrever regras e planejar o turno.
> **[DESIGN.md](DESIGN.md):** arquitetura, decisões de implementação e avaliação.

Continuação do projeto do Grupo B do Ciclo 2 ([`../PCI-Saude-GroupB`](../PCI-Saude-GroupB)),
que planeja o turno de visitas domiciliares do Agente Comunitário de Saúde
(ACS). Esta pasta funciona sozinha: a parte do Ciclo 2 que ela usa está
copiada, sem alterações, em [`backend/acsplan/`](backend/acsplan/LEIAME.md).

## O problema

O planejador do Ciclo 2 garante, com um domínio PDDL, que cada visita respeite
a Lei 11.350/2006 e os recursos disponíveis. A principal conclusão daquele
ciclo é que o planejamento se adapta a **regras novas sem mudar o código**.

Mas acrescentar uma regra exige saber PDDL, e uma regra que se explica em uma
frase espalha mudanças por vários lugares do domínio. Na prática, só quem
programa consegue acrescentar regras.

## A proposta

A equipe descreve a regra preenchendo **modelos fixos**, e um **compilador** a
transforma em PDDL de forma determinística, sem LLM. As normas (o domínio
legal) ficam travadas; as regras da equipe são aplicadas por cima.

```
assistente interativo  ──gera──▶  regras.toml  ──compilador──▶  domínio e problema PDDL
(pergunta campo a campo)          (fica salvo)                  ──▶ plano ──▶ roteiro do ACS
```

| Modelo | Exemplo |
|---|---|
| **A. Recurso** | o ACS leva 6 doses de álcool por saída, repostas na UBS |
| **B. Preparo** | higienizar as mãos, gastando uma dose; sair da casa desfaz |
| **C. Pré-requisito** | higienizar as mãos antes de aferir a pressão |
| **D. Consumo** | cada glicemia gasta 2 bolas de algodão |
| **E. Exigência por paciente** | quem tem suspeita de tuberculose exige N95 para iniciar a visita, ou luvas antes de um procedimento |

## Estado e resultados

Etapas 1 a 7 concluídas e a avaliação (etapa 8) quase toda; falta aplicar o
teste com usuários, cujo material está pronto.

- **Correto:** as três regras sintéticas do Ciclo 2, escritas como modelos,
  reproduzem o domínio estendido do Ciclo 2 **inteiro**: mesma estrutura e
  mesmo comportamento em 24 de 24 instâncias.
- **Mais curto que PDDL:** sete regras novas custaram de 7 a 18 linhas de TOML
  cada, contra 13 a 60 linhas de PDDL alteradas.
- **Barato para o turno:** cada regra acrescenta de 1 a 9 minutos ao turno
  ótimo de 386 min.
- **Escala:** com o Fast Downward (opcional) e o planejamento por janelas, as
  sete regras juntas com 10 pacientes geram o roteiro em ~30 s; o planejador
  do Ciclo 2 sozinho não termina a partir de seis regras.

Detalhes, números e limitações no [DESIGN.md](DESIGN.md#avaliação).

## Estrutura

```
acs.py        ponto de entrada: python3 acs.py <comando> (veja o HOWTORUN)
backend/      o código
  compilador/   o compilador, o assistente e o comando planejar
  acsplan/      cópia parcial, sem alterações, do Ciclo 2
  testes/       testes automáticos e scripts de avaliação
exemplos/     regras de exemplo e a avaliação (planilha, regras R1–R7, resultados,
              teste com usuários)
```
