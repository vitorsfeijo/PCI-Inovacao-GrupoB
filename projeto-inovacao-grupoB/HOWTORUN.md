# Como rodar

Instruções para instalar, escrever regras, planejar o turno e rodar os
testes. Para a ideia geral, veja o [README](README.md); para a arquitetura e
as decisões de implementação, o [DESIGN](DESIGN.md).

Todos os comandos usam o lançador **`acs.py`**, nesta pasta
(`projeto-inovacao-grupoB`); o código fica em `backend/`.
`python3 acs.py --help` lista os comandos.

## Requisitos

**Python 3.11 ou superior** (a leitura de TOML usa o `tomllib`, da biblioteca
padrão). Nenhuma dependência obrigatória, e nenhuma dependência da pasta
`PCI-Saude-GroupB`: a parte do Ciclo 2 que o projeto usa está copiada em
`backend/acsplan/`.

**O comando do Python muda conforme o sistema.** Os comandos deste guia
estão escritos com `python`:

| Sistema | Comando | Exemplo |
|---|---|---|
| Linux / macOS | `python3` | `python3 acs.py assistente minhas-regras.toml` |
| Windows | `python` ou `py` | `python acs.py assistente minhas-regras.toml` |

### Fast Downward (opcional, recomendado)

Sem ele, tudo funciona com o planejador do Ciclo 2, que não dá conta de
turnos com muitas regras (veja o [DESIGN](DESIGN.md#avaliação)). Com ele, o
comando `planejar` passa a usá-lo sozinho. Tem versões já compiladas para
Windows, Linux e macOS.

No **Windows** (e no macOS, se o `pip` estiver disponível):

```bash
python -m pip install -r requirements-opcional.txt      # up-fast-downward
```

No **Linux**, distribuições recentes bloqueiam o `pip install` no Python do
sistema (erro *externally-managed-environment*). O caminho é um ambiente
virtual, criado uma vez dentro desta pasta (a pasta `.venv` é ignorada pelo
git):

```bash
python3 -m venv .venv                                   # cria o ambiente
source .venv/bin/activate                               # ativa (em cada terminal novo)
python -m pip install -r requirements-opcional.txt     # instala o Fast Downward
```

Com o ambiente ativado, `python` passa a ser o Python dele, e os comandos
deste guia funcionam como estão escritos. Sem ativar, usem o caminho direto:
`.venv/bin/python acs.py planejar ...`.

---

## Interface web

```bash
python acs.py web
```

Abre o navegador em `http://localhost:8000` (se a porta estiver ocupada, usa
a seguinte). A interface roda **só neste computador**: o servidor não aceita
conexões de outras máquinas, e os dados dos pacientes não saem dele. A única
coisa buscada na internet são as imagens das ruas no mapa (OpenStreetMap);
sem internet, o mapa vira um desenho simples. Ctrl+C no terminal encerra.
Opções: `--porta N` e `--sem-navegador`.

São quatro abas: **Regras**, **Planejar**, **Antes × depois** e **Mapa**.

**Regras.** Cada modelo (recurso, preparo, consumo,
exigência) tem um botão "+ Adicionar"; o formulário ao lado explica cada
campo e confere enquanto vocês digitam. Nome com acento ou espaço ganha uma
sugestão ("Usar “alcool-gel”"); renomear um recurso ou preparo atualiza as
regras que o usam; os problemas aparecem no campo, no cartão da regra e numa
lista embaixo. Com tudo válido, o selo fica verde e "Baixar regras.toml"
salva o arquivo, que serve para o `planejar` do terminal. Também dá para
abrir um `.toml` existente ou um dos exemplos. O que estiver na tela fica
guardado no navegador até clicar em "Novo".

**Planejar.** Escolham as regras (as da tela Regras,
quando válidas, ou só as normas da lei), os pacientes (uma planilha de
exemplo, a planilha da equipe em `.csv` ou pacientes inventados para testar)
e o turno (horário de início, duração e máximo de pacientes, todos
opcionais). "Planejar o turno" mostra o andamento com as mesmas mensagens do
terminal e, no fim, o roteiro: visitas em ordem com horário estimado de
chegada, a lista de tarefas de cada uma, as passagens pela UBS para repor
material e quem ficou para outro turno. "Imprimir" imprime só o roteiro;
"Baixar (.txt)" salva o mesmo texto do terminal; "Ver no mapa" abre a
rota na aba Mapa. As opções avançadas
(estratégia, planejador, rota) são as mesmas do `planejar`.

**Antes × depois.** Planeja o mesmo turno duas vezes, com os mesmos
pacientes e a mesma rota: só com as normas da lei e com as regras da equipe.
As regras vêm da aba Regras e os pacientes e o turno, da aba Planejar. Mostra
a diferença de duração, de tarefas e de voltas à UBS; o que as regras
acrescentaram ("Higienizar as mãos: 5 vezes"); e, visita a visita, as tarefas
novas destacadas e o atraso na chegada. "Mostrar só as tarefas que mudaram"
esconde o resto.

**Mapa.** A rota do último roteiro planejado: a UBS, as visitas numeradas na
ordem, as passagens pela UBS para repor material (tracejadas) e, em cinza,
quem ficou para outro turno. Clicar numa visita (no mapa ou na lista) mostra
o horário de chegada e as tarefas. O mapa de ruas usa o OpenStreetMap; o
"Desenho simples" mostra os mesmos pontos sem internet, e a tela troca para
ele sozinha se as imagens das ruas não carregarem. As linhas são retas, como
as distâncias que o planejador usa; o caminho pelas ruas pode ser outro.

A API está descrita no [DESIGN](DESIGN.md#servidor-e-api-da-interface-web).

## Escrevendo regras pelo assistente

```bash
python acs.py assistente minhas-regras.toml
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
- Se o arquivo já existe, as regras novas são **acrescentadas ao fim**, sem
  apagar o que estava lá (inclusive comentários).
- No fim, as regras passam pela conferência do compilador antes de serem
  gravadas, e os avisos são mostrados. Ctrl+C cancela sem gravar nada.
- Com `--registro sessao.jsonl`, ele grava cada pergunta, resposta e recusa
  com o horário (usado no teste com usuários).

O arquivo gravado é um TOML comum, com um comentário explicando cada campo, e
pode ser editado à mão depois.

## Escrevendo regras à mão

O arquivo de regras é um TOML com um bloco por regra. Exemplos prontos:
[`exemplos/higienizacao.toml`](exemplos/higienizacao.toml) (só a
higienização) e [`exemplos/sinteticas-ciclo2.toml`](exemplos/sinteticas-ciclo2.toml)
(as três regras sintéticas do Ciclo 2, com os cinco modelos).

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

O pré-requisito (modelo C) é o campo `exigido_antes_de` do preparo, porque
sempre se refere a um preparo.

### Campos

| Modelo | Campo | Obrigatório | Significado |
|---|---|---|---|
| recurso | `nome` | sim | nome do estoque; vira o predicado de nível |
| recurso | `capacidade` | sim | unidades por carga (≥ 1) |
| recurso | `custo_reposicao` | sim | minutos para repor na UBS (≥ 0) |
| recurso | `acao_reposicao` | não | nome da ação de reposição (padrão `repor-<nome>`) |
| recurso | `texto` | não | o que repor, como aparece no roteiro do ACS (padrão: o nome) |
| preparo | `nome` | sim | nome da ação que o ACS executa |
| preparo | `estado` | sim | condição que passa a valer depois do preparo |
| preparo | `custo` | sim | minutos (≥ 0) |
| preparo | `consome` | não | recurso gasto a cada execução |
| preparo | `desfeito_ao_sair` | não | se sair da casa desfaz o estado (padrão `true`) |
| preparo | `exigido_antes_de` | não | procedimentos que só acontecem com o estado valendo |
| preparo | `texto` | não | a tarefa, como aparece no roteiro (padrão: o nome, ex. "Higienizar maos") |
| consumo | `procedimento` | sim | procedimento que gasta o recurso |
| consumo | `recurso` | sim | recurso gasto a cada execução |
| consumo | `quantidade` | não | unidades gastas a cada execução (padrão 1; não pode passar da capacidade) |
| exigencia | `nome` | sim | nome da conferência; gera `<nome>-conferida`, `conferir-<nome>-exigida` e `conferir-<nome>-dispensada` |
| exigencia | `marca` | sim | marca do paciente; vem da coluna de mesmo nome da planilha, com `_` no lugar de `-` |
| exigencia | `preparo` | sim | preparo cujo estado é exigido |
| exigencia | `antes_de` | não | procedimentos em que o preparo é exigido desses pacientes; sem ele, vale o início da visita |
| exigencia | `custo` | não | minutos da conferência na porta (padrão 1); não se aplica com `antes_de` |
| exigencia | `texto` | não | a conferência, como aparece no roteiro (padrão: "Conferir <nome> antes de entrar"); não se aplica com `antes_de` |

**Exigência antes de um procedimento.** Por exemplo, luvas só na glicemia de
gestantes (a planilha precisa da coluna `gestante`, com sim/não):

```toml
[[exigencia]]
nome = "luvas-gestante"
marca = "gestante"
preparo = "calcar-luvas"
antes_de = ["glicemia"]
```

### Nomes e procedimentos

Os nomes seguem a regra do PDDL: minúsculas, sem acento nem espaço, com hífen
entre as palavras. O `texto` é o único campo em que acentos e espaços são
livres, porque não entra no PDDL, só no roteiro.

Os procedimentos aceitos formam uma lista fechada:

| Nome na regra | Procedimento | Ação no domínio |
|---|---|---|
| `pressao` | aferir pressão arterial | `aferir-pressao-arterial` |
| `glicemia` | medir glicemia capilar | `medir-glicemia-capilar` |
| `temperatura` | aferir temperatura axilar | `aferir-temperatura-axilar` |
| `medicacao` | orientar a administração de medicação | `orientar-administracao-medicacao` |
| `antropometria` | verificação antropométrica (peso e altura) | `verificacao-antropometrica` |
| `vacinal` | verificar a caderneta de vacinação | `verificar-caderneta-vacinal` |

### Conferindo um arquivo de regras

```bash
python acs.py compilar minhas-regras.toml -o /dev/null   # só confere (Windows: -o NUL)
```

Erros aparecem todos de uma vez, em português, com o campo e o valor aceito.
Avisos (regras válidas que provavelmente não fazem o esperado) não impedem a
compilação.

---

## Planejando o turno e gerando o roteiro do ACS

```bash
python acs.py planejar exemplos/sinteticas-ciclo2.toml --orcamento 240
```

Seleciona quem entra no turno, define a rota, compila as regras, planeja e
imprime o roteiro, como o `acsplan roteiro` do Ciclo 2, com as regras
aplicadas. Sem arquivo de regras, usa só o domínio legal. Um trecho, com uma
instância que tem pacientes que exigem máscara (`--instancia-sintetica 4 2`):

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

| Opção | Padrão | O que faz |
|---|---|---|
| `--dados` | planilha de exemplo | pacientes em `.csv` ou `.json`, no formato do Ciclo 2 |
| `--instancia-sintetica N SEMENTE` | — | microárea sorteada, em vez da planilha |
| `--orcamento MIN`, `--max-pacientes`, `--sem-selecao` | — | seleção de quem entra no turno |
| `--metodo`, `--distancias`, `--modal`, `--semente`, `--sem-precedencia` | como no Ciclo 2 | roteirização |
| `--planejador` | `auto` | `auto` (Fast Downward se instalado, senão o do Ciclo 2), `fast-downward` ou `ciclo2` |
| `--estrategia` | `auto` | `auto` (ótimo se terminar em 1/4 do limite; senão, o melhor entre janelas e um plano global rápido), `janelas`, `astar-hmax` (só o ótimo), `astar-hadd` (plano bom) ou `gbfs` (primeiro plano) |
| `--janela K` | 3 com o FD, 1 sem | visitas enxergadas por janela |
| `--limite S` | 60 | limite de tempo da busca |
| `--salvar ARQUIVO` | — | grava o roteiro em vez de imprimir |
| `--salvar-pddl PASTA` | — | grava o domínio e o problema compilados |
| `--mostrar-plano` | — | lista o plano completo (já limpo), ação por ação |
| `--sem-limpeza` | — | não retira as ações redundantes do plano |

O resumo de cada passo vai para a saída de erro e o roteiro para a saída
padrão, então `... > roteiro.txt` grava só o roteiro. Quando não há roteiro, a
mensagem diferencia o turno **provadamente** impossível (nenhuma sequência de
ações cumpre as regras) da busca que só parou no limite de tempo, o que não
prova nada.

**Marcas de pacientes.** Regras com exigência leem quem tem cada marca da
planilha: a marca `exige-protecao-respiratoria` vem da coluna
`exige_protecao_respiratoria` (sim/não). Uma marca nova pede uma coluna nova;
se a coluna não existe, é erro.

## Compilando domínio e problema

Para usar os arquivos PDDL em outro planejador ou inspecioná-los:

```bash
# imprime o domínio compilado
python acs.py compilar exemplos/higienizacao.toml

# grava em arquivo
python acs.py compilar exemplos/higienizacao.toml -o dominio-com-regras.pddl

# outro domínio de entrada ou outro nome para o domínio gerado
python acs.py compilar regras.toml --dominio outro.pddl --nome meu-dominio
```

O problema parte de um problema gerado pelo Ciclo 2 **para o domínio legal**;
com exigências, precisa também dos dados dos pacientes:

```bash
python acs.py compilar exemplos/sinteticas-ciclo2.toml -o dominio.pddl \
    --problema problema-legal.pddl --saida-problema problema.pddl \
    --dados backend/acsplan/dados/microarea_exemplo.csv
```

O jeito mais simples de obter os dois arquivos de um turno é
`python acs.py planejar ... --salvar-pddl PASTA`.

Em Python (com `backend/` no caminho de importação),
`compilador.gerar_problema_com_regras(dados, roteamento, regras, caminho,
nome_dominio=...)` gera o problema legal e aplica as regras de uma vez.

---

## Testes e experimentos

```bash
python acs.py testes        # todos os testes (cerca de 1 min)
```

Os testes que dependem do Fast Downward são pulados quando ele não está
instalado. Os da interface web precisam do Node 22 ou mais novo (lógica da
tela) e do Chrome ou Chromium (teste de ponta a ponta, num navegador sem
janela) e também são pulados sem eles; outro navegador pode ser indicado com
`CHROME=chromium python acs.py testes`. Só a lógica da tela:
`node --test web/testes/*.test.mjs`.

| Comando | O que faz | Tempo |
|---|---|---|
| `python acs.py equivalencia` | regras sintéticas compiladas × domínio estendido do Ciclo 2 | ~3 min |
| `python acs.py medicoes` | medições da avaliação; grava [`exemplos/avaliacao/resultados.md`](exemplos/avaliacao/resultados.md) (`--rapido` para conferir) | ~25 min |
| `python acs.py qualidade` | qualidade dos planos: configurações do FD × janelas (precisa do FD; `--rapido`) | ~40 min |
| `python acs.py roteiros ROTEIRO PLANILHA r1 ...` | confere um roteiro contra o esperado de cada regra da avaliação | segundos |
| `python acs.py conferir-teste SESSAO.toml --tarefa t1` | confere uma regra do teste com usuário contra o gabarito | segundos |

O teste com usuários tem protocolo próprio:
[`exemplos/avaliacao/teste-usuario/PROTOCOLO.md`](exemplos/avaliacao/teste-usuario/PROTOCOLO.md).
