# Desenho, decisões e avaliação

Como o compilador de regras funciona por dentro, por que foi feito assim, e
o que a avaliação mostrou. Para a ideia geral, veja o [README](README.md);
para instalar e rodar, o [HOWTORUN](HOWTORUN.md).

1. [Arquitetura](#arquitetura)
2. [Decisões de implementação](#decisões-de-implementação)
3. [Avaliação](#avaliação)
4. [Limitações e observações](#limitações-e-observações)
5. [Etapas](#etapas)
6. [Em aberto e trabalhos futuros](#em-aberto-e-trabalhos-futuros)
7. [Estrutura dos arquivos](#estrutura-dos-arquivos)

---

## Arquitetura

```
regras.toml ──► compilador ──► domínio PDDL (legal + regras)
(assistente       │
 ou à mão)        └──────────► problema PDDL (problema legal do Ciclo 2 + fatos das regras)

planejar:  planilha ─► [1] seleção ─► [2] rota ─► [3] regras compiladas
                       (Ciclo 2)      (Ciclo 2)        │
                                                       ▼
           roteiro ◄─ [6] roteiro ◄─ [5] limpeza ◄─ [4] busca
           do ACS        (nosso)                     (Ciclo 2 ou Fast Downward;
                                                      ótimo, janelas ou global)
```

O sistema do Ciclo 2 tem quatro camadas: **seleção** (quem entra no turno),
**roteirização** (a ordem das visitas, por distância, com urgência alta antes
da baixa), **planejamento PDDL** (o que fazer em cada casa e quando passar na
UBS) e **roteiro** (o que o ACS recebe). O planejador recebe a rota congelada
e não pode mudá-la.

O compilador entra entre a rota e o planejamento: ele gera o domínio e o
problema com as regras da equipe. Tudo o que é novo fica em `backend/compilador/`;
o Ciclo 2 é usado como está.

---

## Decisões de implementação

### Modelos fixos, compilação determinística, sem LLM

Acrescentar uma regra ao domínio do Ciclo 2 exige saber PDDL, e uma regra que
se explica em uma frase espalha mudanças: a regra sintética da máscara ocupa
cerca de 35 linhas no `dominio-estendido.pddl`, em predicados, três ações
novas, efeitos nas ações de deslocamento, precondições nas três variantes de
início de visita, e ainda em trechos do gerador de problema e do carregador
da planilha.

A equipe descreve a regra preenchendo **modelos fixos**, e o compilador a
transforma em PDDL de forma determinística. Sem LLM: o mesmo arquivo de
regras sempre gera o mesmo domínio, e o erro aparece num formulário legível,
não em PDDL. A expressividade fica limitada aos modelos, de propósito; o que
não cabe neles continua exigindo PDDL escrito à mão.

O **assistente** pergunta campo a campo e grava um TOML; o **compilador** só
conhece o TOML. Isso mantém o compilador simples de testar, e a regra fica
salva, versionável e editável à mão.

### Os cinco modelos

Os modelos saíram da comparação entre o `dominio-legal.pddl` e o
`dominio-estendido.pddl` do Ciclo 2: o estendido é exatamente o legal
acrescido das três regras sintéticas, e cada uma se decompõe nestas peças.

| Modelo | Significado | O que gera no PDDL |
|---|---|---|
| **A. Recurso** R | estoque de R, com capacidade N, reposto só na UBS | predicados `(R ?n)` e `(nivel-maximo-R ?n)`; ação `repor-R` (ou o nome dado) que, na UBS, leva o estoque ao máximo |
| **B. Preparo** Y, estado E | o ACS faz Y, podendo gastar R; sair da casa desfaz E | predicado `(E ?ag)`; ação Y que torna E verdadeiro (e gasta uma unidade, se consome); `(not (E ?ag))` em `mover` e `desviar-para-ubs` |
| **C. Pré-requisito** | os procedimentos P1, P2… exigem E antes | precondição `(E ?ag)` nessas ações |
| **D. Consumo** de k unidades de R por P | o procedimento P gasta k unidades | parâmetros `?R ?R-1 … ?R-k` em P; precondições `(R ?R)` e a cadeia `(prox ?R-1 ?R) …`; efeitos `(not (R ?R))` e `(R ?R-k)` |
| **E. Exigência** X: marca M exige Y | na porta: pacientes com M só iniciam a visita com o estado de Y | predicados `(M ?p)` e `(X-conferida ?ag ?p)`; ações `conferir-X-exigida` (com M, exige o estado) e `conferir-X-dispensada` (sem M, custo 0); precondição de conferência nas três variantes de `iniciar-visita` |
| | com `antes_de`: os procedimentos listados exigem Y nesses pacientes | cada procedimento se divide em duas versões (ver abaixo) |

Como as regras sintéticas do Ciclo 2 se escrevem com eles:

| Regra sintética | Modelos |
|---|---|
| Higienização das mãos | A (álcool) + B (higienizar, consome álcool) + C (procedimentos do § 4º) |
| Proteção respiratória | A (máscaras) + B (vestir, consome máscara) + E (marca "exige proteção") |
| Coletor de perfurocortante | A (coletor) + D (glicemia consome coletor) |

A, B e C vieram primeiro (suficientes para a higienização); D e E
completaram as outras duas regras. Na avaliação, D e E ganharam um campo
opcional cada, sem virar modelos novos, porque continuam expressando a mesma
ideia: `quantidade` no consumo e `antes_de` na exigência.

**`quantidade` (D).** Gastar k unidades é descer k níveis do estoque, com uma
cadeia de `prox`. Só usa STRIPS: o planejador do Ciclo 2 não tem números.
Quantidade acima da capacidade é erro (o procedimento nunca poderia ser
feito).

**`antes_de` (E): por que duplicar o procedimento.** Reaproveitar a
conferência da porta teria uma brecha: o ACS "conferiria as luvas", iria à
UBS repor fitas (sair desfaz as luvas), voltaria e faria a glicemia sem
luvas, porque a conferência antiga continuaria valendo. Por isso o
procedimento se divide em duas versões: a original, só para quem **não** tem
a marca, e `<procedimento>-<exigência>`, que exige a marca e o estado do
preparo **no momento** do procedimento. É a mesma técnica que o Ciclo 2 usa
nas três variantes de `iniciar-visita`. Com k exigências no mesmo
procedimento surgem 2^k versões; as versões são criadas por último, para
herdar os pré-requisitos e consumos já aplicados ao procedimento.

**Nomes.** O `estado` do preparo tem nome próprio porque não dá para derivá-lo
do nome da ação em português (`higienizar-maos` → `maos-higienizadas`). Os
procedimentos são uma lista fechada, ligada às ações do domínio legal, para
que ninguém precise conhecer os nomes internos do PDDL.

### Domínio legal somente leitura, pasta autocontida

O `dominio-legal.pddl` é **somente lido, nunca alterado**: as normas ficam
travadas e as regras da equipe são aplicadas por cima. O mesmo vale para o
código do Ciclo 2: o gerador de problema dele continua gerando o problema do
domínio legal, e o compilador acrescenta o que as regras exigem.

Para a pasta funcionar sozinha, o que o compilador usa do Ciclo 2 (domínios,
parser e planejador, gerador de problema, roteirizador, seleção de pacientes
e planilha de exemplo) está copiado em `backend/acsplan/`, **sem nenhuma
alteração**. O [`backend/acsplan/LEIAME.md`](backend/acsplan/LEIAME.md) lista o que foi copiado, o que
ficou de fora e como conferir que a cópia continua idêntica ao original.
Todos os testes passam com esta pasta copiada sozinha para outro lugar.

### Problema compilado sobre o problema legal

Para cada recurso de capacidade N, o problema ganha `(R nN)` e
`(nivel-maximo-R nN)` (o turno começa com o estoque cheio) e, quando N passa
do maior nível existente, objetos `n…` e fatos `(prox …)` a mais. Preparos e
consumos não acrescentam fatos: o estado do preparo começa falso (no PDDL, o
que não está no estado inicial é falso). Cada paciente marcado vira um fato
`(M pX)`, e o problema passa a apontar para o domínio compilado.

**Colunas da planilha.** O leitor de CSV do Ciclo 2 **descarta** colunas que
não conhece; uma coluna nova como `gestante` sumiria em silêncio, e a regra
deixaria de valer sem nenhum erro. O compilador relê da planilha as colunas
usadas pelas exigências, sem alterar a cópia do Ciclo 2, e uma marca sem
coluna correspondente é erro, não "ninguém marcado": quase sempre é um nome
digitado errado.

### Validação

O compilador recusa regras malformadas com **mensagens em português** que
dizem o que está errado e qual é o valor aceito, e relata **todos os
problemas de uma vez**:

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

| Nível | O que confere | Onde |
|---|---|---|
| Campo | formato, tipo e faixa de cada valor; campos que faltam ou não existem | `regras.py`, funções `validar_*` |
| Regras entre si | nomes repetidos (inclusive derivados), referência a recurso ou preparo inexistente, quantidade acima da capacidade | `regras.py`, `ler_regras` |
| Regras e domínio | nome (ou nome derivado, como `repor-alcool`) já usado pelo domínio | `dominio.py` |

Erros de formato do TOML aparecem com linha e coluna. Os validadores de campo
devolvem a mensagem ou nada, para o assistente reaproveitá-los campo a campo.
Há também **avisos**, que não impedem a compilação: recurso que nada consome,
preparo que nada exige, preparo exigido que não é desfeito ao sair (basta uma
vez no turno), arquivo sem regras.

### Roteiro próprio

O roteiro do Ciclo 2 tem os textos fixos no código e não mostraria ações
criadas por regras novas; por isso o roteiro fica em `backend/compilador/roteiro.py`,
adaptado do original. O texto de cada tarefa nova vem do campo `texto` da
regra (o único com acentos e espaços livres, porque não entra no PDDL). As
versões de procedimento criadas por `antes_de` aparecem com o texto do
procedimento original. Os minutos vêm do custo de cada ação do plano, então o
total bate com o custo do plano.

Cada preparo criado por regra aparece na visita em que é **usado**, e não na
próxima visita qualquer: um preparo que vale o turno todo (zerar a balança)
pode ser feito pelo planejador a qualquer momento antes do uso, e apareceria
na visita de quem nem é pesado.

Com a planilha de exemplo, `--orcamento 240` e o mesmo modo de busca
(`--estrategia astar-hadd --sem-limpeza`), o roteiro sai igual ao do
`acsplan roteiro --dominio estendido` do Ciclo 2: as mesmas 6 visitas, na
mesma ordem, com 262 minutos e o mesmo alerta de orçamento.

### Instanciação com poda

O planejador do Ciclo 2 instancia cada ação gerando **todas** as combinações
de objetos para os parâmetros (`itertools.product`) e só depois descarta as
que violam uma precondição fixa, como `(prox ?n-1 ?n)`. Cada recurso gasto
numa ação acrescenta parâmetros do tipo nível e multiplica as combinações:
com as sete regras da avaliação, eram 4,7 bilhões.

`backend/compilador/instanciacao.py` liga os parâmetros um a um, **na mesma ordem**,
e testa cada precondição fixa assim que todas as suas variáveis estão
ligadas; como `(prox ?n-1 ?n)` determina `?n-1` a partir de `?n`, cada
recurso deixa de multiplicar por 11. O resultado é **idêntico** ao original
(mesmas ações, mesma ordem, mesmos identificadores de fatos), o que os testes
conferem em cinco casos; com as sete regras, 9.449 ações em 0,2 s. É uma
subclasse que troca só esse método; a cópia do Ciclo 2 não muda.

### Fast Downward opcional

O planejador do Ciclo 2 (Python puro, heurísticas `h_max` e `h_add`) não
escala com muitas regras. O Fast Downward, planejador de referência da área,
é usado **se estiver instalado** (pacote `up-fast-downward`, com versões já
compiladas para Windows, Linux e macOS); senão, tudo funciona com o do
Ciclo 2. `backend/compilador/fastdownward.py` só **localiza** o executável do pacote
(importá-lo exigiria o framework Unified Planning, que não usamos), roda-o
sobre os mesmos arquivos PDDL, e **valida o plano devolvido na tarefa do
nosso planejador** antes de seguir. Os códigos de saída distinguem "provou
que não há plano" de "parou no limite".

### Servidor e API da interface web

`python3 acs.py web` sobe um servidor local que serve a interface (pasta
`web/`) e uma API em JSON (`backend/servidor/`). Escolhas:

- **Só biblioteca padrão** (`http.server`), para manter zero dependências
  obrigatórias; a interface é HTML, CSS e JavaScript simples, sem etapa de
  *build*.
- **Só neste computador:** o servidor ouve em `127.0.0.1` e recusa
  requisições cujo cabeçalho `Host` não seja local, o que impede um site
  aberto no mesmo navegador de usar a API (*DNS rebinding*). A planilha tem
  dados de pacientes.
- **Nada é gravado** fora de pastas temporárias: salvar regras é um download
  feito pelo navegador.
- **Uma fonte só da verdade:** os formulários são montados a partir de
  `GET /api/modelos`, que lê as descrições e os **tipos de campo** do próprio
  `regras.py`; a validação usa os mesmos validadores do assistente e do
  compilador.
- **O mesmo núcleo do terminal:** o `planejar` foi dividido em `executar`
  (devolve um resultado estruturado: seleção, rota com coordenadas, visitas,
  tarefas, minutos, resumo) e `main` (imprime). A API traduz o pedido para os
  mesmos argumentos da linha de comando e usa o mesmo analisador, então opções
  inválidas são recusadas do mesmo jeito.
- **Planejamento em segundo plano:** planejar pode levar até um minuto, então
  `POST /api/planejar` cria uma tarefa e a interface acompanha
  `GET /api/tarefas/<id>`, com as mesmas mensagens de progresso do terminal.
  No máximo dois planejamentos rodam ao mesmo tempo.

| Rota | O que faz |
|---|---|
| `GET /api/modelos` | modelos, campos (tipo, obrigatório, descrição) e procedimentos |
| `GET /api/exemplos`, `GET /api/exemplos/regras/<id>` | regras e planilhas de exemplo |
| `POST /api/regras/campo` | valida um campo `{modelo, campo, valor}`; devolve o erro e, para nomes, uma sugestão |
| `POST /api/regras/validar` | valida o conjunto `{regras}`, inclusive contra o domínio; devolve problemas, avisos e o TOML |
| `POST /api/regras/ler` | lê um TOML `{toml}` para os formulários |
| `POST /api/planejar` | `{regras_toml, planilha: {exemplo \| csv \| sintetica}, opcoes}` → `{id}` |
| `GET /api/tarefas/<id>` | estado, mensagens de progresso e, no fim, o resultado |

### Estratégia de busca: `auto`, janelas e limpeza

| Estratégia | Ciclo 2 | Fast Downward |
|---|---|---|
| só o ótimo (`astar-hmax`) | A\* com `h_max` | A\* com LM-cut |
| plano bom (`astar-hadd`) | A\* com `h_add` | LAMA |
| primeiro plano (`gbfs`) | busca gulosa | LAMA, 1º plano |
| `janelas` | `h_max` por janela (`h_add` se o tempo acabar) | LM-cut por janela (LAMA se o tempo acabar) |

**`auto` (padrão).** Tenta o ótimo em 1/4 do limite; turnos pequenos param
aí, com garantia. Se não terminar, calcula o plano **por janelas** e um
**plano global rápido**, e fica com o melhor plano válido depois da limpeza.
Se a busca ótima *provar* que o turno é impossível, não há segunda tentativa.

**Janelas** (`backend/compilador/janelas.py`). A ordem das visitas já vem pronta, e
um turno com poucos pacientes tem plano ótimo em segundos. A partir do estado
atual (estoques, equipamento vestido, janelas de supervisão), planeja-se de
forma ótima o atendimento das próximas k visitas; executa-se só até concluir
a primeira; a janela avança uma casa. Olhar k visitas à frente evita a miopia
de planejar uma casa por vez (por exemplo, repor dois materiais numa mesma
passagem pela UBS). Cada plano de janela passa pela limpeza antes de ser
executado. k = 3 com o Fast Downward e k = 1 sem ele.

**Por que não só janelas: o beco sem saída.** As janelas de supervisão não se
repõem (uma por visita na planilha), e um desvio à UBS no meio de uma visita
encerra a supervisão e obriga a acionar de novo. Sem o Fast Downward (k = 1),
as sete regras gastaram as janelas cedo demais e a última visita ficou sem
supervisão. Por isso o `auto` sempre calcula também o plano global.

**Limpeza** (`backend/compilador/limpeza.py`). Eliminação de ações redundantes
(*action elimination*; Fink e Yang, 1992; Nakhost e Müller, 2010): para cada
ação, tenta-se retirá-la junto com as seguintes que deixam de ser aplicáveis
sem ela; se o resto ainda atinge o objetivo, a retirada vale. O plano só
perde ações, então continua válido e nunca fica mais caro.

**Por que não `h_add` como padrão.** Foi o padrão por um tempo e fazia turnos
11% mais longos que o ótimo sem nenhuma regra, e até 35% com exigências na
porta, vestindo equipamento em quem não precisava e indo à UBS repor sem
necessidade.

---

## Avaliação

### Equivalência com o domínio estendido do Ciclo 2

As regras sintéticas, escritas como modelos e compiladas sobre o domínio
legal, precisam reproduzir o `dominio-estendido.pddl` escrito à mão pelo
Grupo B do Ciclo 2 (`python3 acs.py equivalencia`). Duas comparações:

1. **Estrutura:** mesmos predicados e, em cada ação, os mesmos parâmetros,
   precondições, efeitos e custo, aceitando troca de nomes entre variáveis
   do mesmo tipo (o compilador gera `?coletor` onde o domínio escrito à mão
   usa `?c`).
2. **Comportamento:** em cada instância, o custo ótimo é o mesmo nos dois
   lados, e o plano de cada um, executado no outro, é válido e tem o mesmo
   custo.

**Completa (modelos A a E).** As três regras sintéticas
([`exemplos/sinteticas-ciclo2.toml`](exemplos/sinteticas-ciclo2.toml)) contra
o estendido **inteiro**, comparando os dois pipelines de ponta a ponta (Ciclo
2: estendido + problema do Ciclo 2; compilado: legal + regras + problema
legal com os fatos das regras). **Estrutura igual, e 24 de 24 instâncias
equivalentes:**

| Instâncias | Recursos | O que exercitam |
|---|---|---|
| 2 e 3 pacientes, 5 sementes | capacidades padrão do Ciclo 2 | 3 instâncias com paciente que exige máscara |
| 2 e 3 pacientes, 5 sementes | 2 doses de álcool, 1 máscara, coletor com 2 posições | 5 planos com reposição ou troca na UBS |
| 4 pacientes, sementes 2 e 164 | padrão e 1 máscara por carga | 2 pacientes com máscara; com 1 máscara, reposição obrigatória |

As sementes 2 e 164 são as únicas do gerador do Ciclo 2 (testadas até 200)
com dois pacientes que exigem máscara.

**Parcial (higienização).** Antes de D e E existirem, a higienização foi
comparada com a **projeção** do estendido, sem máscara e coletor (remoção
mecânica, por nome de predicado). Estrutura igual, e 30 de 30 instâncias
equivalentes, 11 delas com reposição de álcool.

**Controle negativo.** Regras alteradas de propósito precisam ser acusadas:

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

A primeira linha mostra por que há duas comparações: o comportamento só
revela o erro quando a instância exercita aquela parte da regra; a estrutura
revela sempre.

### Regras novas e planilha de avaliação

Sete regras **sintéticas** que não existem no domínio estendido, em
[`exemplos/avaliacao/regras/`](exemplos/avaliacao/regras/): R1 lancetas na
glicemia; R2 desinfetar o termômetro antes da temperatura; R3 zerar a balança
uma vez no turno; R4 avental para acamados; R5 N95 para suspeita de
tuberculose; R6 luvas só na glicemia de gestantes; R7 algodão, 2 na glicemia
e 1 na temperatura. (A R1 seria "luvas em toda glicemia", mas contradizia a
R6 e virou lancetas.)

A planilha de avaliação ([`exemplos/avaliacao/`](exemplos/avaliacao/)) é a
planilha de exemplo do Ciclo 2 com as colunas `gestante` (p3),
`suspeita_tuberculose` (p7) e `exige_avental` (p6 e p8). Única alteração
clínica: p3 passa a fazer glicemia, para que a R6 seja exercitada
(documentado no JSON companheiro).

### Teste do roteiro: falhas encontradas

Cada regra foi planejada no turno completo da planilha de avaliação (10
pacientes), e o roteiro foi conferido contra o que cada regra deveria
produzir (`backend/testes/roteiros_avaliacao.py`). O teste revelou quatro falhas,
todas corrigidas:

| Falha | Causa | Correção |
|---|---|---|
| Regras combinadas não rodavam | instanciação do Ciclo 2: 4,7 bilhões de combinações com as sete regras | instanciação com poda |
| Turnos até 35% mais longos que o ótimo, com avental e N95 em quem não precisava | estratégia padrão `h_add` | padrão `auto` |
| Ações inúteis no plano (5 aventais para 2 acamados, 4 idas à UBS) | idem | limpeza: −10 ações e −81 min nesse caso |
| "Zerar a balança" na visita de quem não é pesado | o plano zera a qualquer momento antes do uso | o roteiro mostra cada preparo na visita em que é usado |

Com as correções, as sete regras passam na conferência, sozinhas e todas
juntas.

### Medições

Resultados completos em [`exemplos/avaliacao/resultados.md`](exemplos/avaliacao/resultados.md)
(`python3 acs.py medicoes`). Planilha de avaliação, 10 pacientes, mesma
rota. **Esforço e impacto de cada regra, sozinha** (turno ótimo sem regras:
386 min):

| Regra | TOML escrito | PDDL alterado | Turno ótimo | Δ |
|---|---|---|---|---|
| R1 lancetas | 8 linhas | 27 linhas | 389 min | +3 |
| R2 termômetro | 13 | 36 | 387 | +1 |
| R3 balança | 7 | 13 | 388 | +2 |
| R4 avental | 18 | 60 | 395 | +9 |
| R5 N95 | 18 | 60 | 389 | +3 |
| R6 luvas | 17 | 52 | 387 | +1 |
| R7 algodão | 12 | 41 | 389 | +3 |

1. **Escrever uma regra é muito mais curto que editar o PDDL:** cada linha de
   TOML vira, em média, 3,1 linhas de PDDL alteradas, espalhadas por até 9
   ações.
2. **No plano ótimo, cada regra custa pouco ao turno:** de 1 a 9 minutos.
3. **A instanciação com poda resolve o crescimento das combinações:** com as
   sete regras e as três do Ciclo 2, a original testaria 566 bilhões de
   combinações; a podada gera 90.545 ações em 1,8 s.
4. **Achar um plano deixa de ser problema com o Fast Downward:** plano em
   0,1 s em todos os casos, inclusive com as dez regras juntas. O
   planejador do Ciclo 2 não termina a partir de seis regras.
5. **Achar o plano ótimo continua difícil com muitas regras:** o LM-cut prova
   o ótimo até R1–R4 (401 min, 31 s) e não termina a partir de R1–R5; o
   primeiro plano do Fast Downward fica de 7% a 45% acima do ótimo.

**O planejador do Ciclo 2 não escala com muitas regras.** Com as sete regras,
por número de pacientes: < 1 s com 1; até 3,6 s com 2; até 23 s com 3; não
termina em 10 min com 5. Acrescentando as regras uma a uma (10 pacientes):
R1 0,6 s; R1–R4 6,5 s; R1–R5 35 s; seis ou mais, mais de 2 min. Não é
impossibilidade: todos os turnos pequenos têm plano, e nenhum par de regras
conflita. É o espaço de estados, em que estoques e equipamentos se combinam
ao longo das visitas.

**Fast Downward × Ciclo 2** (10 pacientes):

| Caso | Ótimo, `h_max` do Ciclo 2 | FD ótimo (LM-cut) | FD LAMA | FD 1º plano |
|---|---|---|---|---|
| sem regras | 386 min em 1,9 s | 386 em 0,2 s | 386 em 0,4 s | 412 em 0,1 s |
| R3 balança | 388 em 2,6 s | 388 em 0,3 s | 388 em 0,5 s | 414 |
| R4 avental | 395 em 9,3 s | 395 em 0,7 s | 395 em 1,7 s | 421 |
| R5 N95 | 389 em 13,3 s | 389 em 1,0 s | 389 em 2,6 s | 417 |
| sete regras | não termina | não termina em 5 min | 486 (não melhora em 60 s) | 486 em 0,02 s |

O modo ótimo do Fast Downward dá exatamente os ótimos do `h_max`, de 10 a 13
vezes mais rápido; com muitas regras, a diferença passa a ser "termina ×
não termina".

### Qualidade dos planos: janelas

Experimento `python3 acs.py qualidade` (com o Fast Downward; custos
depois da limpeza; limite de 60 s, 120 s para o ótimo):

| Caso | Ótimo | 1º plano FD | LAMA | Portfólio 2023 | Janelas k=1 | k=2 | **k=3** | k=4 |
|---|---|---|---|---|---|---|---|---|
| R1–R4, 10 pacientes | 401 (31 s) | 427 | 401 (33 s) | 406 | 409 (1 s) | 409 | **403 (0,9 s)** | 421 |
| 7 regras, p3 p6 p7 | 156 (1 s) | 179 | 156 (59 s) | 156 | 156 (0,3 s) | 156 | **156 (1 s)** | 156 |
| 7 regras, p6 p7 p8 | 199 (7 s) | 217 | 199 (14 s) | 200 | 199 (0,3 s) | 199 | **199 (7 s)** | 199 |
| 7 regras, 10 pacientes | não termina | 477 | 477 | 469 | 436 (1 s) | 436 | **430 (16 s)** | 428 (153 s) |

- No caso difícil, o turno cai de **477 para 430 min** (−10%); somando os
  acréscimos de cada regra sozinha, o ótimo estaria perto de 408.
- Onde o ótimo é conhecido, as janelas o alcançam ou ficam a 0,5% dele, em
  cerca de 1 s.
- k = 3 é o melhor equilíbrio: k = 4 melhora 2 minutos e leva dez vezes mais.

As medições da seção anterior são anteriores às janelas; com o `auto` atual
e o Fast Downward, o turno das sete regras sai com 430 min em ~30 s.

### Teste com usuários (material pronto, aplicação pendente)

Protocolo, tarefas e gabaritos em
[`exemplos/avaliacao/teste-usuario/`](exemplos/avaliacao/teste-usuario/): três
tarefas de dificuldade crescente (tablet; manguito; luvas para ferida
exposta), questionário e tabela de resultados. O assistente grava a sessão
(`--registro`), e `backend/testes/teste_usuario.py` confere cada regra contra o
gabarito **ignorando os nomes escolhidos**, e tira do registro o tempo e as
recusas.

---

## Limitações e observações

- **Falha herdada do Ciclo 2.** A ação `retornar-a-rota` (voltar da UBS para
  a casa) não desfaz nenhum estado: o planejador pode higienizar as mãos na
  UBS e chegar à casa ainda "higienizado"; o mesmo vale para a supervisão. O
  domínio estendido do Ciclo 2 tem exatamente esse comportamento, e o
  compilador o reproduz de propósito, para o teste de equivalência ser
  possível. Corrigir é decidir se `retornar-a-rota` também é uma ação de
  saída.
- **Sem o Fast Downward, muitas regras não planejam:** o planejador do Ciclo
  2 não termina a partir de seis regras no turno de 10 pacientes, e as
  janelas com k = 1 podem cair no beco sem saída da supervisão.
- **O ótimo com muitas regras é desconhecido:** com as sete regras e 10
  pacientes, nenhum dos quatro modos ótimos do Fast Downward termina em 5
  minutos; os 430 min das janelas estão, pela estimativa, a cerca de 5% do
  ótimo, mas isso não está provado.
- **Rota escolhida só pela distância:** o roteirizador do Ciclo 2 não enxerga
  as regras. Uma rota um pouco mais longa poderia dar um turno total mais
  curto (por exemplo, passando perto da UBS entre dois acamados com um
  avental por carga).

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
   1. [x] Extensões: `quantidade` no consumo e exigência por paciente num
          procedimento (`antes_de`).
   2. [x] Planilha de avaliação.
   3. [x] Sete regras novas, todas sintéticas.
   4. [x] Medições ([resultados](exemplos/avaliacao/resultados.md)), teste do
          roteiro e qualidade dos planos.
   5. [ ] Teste com alguém que não programa. **Material pronto, aplicação
          pendente** (pelo grupo).
9. [ ] Interface web:
   1. [x] Reorganização: `backend/` e o lançador `acs.py`.
   2. [x] Servidor local e API.
   3. [ ] Tela de regras.
   4. [ ] Tela de planejamento e roteiro.
   5. [ ] Antes × depois.
   6. [ ] Mapa da rota.

---

## Em aberto e trabalhos futuros

**Em aberto.** Quem vai escrever as regras (enfermeiro, coordenação da UBS,
gestão municipal)? Define o tom das perguntas e das mensagens.

**Escolher a rota pensando nas regras.** Gerar várias rotas candidatas (o
algoritmo genético faz isso mudando a semente), planejar o turno com as
regras em cada uma e ficar com o menor turno total. Com o Fast Downward e as
janelas, cada rota custa segundos.

**Duas classes de regra ficam fora deste ciclo.** Nenhuma é impossível em
PDDL; o que muda é o custo de implementar:

- **Alternativas** ("higienizar as mãos *ou* usar luvas"). Em STRIPS, o "ou"
  vira uma versão da ação para cada alternativa, como em `iniciar-visita`. O
  custo é duplicar o procedimento, e as cópias se multiplicam quando várias
  alternativas se combinam.
- **Horário do dia** ("visitar gestantes pela manhã"). O planejador aceita
  STRIPS com custos, e o custo acumulado não pode ser usado como condição.
  Caminhos: um planejador temporal (PDDL 2.1/2.2, com ações com duração e
  janelas de tempo); um relógio discreto no domínio, em blocos de tempo, ao
  custo de um espaço de busca muito maior; ou tratar a regra como ordem
  ("gestantes antes dos demais"), que o domínio sabe verificar (como a
  urgência) mas que precisa ser produzida pelo roteirizador.

---

## Estrutura dos arquivos

```
README.md                  ideia geral
HOWTORUN.md                instalar, escrever regras, planejar, testar
DESIGN.md                  este arquivo
acs.py                     ponto de entrada: python3 acs.py <comando>
requirements-opcional.txt  Fast Downward (opcional)
web/                       a interface (HTML, CSS e JavaScript, servidos pelo backend)
backend/
  compilador/
    regras.py        modelos, leitura e escrita do TOML, conferência de cada campo
    assistente.py    assistente interativo que grava o TOML
    dominio.py       aplica os modelos sobre a árvore do domínio
    problema.py      acrescenta ao problema os fatos das regras (recursos, marcas)
    pddl.py          escreve a árvore (domínio ou problema) como PDDL legível
    ciclo2.py        caminhos e acesso à cópia do Ciclo 2 (acsplan/)
    planejar.py      comando planejar: turno inteiro com as regras
    roteiro.py       roteiro do ACS, com os textos das regras
    instanciacao.py  instanciação com poda (resultado idêntico ao do Ciclo 2)
    limpeza.py       retira ações redundantes do plano
    fastdownward.py  Fast Downward opcional, com validação do plano
    janelas.py       planejamento por janelas
    __main__.py      linha de comando (chamada pelo acs.py)
  servidor/
    http.py          servidor local (python3 acs.py web)
    api.py           operações da API, como funções puras
    tarefas.py       planejamentos em segundo plano
  acsplan/           cópia parcial, sem alterações, do pacote do Ciclo 2 (ver LEIAME.md)
  testes/
    test_*.py              testes automáticos (python3 acs.py testes)
    equivalencia.py        comparações com o domínio estendido
    medicoes.py            medições da avaliação
    qualidade_planos.py    experimento de qualidade dos planos
    roteiros_avaliacao.py  confere um roteiro contra o esperado de cada regra
    teste_usuario.py       confere as regras do teste com usuário
exemplos/
  higienizacao.toml        regra sintética da higienização, como no Ciclo 2
  sinteticas-ciclo2.toml   as três regras sintéticas, com os cinco modelos
  avaliacao/               planilha, regras R1–R7, resultados e teste com usuário
```

O lançador `acs.py` põe `backend/` no caminho de importação e despacha cada
comando; de dentro de `backend/`, `python3 -m compilador ...` e
`python3 -m unittest discover testes` também funcionam.
