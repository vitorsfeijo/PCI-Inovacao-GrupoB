# Compilador de regras para o planejador de visitas do ACS

Projeto em Ciência e Inovação (INF99003), Ciclo 3, Grupo B.
Luis Henrique Caselani Macedo Junior · Manuela Cristina Zen Dalmonte · Vítor Santana Feijó

Continuação do projeto do Grupo B do Ciclo 2, em [`../PCI-Saude-GroupB`](../PCI-Saude-GroupB).
Esta pasta funciona sozinha: a parte do Ciclo 2 que o compilador usa está
copiada, sem alterações, em [`acsplan/`](acsplan/LEIAME.md).

> **Estado:** etapas 1 a 7 concluídas. Os cinco modelos (A a E) funcionam, e
> as três regras sintéticas do Ciclo 2, escritas como modelos, reproduzem o
> domínio estendido **inteiro**: mesma estrutura e mesmo comportamento em 24 de
> 24 instâncias. As regras podem ser escritas à mão ou pelo assistente
> interativo, e `python -m compilador planejar` vai da planilha de pacientes ao
> roteiro do ACS com as regras aplicadas. Falta a avaliação (etapa 8).

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

Para a pasta funcionar sozinha, o que o compilador usa do Ciclo 2 (domínios,
parser e planejador, gerador de problema, roteirizador, seleção de pacientes e
planilha de exemplo) está copiado em `acsplan/`, **sem nenhuma alteração**.
O [`acsplan/LEIAME.md`](acsplan/LEIAME.md) lista o que foi copiado, o que
ficou de fora e como conferir que a cópia continua idêntica ao original.

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

Os cinco modelos estão implementados. A, B e C vieram primeiro (suficientes
para a higienização); D e E completaram as outras duas regras.

## Formato do arquivo de regras

O pré-requisito (C) é escrito como um campo do preparo, porque sempre se refere
a um preparo. Exemplos: [`exemplos/higienizacao.toml`](exemplos/higienizacao.toml)
(só a higienização) e [`exemplos/sinteticas-ciclo2.toml`](exemplos/sinteticas-ciclo2.toml)
(as três regras sintéticas, com todos os modelos).

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

[[recurso]]
nome = "coletor"
capacidade = 3
custo_reposicao = 3
acao_reposicao = "trocar-coletor"   # opcional, padrão "repor-coletor"

[[consumo]]                    # a glicemia ocupa uma posição no coletor
procedimento = "glicemia"
recurso = "coletor"

[[exigencia]]                  # quem tem a marca exige máscara para iniciar a visita
nome = "protecao"
marca = "exige-protecao-respiratoria"
preparo = "vestir-mascara"
custo = 1                      # opcional, padrão 1
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
| recurso | `acao_reposicao` | não | nome da ação de reposição (padrão `repor-<nome>`) |
| consumo | `procedimento` | sim | procedimento que gasta o recurso |
| consumo | `recurso` | sim | recurso gasto, uma unidade por execução |
| exigencia | `nome` | sim | nome da conferência feita na porta; gera `<nome>-conferida`, `conferir-<nome>-exigida` e `conferir-<nome>-dispensada` |
| exigencia | `marca` | sim | marca do paciente; vem da coluna de mesmo nome da planilha, com `_` no lugar de `-` |
| exigencia | `preparo` | sim | preparo cujo estado é exigido para iniciar a visita |
| exigencia | `custo` | não | minutos da conferência quando exigida (padrão 1; dispensada custa 0) |
| recurso | `texto` | não | o que repor, como aparece no roteiro do ACS (padrão: o nome) |
| preparo | `texto` | não | a tarefa, como aparece no roteiro (padrão: o nome, ex. "Higienizar maos") |
| exigencia | `texto` | não | a conferência, como aparece no roteiro (padrão: "Conferir <nome> antes de entrar") |

O `texto` é o único campo em que acentos e espaços são livres: ele não entra no
PDDL, só no roteiro que o ACS recebe.

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
dizem o que está errado e qual é o valor aceito. Ele relata **todos os
problemas de uma vez**, para que quem escreveu a regra corrija tudo antes de
rodar de novo:

```
Não foi possível compilar regras.toml. 3 problemas encontrados:
  1. recurso "Álcool Gel", campo 'nome': "Álcool Gel" não serve como nome. Use só
     letras minúsculas sem acento e números, com hífen entre as palavras, começando
     por letra (ex.: "maos-higienizadas"). Sugestão: "alcool-gel".
  2. recurso "Álcool Gel", campo 'capacidade': deve ser um número inteiro, sem
     aspas. Recebido: '6'
  3. preparo "higienizar-maos", campo 'exigido_antes_de': procedimento(s)
     inexistente(s): 'glicose'. Os aceitos são: pressao, glicemia, temperatura, ...
```

A validação acontece em três níveis:

| Nível | O que confere | Onde |
|---|---|---|
| Campo | formato, tipo e faixa de cada valor; campos que faltam ou não existem | `regras.py`, funções `validar_*` |
| Regras entre si | nomes repetidos, preparo que consome recurso não declarado | `regras.py`, `ler_regras` |
| Regras e domínio | nome (ou nome derivado, como `repor-alcool`) já usado pelo domínio | `dominio.py` |

Erros de formato do TOML aparecem com linha e coluna. Os validadores de campo
devolvem a mensagem ou nada, para o assistente interativo reaproveitá-los
campo a campo.

Além dos erros, há **avisos**, que não impedem a compilação, para regras
válidas que provavelmente não fazem o que se espera:

- recurso que nenhum preparo consome (não muda nenhum plano);
- preparo sem `exigido_antes_de` (o planejador nunca vai fazê-lo);
- preparo exigido que não é desfeito ao sair (basta uma vez no turno inteiro);
- arquivo sem nenhuma regra.

## Como saberemos que funciona

**Teste de equivalência.** As regras sintéticas, escritas como modelos e
compiladas sobre o domínio legal, precisam reproduzir o `dominio-estendido.pddl`
escrito à mão pelo Grupo B do Ciclo 2. São duas comparações:

1. **Estrutura:** mesmos predicados e, em cada ação, os mesmos parâmetros,
   precondições, efeitos e custo. Os nomes das variáveis podem diferir: o
   compilador gera `?coletor` onde o domínio escrito à mão usa `?c`, e a
   comparação aceita qualquer troca de nomes entre variáveis do mesmo tipo.
2. **Comportamento:** em cada instância, o custo ótimo (A\* com h_max) é o mesmo
   nos dois lados, e o plano de cada um, executado no outro, é válido e tem o
   mesmo custo.

### Equivalência completa (modelos A a E)

As três regras sintéticas ([`exemplos/sinteticas-ciclo2.toml`](exemplos/sinteticas-ciclo2.toml))
são comparadas com o domínio estendido **inteiro**. No comportamento, a
comparação é entre os dois pipelines de ponta a ponta, a partir dos mesmos
dados de pacientes:

- **Ciclo 2:** `dominio-estendido.pddl` + problema gerado pelo Ciclo 2 para ele;
- **compilado:** `dominio-legal.pddl` + regras compiladas + problema legal com
  os fatos das regras.

**Resultado:** estrutura igual, e 24 de 24 instâncias equivalentes:

| Instâncias | Recursos | O que exercitam |
|---|---|---|
| 2 e 3 pacientes, 5 sementes | capacidades padrão do Ciclo 2 | 3 instâncias com paciente que exige máscara |
| 2 e 3 pacientes, 5 sementes | 2 doses de álcool, 1 máscara, coletor com 2 posições | 5 planos com reposição ou troca na UBS |
| 4 pacientes, sementes 2 e 164 | padrão e 1 máscara por carga | 2 pacientes com máscara; com 1 máscara, reposição obrigatória |

As sementes 2 e 164 são as únicas do gerador do Ciclo 2 (testadas até 200)
com dois pacientes que exigem máscara; sem elas, a falta de máscara nunca
seria exercitada.

### Equivalência parcial (higienização)

Antes de D e E existirem, a higienização ([`exemplos/higienizacao.toml`](exemplos/higienizacao.toml))
foi comparada com a **projeção** do estendido: o estendido sem os elementos da
máscara e do coletor. A projeção é mecânica, por nome de predicado: remove os
predicados dessas regras, as ações que só existiam para elas, os literais que
as mencionam e os parâmetros que ficam sem uso. Nada é editado à mão.

**Resultado:** estrutura igual, e 30 de 30 instâncias equivalentes (2 a 4
pacientes, 5 sementes, com o álcool do exemplo e com álcool para só 2 casas,
caso em que 11 planos precisam de reposição na UBS). O teste continua no
relatório, porque isola a higienização.

### Controle negativo

Para mostrar que o teste detecta diferenças, ele também roda com regras
alteradas de propósito, que precisam ser acusadas:

| Alteração | Estrutura | Comportamento |
|---|---|---|
| tirar `temperatura` de `exigido_antes_de` | acusa a precondição que falta | igual (ninguém precisa de temperatura) |
| `desfeito_ao_sair = false` | acusa os efeitos em `mover` e `desviar-para-ubs` | 125 × 129 |
| custo 3 em vez de 2 na higienização | acusa o custo | 132 × 129 |
| sem o consumo do coletor | acusa a glicemia | — |
| consumo na pressão em vez da glicemia | acusa as duas ações | — |
| sem a exigência da máscara | acusa predicados, conferências e início da visita | — |
| custo 2 na conferência | acusa a conferência exigida | — |
| coletor com reposição `repor-coletor` | acusa `repor-coletor` × `trocar-coletor` | — |

A primeira linha mostra por que as duas comparações existem: o comportamento
só revela o erro quando a instância exercita aquela parte da regra; a
estrutura revela sempre.

```bash
python -m testes.equivalencia          # relatório completo (cerca de 3 min)
python -m unittest discover testes     # inclui uma versão rápida (cerca de 20 s)
```

---

## Etapas

1. [x] Compilador do domínio para os modelos A, B e C.
2. [x] Geração dos fatos do problema a partir das regras, sobre o problema
       que o Ciclo 2 gera para o domínio legal.
3. [x] Validação com mensagens em português.
4. [x] Teste de equivalência da higienização.
5. [x] Assistente interativo que gera o TOML.
6. [x] Modelos D e E e teste de equivalência completo.
7. [x] Comando `planejar` (seleção, rota, regras, plano e roteiro) e texto
       legível das ações novas no roteiro do ACS, sem alterar o `acsplan`.
8. [ ] Avaliação com regras que não existem no domínio estendido:
   1. [ ] Extensões: `quantidade` no consumo (um procedimento pode gastar
          mais de uma unidade) e exigência por paciente num procedimento
          (ex.: luvas só na glicemia de gestantes).
   2. [ ] Planilha de avaliação: cópia da planilha de exemplo com as colunas
          `exige_avental` e `suspeita_tuberculose`.
   3. [ ] Sete regras novas, todas sintéticas: luvas na glicemia; desinfetar
          o termômetro antes da temperatura; zerar a balança uma vez no turno;
          avental para acamados; N95 para suspeita de tuberculose; luvas só na
          glicemia de gestantes; um procedimento gastando 2 unidades de um
          estoque que outro gasta 1.
   4. [ ] Medições: se compila, se o roteiro mostra a tarefa certa, linhas de
          TOML × linhas de PDDL geradas, quanto o turno cresce, e tempo de
          planejamento com 0, 3, 5 e 8 regras ativas.
   5. [ ] Teste com alguém que não programa: escrever 2 ou 3 regras pelo
          assistente, medindo tempo e erros.

## Em aberto

- **Usuário-alvo:** quem vai escrever as regras (enfermeiro, coordenação da
  UBS, gestão municipal)? Define o tom das perguntas e das mensagens.

## Trabalhos futuros

Duas classes de regra ficam fora deste ciclo. Nenhuma é impossível em PDDL;
o que muda é o custo de implementar:

- **Alternativas** ("higienizar as mãos *ou* usar luvas"). Em STRIPS, o "ou"
  vira uma versão da ação para cada alternativa, como o Ciclo 2 já faz com as
  três variantes de `iniciar-visita`. O custo é duplicar o procedimento no
  domínio, e as cópias se multiplicam quando várias alternativas se combinam.
- **Horário do dia** ("visitar gestantes pela manhã"). O planejador do Ciclo 2
  aceita STRIPS com custos, e o custo acumulado não pode ser usado como
  condição. Caminhos possíveis: um planejador temporal (PDDL 2.1/2.2, com
  ações com duração e janelas de tempo); um relógio discreto no domínio, em
  blocos de tempo, ao custo de um espaço de busca muito maior; ou tratar a
  regra como ordem ("gestantes antes dos demais"), que o domínio sabe
  verificar (como a urgência) mas que precisa ser produzida pelo
  roteirizador, já que a rota chega pronta ao planejador.

## Como usar

### Escrevendo as regras pelo assistente

Dentro desta pasta:

```bash
python -m compilador.assistente minhas-regras.toml
```

O assistente pergunta o que adicionar (recurso, preparo, consumo ou
exigência) e depois cada campo, com explicação. Um trecho da conversa:

```
Novo RECURSO: um estoque finito que só é reposto na UBS (ex.: álcool, máscaras).
Nome do recurso: Álcool Gel
  Nomes precisam ser em minúsculas, sem acento nem espaço. Usar "alcool-gel"? [S/n]: s
Quantas unidades o ACS leva por carga: seis
  ! digite um número inteiro. Recebido: "seis"
Quantas unidades o ACS leva por carga: 4
Quantos minutos leva para repor na UBS [3]:
```

- Cada resposta é validada na hora; uma resposta inválida faz a mesma pergunta
  de novo. Nomes já usados pelo domínio ou por outra regra são recusados
  quando digitados.
- Para recurso, preparo e exigência, o assistente pergunta também o texto que
  aparece no roteiro do ACS; Enter aceita o nome da regra.
- Recursos, preparos e procedimentos são escolhidos por número, numa lista
  com o nome legível de cada procedimento. Consumo e exigência só podem ser
  criados depois do recurso ou preparo a que se referem.
- As três regras sintéticas do Ciclo 2 podem ser recriadas inteiras só
  respondendo perguntas; um teste automático confere que o resultado é igual
  a `exemplos/sinteticas-ciclo2.toml`.
- Se o arquivo já existe, as regras novas são **acrescentadas ao fim**, sem
  apagar o que estava lá (inclusive comentários).
- No fim, as regras passam pela conferência do compilador antes de serem
  gravadas, e os avisos são mostrados. Ctrl+C cancela sem gravar nada.

O arquivo gravado é um TOML comum, com um comentário explicando cada campo, e
pode ser editado à mão depois.

### Planejando o turno e gerando o roteiro do ACS

```bash
python -m compilador planejar exemplos/sinteticas-ciclo2.toml --orcamento 240
```

Faz o mesmo que o `acsplan roteiro` do Ciclo 2, com as regras aplicadas:
seleciona quem entra no turno, define a rota, compila as regras, planeja e
imprime o roteiro. Sem arquivo de regras, usa só o domínio legal. Um trecho,
com uma instância que tem pacientes que exigem máscara
(`--instancia-sintetica 4 2`):

```
  1. Paciente 03  (adulto)
     início aprox.: 18 min de turno
     [ ] Acionar o enfermeiro da equipe (acompanhamento obrigatório)
     [ ] Colocar máscara de proteção respiratória
     [ ] Conferir a proteção antes de entrar
     [ ] Higienizar as mãos
     [ ] Aferir pressão arterial
     [ ] Aferir temperatura axilar
     [ ] Encaminhar o paciente à unidade de referência
     [ ] Registrar a visita no sistema
```

O texto das tarefas novas vem do campo `texto` de cada regra. O roteiro é
adaptado do roteiro do Ciclo 2, mas fica em `compilador/roteiro.py`, porque o
original tem os textos fixos no código e não mostraria ações criadas por
regras novas. Os minutos vêm do custo de cada ação do plano, então o total bate
com o custo do plano.

Com a planilha de exemplo e `--orcamento 240`, o roteiro sai igual ao do
`acsplan roteiro --dominio estendido` do Ciclo 2: as mesmas 6 visitas, na mesma
ordem, com 262 minutos e o mesmo alerta de orçamento.

| Opção | Padrão | O que faz |
|---|---|---|
| `--dados` | planilha de exemplo | pacientes em `.csv` ou `.json`, no formato do Ciclo 2 |
| `--instancia-sintetica N SEMENTE` | — | microárea sorteada, em vez da planilha |
| `--orcamento MIN`, `--max-pacientes`, `--sem-selecao` | — | seleção de quem entra no turno |
| `--metodo`, `--distancias`, `--modal`, `--semente`, `--sem-precedencia` | como no Ciclo 2 | roteirização |
| `--estrategia` | `astar-hadd` | busca: `astar-hmax` (ótimo, mais lento), `astar-hadd` ou `gbfs` |
| `--limite S` | 60 | limite de tempo da busca |
| `--salvar ARQUIVO` | — | grava o roteiro em vez de imprimir |
| `--salvar-pddl PASTA` | — | grava o domínio e o problema compilados |
| `--mostrar-plano` | — | lista o plano completo, ação por ação |

O resumo de cada passo vai para a saída de erro e o roteiro para a saída
padrão, então `... > roteiro.txt` grava só o roteiro. Quando não há roteiro, a
mensagem diferencia o turno **provadamente** impossível (nenhuma sequência de
ações cumpre as regras) da busca que só parou no limite de tempo, o que não
prova nada.

O assistente também pode ser chamado como `python -m compilador assistente`.

### Compilando

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

Preparos e consumos não acrescentam nada: o estado do preparo começa falso
(no PDDL, o que não está no estado inicial é falso), e o consumo usa o estoque
do recurso. O problema também passa a apontar para o domínio compilado
(`visita-domiciliar-acs-regras`, ou o nome dado em `--nome`).

Exigências precisam saber **quem tem a marca**, e isso vem da planilha de
pacientes do Ciclo 2 (`.csv` ou `.json`), em `--dados`. A marca
`exige-protecao-respiratoria` é lida da coluna `exige_protecao_respiratoria`:

```bash
python -m compilador exemplos/sinteticas-ciclo2.toml -o dominio.pddl \
    --problema problema-legal.pddl --saida-problema problema.pddl \
    --dados acsplan/dados/microarea_exemplo.csv
```

Cada paciente marcado vira um fato `(exige-protecao-respiratoria pX)`. Sem
`--dados`, o compilador recusa o problema e explica o que falta.

Quem usa o pipeline do Ciclo 2 em Python pode chamar
`compilador.gerar_problema_com_regras(dados, roteamento, regras, caminho,
nome_dominio=...)`, que gera o problema legal e aplica as regras de uma vez.

## Estrutura

```
compilador/
  regras.py      modelos, leitura e escrita do TOML, conferência de cada campo
  assistente.py  assistente interativo que grava o TOML
  dominio.py     aplica os modelos sobre a árvore do domínio
  problema.py    acrescenta ao problema os fatos que as regras exigem (recursos, marcas)
  pddl.py        escreve a árvore (domínio ou problema) como PDDL legível
  ciclo2.py      caminhos e acesso à cópia do Ciclo 2 (acsplan/)
  planejar.py    comando planejar: turno inteiro com as regras
  roteiro.py     roteiro do ACS, com os textos das regras
  __main__.py    linha de comando
acsplan/         cópia parcial, sem alterações, do pacote do Ciclo 2 (ver LEIAME.md)
exemplos/
  higienizacao.toml       regra sintética da higienização, como no Ciclo 2
  sinteticas-ciclo2.toml  as três regras sintéticas, com os cinco modelos
testes/
  test_compilador.py    leitura, validação, avisos, domínio e problema
  equivalencia.py       comparações com o estendido (também roda sozinho)
  test_equivalencia.py  equivalência parcial e completa, controle negativo
  test_assistente.py    sessões do assistente com respostas programadas
  test_planejar.py      roteiro e comando planejar
```

Para rodar os testes, dentro desta pasta:

```bash
python -m unittest discover testes
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
O Ciclo 2 pedia 3.10+; o requisito sobe por causa do TOML. Nenhuma dependência
externa, e nenhuma dependência da pasta `PCI-Saude-GroupB`: todos os testes
passam com esta pasta copiada sozinha para outro lugar.
