# Protocolo do teste com usuário (etapa 8.5)

**Pergunta:** alguém que não programa consegue escrever regras pelo
assistente, sem ajuda, e as regras saem certas?

**O que se mede, por tarefa:** se a regra saiu certa (conferida contra o
gabarito), o tempo, quantas respostas o assistente recusou e quantas vezes a
pessoa pediu ajuda. No fim, um questionário curto.

---

## Participantes

- Pessoas que **não programam**. O ideal é alguém da área da saúde (ACS,
  enfermagem, gestão da UBS); colegas de outros cursos também servem, e isso
  fica registrado.
- Três a cinco pessoas já mostram os problemas mais comuns.
- Ninguém do grupo, e ninguém que tenha visto o formato TOML ou o README.

**Consentimento:** explique que o teste avalia o **sistema**, não a pessoa;
que é anônimo (os arquivos levam só um código, como P1, P2); que nenhum dado
pessoal é coletado; e que ela pode parar quando quiser. Peça a concordância
verbal antes de começar.

## Preparação (antes de cada participante)

1. Um computador com Python 3.11 ou superior e esta pasta
   (`projeto-inovacao-grupoB`).
2. Uma pasta vazia para a sessão, por exemplo `sessoes/P1/`.
3. O arquivo [`TAREFAS.md`](TAREFAS.md) impresso ou aberto numa janela à parte.
4. O terminal aberto em `projeto-inovacao-grupoB`.

## Condução (cerca de 30 minutos)

1. **Introdução (2 min).** Leia: "Este programa planeja as visitas do agente
   comunitário. Vamos testar uma parte nova, em que a própria equipe ensina
   regras novas ao programa respondendo perguntas. Você vai fazer três
   tarefas. Pense em voz alta; eu só ajudo se você pedir."
2. **Uma tarefa por vez.** Para a tarefa 1, rode:

   ```bash
   python -m compilador assistente sessoes/P1/t1.toml --registro sessoes/P1/t1.jsonl
   ```

   Para as tarefas 2 e 3, troque `t1` por `t2` e `t3`. O `--registro` grava
   cada pergunta, resposta e recusa com o horário; não é preciso cronometrar.
3. **Durante a tarefa,** anote numa folha: cada **pedido de ajuda** (o que a
   pessoa perguntou e o que você respondeu) e as **hesitações** que ela
   verbalizar ("não sei o que é estado", "isso é minuto?").
4. **Ajuda:** só quando a pessoa pedir, e a mínima: repetir a pergunta do
   assistente com outras palavras. Nunca diga o valor a digitar.
5. **Não corrija** a regra ao final, mesmo que esteja errada: o erro é dado.
6. **Questionário (5 min)** depois das três tarefas.

## Conferência (depois da sessão)

Para cada tarefa:

```bash
python -m testes.teste_usuario sessoes/P1/t1.toml --tarefa t1 --registro sessoes/P1/t1.jsonl
```

O conferidor compara a regra com o gabarito ([`gabarito-t1.toml`](gabarito-t1.toml)
etc.), **ignorando os nomes** que a pessoa escolheu: só importam custos,
quantidades, quando vale e antes de que procedimento. Ele diz o que está
certo, o que está diferente, e tira do registro o tempo e as recusas.

## Questionário

Escala de 1 (discordo totalmente) a 5 (concordo totalmente):

1. Foi fácil entender o que cada pergunta pedia.
2. Eu saberia escrever uma regra nova sozinho(a), sem o aplicador por perto.
3. Tenho confiança de que as regras que escrevi fazem o que eu queria.
4. As mensagens de erro me ajudaram a corrigir a resposta.

Perguntas abertas:

5. Qual pergunta do assistente foi a mais confusa? Por quê?
6. Que regra da sua rotina (ou que você imagina) você não conseguiria
   escrever com essas perguntas?

## Tabela de resultados

Uma linha por participante e tarefa:

| Participante | Perfil | Tarefa | Certa? | Diferenças | Tempo | Recusas | Pedidos de ajuda | Observações |
|---|---|---|---|---|---|---|---|---|
| P1 | | T1 | | | | | | |
| P1 | | T2 | | | | | | |
| P1 | | T3 | | | | | | |

E uma linha por participante para o questionário (Q1 a Q4, e as respostas
abertas resumidas).

## O que levar para o relatório

- Taxa de acerto por tarefa (quantos fizeram certo), e os erros mais comuns.
- Tempo mediano por tarefa.
- As perguntas do assistente que mais geraram recusa, hesitação ou pedido
  de ajuda: elas são o ponto de melhoria mais concreto.
- As regras que as pessoas disseram não conseguir escrever: comparam-se com
  os trabalhos futuros (alternativas e horário).
