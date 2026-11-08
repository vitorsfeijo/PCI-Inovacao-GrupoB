# Compilador de regras para o planejador de visitas do ACS

Projeto em Ciência e Inovação (INF99003), Ciclo 3, Grupo B.
Luis Henrique Caselani Macedo Junior · Manuela Cristina Zen Dalmonte · Vítor Santana Feijó

Continuação do projeto do Grupo B do Ciclo 2, em [`../PCI-Saude-GroupB`](../PCI-Saude-GroupB).

> **Estado:** etapas 1 e 2 concluídas. O compilador já gera domínio e problema
> para os modelos A, B e C; as demais etapas estão na lista abaixo.

---

## O problema

O planejador do Ciclo 2 garante, por meio de um domínio PDDL, que cada visita
respeite as regras da Lei 11.350/2006 e os recursos disponíveis. A principal
conclusão daquele ciclo (experimento E10) é que o planejamento se adapta a
**regras novas sem mudar o código**, enquanto uma solução procedural precisa
ser reescrita.

Mas acrescentar uma regra hoje exige saber PDDL, e uma regra que se explica em
uma frase espalha mudanças por vários lugares. A regra sintética da máscara,
por exemplo, ocupa cerca de 35 linhas no `dominio-estendido.pddl`: predicados
novos, três ações novas, efeitos a mais nas ações de deslocamento, uma
precondição a mais nas três variantes de início de visita, e ainda trechos no
gerador de problema e no carregador da planilha.

Na prática, só quem programa consegue acrescentar regras.

## A proposta

Deixar que a equipe descreva uma regra preenchendo **modelos fixos**, e que um
**compilador** transforme esses modelos em PDDL de forma determinística, sem
LLM. A expressividade fica limitada aos modelos, e isso é aceito de propósito:
o que não cabe nos modelos continua exigindo PDDL escrito à mão.

```
assistente interativo  ──gera──▶  regras.toml  ──compilador──▶  domínio PDDL
(pergunta campo a campo)          (fica salvo)                  + fatos do problema
```

- O **assistente** pergunta cada campo de cada modelo e valida a resposta na
  hora. No fim, salva um arquivo TOML.
- O **arquivo TOML** pode ser revisado, editado à mão, versionado e reaproveitado.
- O **compilador** só conhece o TOML. Isso o mantém simples de testar.

O `dominio-legal.pddl` do Ciclo 2 é **somente lido, nunca alterado**: as normas
ficam travadas e as regras da equipe são aplicadas por cima. O mesmo vale para o
código do Ciclo 2: o gerador de problema dele continua gerando o problema do
domínio legal, e o compilador acrescenta o que as regras exigem.

---

## Os modelos de regra

Os modelos saíram da comparação entre o `dominio-legal.pddl` e o
`dominio-estendido.pddl`. O estendido é exatamente o legal acrescido das três
regras sintéticas, e cada uma delas se decompõe nas peças abaixo.

| Modelo | Significado | O que gera no PDDL |
|---|---|---|
| **A. Recurso** | existe um estoque de R, com capacidade N, reposto só na UBS | predicados de nível, ação `repor-R`, fatos iniciais |
| **B. Preparo** | o ACS pode fazer Y, consumindo R; sair da casa desfaz Y | predicado, ação Y, `(not Y)` em `mover` e `desviar-para-ubs` |
| **C. Pré-requisito** | os procedimentos P1, P2… exigem Y antes | precondição a mais nessas ações |
| **D. Consumo** | o procedimento P gasta uma unidade de R | parâmetros, precondição e efeito a mais em P |
| **E. Exigência por paciente** | pacientes marcados com M exigem Y para iniciar a visita | marca no paciente, ações de conferência, precondição no início da visita |

Como as regras sintéticas do Ciclo 2 se escrevem com eles:

| Regra sintética | Modelos |
|---|---|
| Higienização das mãos | A (álcool) + B (higienizar, consome álcool) + C (procedimentos do § 4º) |
| Proteção respiratória | A (máscaras) + B (vestir, consome máscara) + E (marca "exige proteção") |
| Coletor de perfurocortante | A (coletor) + D (glicemia consome coletor) |

**Escopo inicial: modelos A, B e C**, suficientes para a higienização das mãos.
D e E vêm depois que o primeiro ciclo estiver validado.

## Formato do arquivo de regras

O pré-requisito (C) é escrito como um campo do preparo, porque sempre se refere
a um preparo. Exemplo completo em [`exemplos/higienizacao.toml`](exemplos/higienizacao.toml).

```toml
[[recurso]]
nome = "alcool"
capacidade = 6          # unidades por carga
custo_reposicao = 3     # minutos para repor na UBS

[[preparo]]
nome = "higienizar-maos"
estado = "maos-higienizadas"   # o que passa a valer depois do preparo
consome = "alcool"             # opcional
custo = 2                      # minutos
desfeito_ao_sair = true        # opcional, padrão true
exigido_antes_de = ["pressao", "glicemia", "temperatura", "medicacao", "antropometria"]
```

| Modelo | Campo | Obrigatório | Significado |
|---|---|---|---|
| recurso | `nome` | sim | nome do estoque; vira o predicado de nível |
| recurso | `capacidade` | sim | unidades por carga (≥ 1) |
| recurso | `custo_reposicao` | sim | minutos para repor na UBS (≥ 0) |
| preparo | `nome` | sim | nome da ação que o ACS executa |
| preparo | `estado` | sim | condição que passa a valer depois do preparo |
| preparo | `custo` | sim | minutos (≥ 0) |
| preparo | `consome` | não | recurso gasto a cada execução |
| preparo | `desfeito_ao_sair` | não | se sair da casa desfaz o estado (padrão `true`) |
| preparo | `exigido_antes_de` | não | procedimentos que só acontecem com o estado valendo |

Os nomes seguem a regra do PDDL: minúsculas, sem acento nem espaço, com hífen
entre as palavras. O `estado` tem nome próprio porque não dá para derivá-lo do
nome da ação em português (`higienizar-maos` → `maos-higienizadas`).

Os procedimentos aceitos formam uma lista fechada, ligada às ações do domínio
legal, para que ninguém precise conhecer os nomes internos do PDDL:

| Nome na regra | Ação no domínio |
|---|---|
| `pressao` | `aferir-pressao-arterial` |
| `glicemia` | `medir-glicemia-capilar` |
| `temperatura` | `aferir-temperatura-axilar` |
| `medicacao` | `orientar-administracao-medicacao` |
| `antropometria` | `verificacao-antropometrica` |
| `vacinal` | `verificar-caderneta-vacinal` |

## Validação

O compilador recusa regras malformadas com **mensagens em português** que
dizem o que está errado e qual é o valor válido. Por exemplo:

- o preparo `higienizar-maos` consome `alcool`, mas não há recurso com esse nome;
- o procedimento `glicose` não existe; os válidos são `pressao`, `glicemia`, …;
- dois recursos com o mesmo nome;
- capacidade menor que 1.

O assistente usa as mesmas validações, campo a campo.

## Como saberemos que funciona

**Teste de equivalência.** As regras sintéticas, escritas como modelos e
compiladas sobre o domínio legal, precisam reproduzir o `dominio-estendido.pddl`
escrito à mão pelo Grupo B do Ciclo 2:

1. **Na estrutura:** mesmas ações, precondições e efeitos.
2. **No comportamento:** mesmos planos e custos nas instâncias dos experimentos.

No escopo inicial (A, B e C), o teste compara só as partes da higienização: as
ações `higienizar-maos` e `repor-alcool`, as precondições nos cinco
procedimentos e os efeitos em `mover` e `desviar-para-ubs`. A equivalência
completa vem com D e E.

---

## Etapas

1. [x] Compilador do domínio para os modelos A, B e C.
2. [x] Geração dos fatos do problema a partir das regras, sobre o problema
       que o Ciclo 2 gera para o domínio legal.
3. [ ] Validação com mensagens em português.
4. [ ] Teste de equivalência da higienização.
5. [ ] Assistente interativo que gera o TOML.
6. [ ] Modelos D e E e teste de equivalência completo.
7. [ ] Integração com a linha de comando do `acsplan` e texto legível das
       ações novas no roteiro do ACS.
8. [ ] Avaliação com regras que não existem no domínio estendido e, se
       possível, com alguém que não programa.

## Em aberto

- **Usuário-alvo:** quem vai escrever as regras (enfermeiro, coordenação da
  UBS, gestão municipal)? Define o tom das perguntas e das mensagens.
- **Integração com o código do Ciclo 2:** o compilador reaproveita o parser
  PDDL de `acsplan/logica/planejador.py`; falta decidir se o código final vive
  aqui ou dentro do `acsplan`.

## Como usar

Dentro desta pasta:

```bash
# imprime o domínio compilado
python -m compilador exemplos/higienizacao.toml

# grava em arquivo
python -m compilador exemplos/higienizacao.toml -o dominio-com-regras.pddl

# outro domínio de entrada ou outro nome para o domínio gerado
python -m compilador regras.toml --dominio outro.pddl --nome meu-dominio
```

Para planejar, o problema também precisa dos fatos das regras. O compilador
recebe um problema gerado pelo Ciclo 2 **para o domínio legal** e grava a
versão com as regras:

```bash
python -m compilador exemplos/higienizacao.toml -o dominio.pddl \
    --problema problema-legal.pddl --saida-problema problema.pddl
```

O que entra no problema, para cada recurso de capacidade N:

- `(R nN)` e `(nivel-maximo-R nN)`: o turno começa com o estoque cheio, e a
  reposição na UBS enche até N;
- níveis `n…` e fatos `(prox …)` a mais, quando N passa do maior nível que o
  problema já tinha.

Preparos não acrescentam nada: o estado começa falso, e no PDDL o que não está
no estado inicial é falso. O problema também passa a apontar para o domínio
compilado (`visita-domiciliar-acs-regras`, ou o nome dado em `--nome`).

Quem usa o pipeline do Ciclo 2 em Python pode chamar
`compilador.gerar_problema_com_regras(dados, roteamento, regras, caminho,
nome_dominio=...)`, que gera o problema legal e aplica as regras de uma vez.

## Estrutura

```
compilador/
  regras.py      leitura do TOML e conferência de cada campo
  dominio.py     aplica os modelos sobre a árvore do domínio
  problema.py    acrescenta ao problema os fatos que as regras exigem
  pddl.py        escreve a árvore (domínio ou problema) como PDDL legível
  ciclo2.py      caminhos e parser PDDL do Ciclo 2 (../PCI-Saude-GroupB)
  __main__.py    linha de comando
exemplos/
  higienizacao.toml   regra sintética da higienização, como no Ciclo 2
```

## Observações

- **Falha herdada do Ciclo 2.** A ação `retornar-a-rota` (voltar da UBS para a
  casa) não desfaz nenhum estado. Por isso o planejador pode higienizar as mãos
  na UBS e chegar à casa ainda com elas "higienizadas"; o mesmo vale para a
  supervisão. O domínio estendido do Ciclo 2 tem exatamente esse comportamento,
  e o compilador o reproduz de propósito, para que o teste de equivalência seja
  possível. Corrigir é decidir se `retornar-a-rota` também é uma ação de saída.

## Requisitos

Python 3.11 ou superior (leitura de TOML com `tomllib`, da biblioteca padrão).
O Ciclo 2 pedia 3.10+; o requisito sobe por causa do TOML.
