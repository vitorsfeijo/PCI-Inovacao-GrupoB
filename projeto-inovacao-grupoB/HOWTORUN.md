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
instalado.

| Comando | O que faz | Tempo |
|---|---|---|
| `python acs.py equivalencia` | regras sintéticas compiladas × domínio estendido do Ciclo 2 | ~3 min |
| `python acs.py medicoes` | medições da avaliação; grava [`exemplos/avaliacao/resultados.md`](exemplos/avaliacao/resultados.md) (`--rapido` para conferir) | ~25 min |
| `python acs.py qualidade` | qualidade dos planos: configurações do FD × janelas (precisa do FD; `--rapido`) | ~40 min |
| `python acs.py roteiros ROTEIRO PLANILHA r1 ...` | confere um roteiro contra o esperado de cada regra da avaliação | segundos |
| `python acs.py conferir-teste SESSAO.toml --tarefa t1` | confere uma regra do teste com usuário contra o gabarito | segundos |

O teste com usuários tem protocolo próprio:
[`exemplos/avaliacao/teste-usuario/PROTOCOLO.md`](exemplos/avaliacao/teste-usuario/PROTOCOLO.md).
