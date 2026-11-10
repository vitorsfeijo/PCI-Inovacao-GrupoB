# Roteiro de fala — aproximadamente 10 minutos

São 13 slides organizados em **Problema → Solução → Na prática → Resultados → Próximos passos**, com o mesmo design do pitch da semana 1. Ajustem os tempos depois de um ensaio. As ressalvas e as fontes ficam aqui no roteiro, e não em notas pequenas na projeção.

| Slide | Duração | Tempo acumulado |
| --- | --- | --- |
| 1. Capa | 20 s | 0:20 |
| 2. Depois do pitch | 50 s | 1:10 |
| 3. O problema | 30 s | 1:40 |
| 4. … vira isto em PDDL | 1 min | 2:40 |
| 5. A solução | 1 min 10 s | 3:50 |
| 6. Cinco modelos fixos | 1 min 10 s | 5:00 |
| 7. Escrevendo uma regra | 50 s | 5:50 |
| 8. Conferido enquanto se digita | 40 s | 6:30 |
| 9. O roteiro e a rota | 50 s | 7:20 |
| 10. O roteiro pode ser impresso | 20 s | 7:40 |
| 11. O que medimos | 1 min 10 s | 8:50 |
| 12. Limites e próximos passos | 50 s | 9:40 |
| 13. Créditos | 20 s | 10:00 |

## 1. Capa

“Na semana passada mostramos o planejador de visitas do ACS que herdamos do Grupo B do ciclo anterior. Hoje mostramos a inovação que escolhemos depois daquela conversa: deixar a própria equipe escrever as regras do planejamento, sem precisar programar.”

## 2. Depois do pitch

“O planejador já faz duas coisas importantes: monta o roteiro respeitando a lei e os materiais, e aceita regras novas sem mudar o código. Mas cada equipe tem regras próprias, e uma regra nova é escrita em PDDL, uma linguagem de planejamento.”

**Condução:** se houver tempo, citar com as palavras de vocês o que ouviram no pitch e que levou a essa escolha.

## 3. O problema

“Um exemplo. A regra da higienização cabe numa frase: higienizar as mãos antes dos procedimentos, gastando uma dose de álcool que só é reposta na unidade.”

**Condução:** deixar a frase na tela por um instante; ela é simples de propósito, para contrastar com o slide seguinte.

**Ressalva:** a regra é sintética, a mesma do domínio estendido do Ciclo 2. Não é norma. Os procedimentos são pressão, glicemia, temperatura, medicação e antropometria.

## 4. … vira isto em PDDL

“Para o planejador entender essa frase, alguém precisa escrever isto. À esquerda, uma ação nova: higienizar as mãos, gastando uma dose de álcool. À direita, uma das ações que já existiam, aferir a pressão: a regra acrescenta a linha destacada, ‘mãos higienizadas’, entre as condições. E isso se repete em mais seis ações, além de uma ação para repor o álcool, três predicados novos e fatos no problema. Quem escreve isso à mão precisa conhecer o domínio inteiro.”

**Fonte:** trechos reais do domínio gerado por `python3 acs.py compilar exemplos/higienizacao.toml` (pasta `projeto-inovacao-grupoB`), só com as linhas quebradas para caber no slide; o PDDL não depende de espaços nem de quebras de linha. As 7 ações alteradas são `mover` e `desviar-para-ubs` (sair da casa desfaz a higienização) e os cinco procedimentos que passam a exigi-la; o domínio legal tem 16 ações.

## 5. A solução

“A solução tem quatro passos, e embaixo de cada um está o exemplo da higienização. A equipe descreve a regra na interface web, num formulário. Isso vira um arquivo de regras legível, o `regras.toml`, que fica salvo. O compilador transforma o arquivo em PDDL, como o trecho do slide anterior. E o planejador monta o roteiro, já com a higienização como tarefa.

Dois pontos importantes. O compilador não usa inteligência artificial: a mesma regra gera sempre o mesmo PDDL, então dá para conferir o resultado. E a base é a lei: o planejador do ciclo anterior já tem as normas da Lei 11.350/2006, e as regras da equipe só acrescentam exigências por cima. Elas podem deixar o turno mais exigente, mas não podem afrouxar a lei.”

**Fonte:** o domínio legal do Ciclo 2 (`backend/acsplan/logica/dominios/dominio-legal.pddl`) contém só regras com base na Lei 11.350/2006, art. 3º (redação da Lei 13.595/2018), com o dispositivo comentado em cada ação. O compilador só acrescenta precondições, efeitos, ações e predicados, e recusa nomes que já existem no domínio (`compilador/dominio.py`).

## 6. Cinco modelos fixos

“São cinco modelos. Recurso: um estoque, como o álcool, reposto na unidade. Preparo: algo que o ACS faz antes, como higienizar as mãos. Pré-requisito: o preparo vem antes de certos procedimentos. Consumo: um procedimento gasta unidades de um recurso. E exigência por paciente: quem tem uma marca na planilha, como suspeita de tuberculose, exige um preparo, como a máscara N95.

É pouco expressivo de propósito: o que não cabe nos modelos fica de fora, em vez de virar um PDDL que ninguém consegue conferir.”

**Fonte:** exemplos da tabela do `projeto-inovacao-grupoB/README.md`. Todos sintéticos.

## 7. Escrevendo uma regra

“É assim que se escreve uma regra na interface. Cada modelo tem o seu formulário. Este é o preparo de higienizar as mãos: o recurso que ele gasta, se sair da casa desfaz o preparo, e antes de quais procedimentos ele é exigido, marcados numa lista.”

**Fonte:** captura da interface (`python3 acs.py web`, aba Regras), com o exemplo “sinteticas-ciclo2” aberto.

## 8. Conferido enquanto se digita

“Cada campo é conferido enquanto se digita. Aqui alguém escreveu ‘Luvas de procedimento’ como nome, com espaço e maiúscula. O formulário explica o erro e oferece a correção com um clique. Com tudo válido, a equipe baixa o arquivo de regras.”

## 9. O roteiro e a rota

“O que o ACS recebe continua sendo o roteiro: cada visita com o horário de chegada e as tarefas para marcar. A regra da higienização já aparece como tarefa, sem que ninguém precise lembrar. À direita, a rota no mapa, com a passagem pela unidade para repor material tracejada.”

**Fonte:** capturas da aba Planejar e da aba Mapa, com as regras `exemplos/sinteticas-ciclo2.toml` e 5 pacientes da planilha de avaliação, início às 08:00. 

**Ressalva:** as linhas do mapa são retas, como as distâncias que o planejador usa; o caminho pelas ruas pode ser outro. O mapa de ruas é do OpenStreetMap (a atribuição aparece no canto da captura). Sem internet, a interface mostra um desenho simples com os mesmos pontos.

## 10. O roteiro pode ser impresso

“E o roteiro pode ser impresso: uma folha por turno, com caixas para marcar cada tarefa.”

**Fonte:** primeira página do PDF que o navegador gera ao imprimir o roteiro (botão “Imprimir” da aba Planejar), com o mesmo exemplo do slide anterior.

## 11. O que medimos

“Três números. Mais curto: sete regras novas custaram de 7 a 18 linhas no arquivo de regras, contra 13 a 60 linhas de PDDL alteradas. Barato para o turno: cada regra sozinha soma de 1 a 9 minutos a um turno ótimo de 386. E escala: com as sete regras e 10 pacientes, o roteiro sai em cerca de 30 segundos com o Fast Downward, enquanto o planejador do ciclo anterior não termina.”

**Fonte:** `projeto-inovacao-grupoB/DESIGN.md`, seção “Avaliação”, e `exemplos/avaliacao/resultados.md`. Os cerca de 30 s são com o Fast Downward e o planejamento por janelas, que não garante o ótimo. O Fast Downward é opcional; sem ele, o sistema usa o planejador do Ciclo 2.

**Se perguntarem se o compilador está certo:** as três regras do ciclo anterior, escritas como modelos, reproduzem o domínio que o outro grupo escreveu à mão, com a mesma estrutura e o mesmo resultado em 24 de 24 instâncias (`DESIGN.md`, “Equivalência com o domínio estendido do Ciclo 2”).

**Ressalva:** regras e pacientes são sintéticos. “1 a 9 minutos” é cada regra sozinha, no plano ótimo.

## 12. Limites e próximos passos

“Duas classes de regra ainda ficam fora dos modelos. Uma é a de alternativas, como higienizar as mãos ou usar luvas. A outra é a de horário do dia, como visitar gestantes pela manhã. Nenhuma é impossível em PDDL, mas as duas custam mais para implementar e ficaram para depois.

O próximo passo é o teste com pessoas que não programam: ver se conseguem escrever uma regra sozinhas, usando a interface.”

**Fonte:** `projeto-inovacao-grupoB/DESIGN.md`, “Em aberto e trabalhos futuros”. Material do teste com usuários em `exemplos/avaliacao/teste-usuario/`.

## 13. Encerramento e créditos

“Obrigado. O planejador original é do Grupo B do Ciclo 2; o compilador e a interface são deste ciclo.”
