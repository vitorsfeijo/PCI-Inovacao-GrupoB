# Roteiro de fala — aproximadamente 10 minutos

São 11 slides organizados em **Problema → Solução → Exemplos → Próximos passos**. Os professores pediram que o problema e a solução ficassem claros, então os slides 2 a 4 precisam ser apresentados sem pressa. Ajustem os tempos depois de um ensaio. As ressalvas ficam aqui no roteiro, e não em notas pequenas na projeção. A versão anterior (9 slides) está em `versao-anterior/`.

| Slide | Duração | Tempo acumulado |
| --- | --- | --- |
| 1. Capa | 20 s | 0:20 |
| 2. Um turno de visitas do ACS | 1 min 15 s | 1:35 |
| 3. O problema | 1 min 15 s | 2:50 |
| 4. A solução proposta | 1 min | 3:50 |
| 5. O que o ACS recebe | 1 min 15 s | 5:05 |
| 6. Como o roteiro é montado | 1 min | 6:05 |
| 7. Exemplo: volta à unidade | 1 min | 7:05 |
| 8. Quando mudar a ordem não resolve | 1 min | 8:05 |
| 9. Regras da equipe | 45 s | 8:50 |
| 10. O que queremos aprender | 50 s | 9:40 |
| 11. Créditos | 20 s | 10:00 |

## 1. Capa

“Somos o Grupo B deste ciclo. Vamos continuar o projeto que o Grupo B do ciclo anterior desenvolveu: um assistente para organizar o turno de visitas domiciliares do agente comunitário de saúde. Hoje queremos mostrar qual problema ele tenta resolver e como, e principalmente ouvir de vocês se esse problema é real.”

## 2. Um turno de visitas do ACS

“Imaginem um turno de quatro horas. Na lista há uma pessoa idosa que precisa de aferição de pressão e glicemia capilar, uma criança para pesar, medir e conferir a caderneta de vacinação e um adulto com visita em atraso.

Antes de sair, o agente precisa decidir três coisas: quem visitar primeiro, o que levar (e se o material dá para todas as visitas), e quem precisa ir junto, e em qual momento.”

**Condução:** deixar as três perguntas da direita no ar por um instante. O público deve se reconhecer na cena antes de qualquer técnica.

**Ressalva:** o cenário é ilustrativo e foi baseado nos perfis do exemplo simulado do projeto (pessoa idosa, criança e adulto). Não é um caso real.

**Gancho legal (o slide sobre a lei foi retirado):** se fizer sentido, comentar oralmente que, pela Lei 11.350/2006, art. 3º, § 4º, aferir pressão e medir glicemia capilar só são atribuição do ACS com curso técnico, equipamento disponível e assistência de profissional de nível superior da equipe. É isso que faz o “quem precisa ir junto” importar.

## 3. O problema

“Resumindo numa frase: organizar o turno não é só escolher a rota. Cada visita depende de prioridade, material e acompanhamento, e o que acontece numa casa afeta as seguintes.

O slide mostra só essa frase; os exemplos ficam na fala. Quando isso é feito de cabeça, imaginamos que podem acontecer coisas como: sair sem fitas suficientes e ter de voltar à unidade, chegar para um procedimento sem o profissional que precisa acompanhar, ou uma visita prioritária ficar para o fim do turno.

São hipóteses nossas. Queremos confirmar com vocês se isso acontece na prática.”

**Condução:** ler a frase do problema devagar. É a frase que os professores pediram para ficar clara. Dizer explicitamente que as consequências são hipóteses.

## 4. A solução proposta

“A solução proposta é um assistente que monta o roteiro do turno. Ou seja: quem visitar, em que ordem, o que levar e o que fazer em cada casa, respeitando prioridades, materiais e acompanhamento profissional.

Ele recebe três tipos de informação: as famílias com suas prioridades e atrasos, os materiais e equipamentos, e a formação do agente junto com a agenda da equipe. E devolve um roteiro.”

**Condução:** o slide mostra só “um assistente que monta o roteiro do turno”; o detalhamento vem na fala e deve espelhar a frase do problema do slide anterior.

## 5. O que o ACS recebe

“Este é o resultado, num exemplo simulado gerado pelo protótipo. À esquerda estão duas paradas: uma pessoa idosa, com acionamento do enfermeiro, pressão e glicemia capilar, e uma criança, com peso, altura e vacinação. Cada item é para marcar quando for feito.

À direita está o resumo: seis visitas, com 266 minutos estimados para 240 disponíveis. O sistema avisa que o turno não cabe. Em vez de esconder o problema, ele mostra o problema para a equipe decidir.”

**Fonte dos valores:** PCI-Saude-GroupB/apresentacao/3/roteiro-do-turno.txt. No slide, a segunda parada mostrada é a da criança (Paciente 06), que na saída original é a parada 3; a parada 2 original (Paciente 03, com reposição de fitas) foi omitida para simplificar. As tarefas foram abreviadas (por exemplo, “Pressão” no lugar de “Aferir pressão arterial”), e os números não foram alterados. “Registrar a visita no sistema” é uma tarefa listada na saída e não indica integração com nenhum sistema assistencial.

**Ressalva:** não é medição em campo. O roteiro ainda precisaria de revisão da equipe antes de ser usado.

## 6. Como o roteiro é montado

“Por dentro, são quatro etapas. O sistema seleciona as visitas pela prioridade, propõe uma ordem das casas, confere se cada procedimento é possível naquela ordem, considerando material, formação e enfermeiro, e entrega o roteiro. Se a ordem não funciona, ele tenta outra.”

**Se perguntarem pela implementação:** o roteirizador propõe a ordem e o planejador lógico (PDDL) confere as ações. A opção `--realimentar` liga as duas etapas. Há limites de tempo e de tentativas, então não encontrar um plano não prova que nenhuma alternativa funcione.

## 7. Exemplo: a volta à unidade entra no plano

“Três visitas com glicemia capilar, e cada uma usa uma fita. O agente sai com uma só. Depois da visita A, sobra zero. O roteiro inclui a volta à unidade para repor antes da visita B, em vez de o agente descobrir o problema na porta da casa.”

**Condução:** acompanhar o estoque 1 → 0 → 2 → 1 → 0.

**Ressalva:** as quantidades são didáticas e não são normativas. O exemplo deixa de lado outras condições, como enfermeiro e tempo.

## 8. Quando mudar a ordem não resolve, o sistema diz por quê

“Nem tudo se resolve trocando a ordem. Se uma visita prioritária ficou para depois, outra ordem resolve. Mas se o agente não tem os requisitos para a visita, como o curso técnico ou o glicosímetro para medir glicemia, nenhuma ordem resolve: falta uma condição, e o sistema diz isso. O mesmo vale quando há mais visitas no mesmo horário do que enfermeiros no turno para acompanhá-las. O sistema não inventa recursos. Ele aponta o limite, e a decisão volta para a equipe.”

**Ressalva:** realimentacao.py verifica antes falta de habilitação ou equipamento e insuficiência das janelas de supervisão. São diagnósticos específicos, não uma explicação de qualquer falha possível.

## 9. As regras da equipe podem entrar no plano

“O grupo do ciclo anterior testou acrescentar regras de exemplo ao planejamento: álcool em gel, que é consumido e reposto; máscaras para visitas sinalizadas; e um coletor de descarte com capacidade limitada. O roteiro passou a respeitá-las. Uma quarta regra poderia ser a caixa térmica das vacinas, que tem tempo limitado fora da unidade. São regras criadas para teste, não normas. Quais regras da rotina de vocês estão faltando aqui?”

**Condução:** o slide mostra só os quatro quadros; o contexto e a pergunta ficam na fala.

**Ressalva:** Higienização, Proteção e Descarte são os três protocolos sintéticos do dominio-estendido.pddl; o E10 mostra a adaptação sem mudar o código de busca, mas não mostra ganho clínico nem de tempo. **Vacinas é um exemplo apenas ilustrativo, que não foi modelado nem testado**: não dizer que o sistema já trata essa regra. Incluir uma regra ainda exige trabalho de modelagem.

## 10. O que queremos aprender com vocês

“Para fechar, três perguntas. Como o turno de visitas é organizado hoje? O que mais atrapalha uma visita planejada? E o que tornaria um roteiro como esse útil de verdade? É a partir desta conversa que vamos definir a nossa inovação neste ciclo.”

**Condução:** deixar este slide projetado durante a conversa. Anotar as situações, como a equipe resolve hoje e o que indicaria que uma melhoria foi útil. Não pedir nomes nem dados identificáveis de pacientes.

## 11. Encerramento e créditos

“O projeto original é do Grupo B do Ciclo 2. Nós, o Grupo B do Ciclo 3, vamos levá-lo adiante. Obrigado!”

Créditos completos: projeto original de Gabriel Pieruccini Knopp, Arthur Andrade da Silva e Izadora Candotti de Oliveira. Apresentação e próximo ciclo por Luis Henrique Caselani Macedo Junior, Manuela Cristina Zen Dalmonte e Vítor Santana Feijó.

## Base factual e rastreabilidade

Caminhos relativos à raiz do repositório.

| Conteúdo | Fonte interna |
| --- | --- |
| Lei 11.350/2006, art. 3º § 4º, e modelagem das condições | PCI-Saude-GroupB/projeto/PROJETO-CICLO2.md |
| Seleção, prioridade, atraso | PCI-Saude-GroupB/acsplan/selecao/politica.py |
| Condições, consumo e reposição | PCI-Saude-GroupB/acsplan/logica/dominios/dominio-legal.pddl |
| Regras hipotéticas | PCI-Saude-GroupB/acsplan/logica/dominios/dominio-estendido.pddl |
| Outras rotas e diagnósticos | PCI-Saude-GroupB/acsplan/logica/realimentacao.py e cli.py |
| Novas regras e limites da evidência | PCI-Saude-GroupB/docs/05-analise-e-conclusoes.md (E7, E9, E10) |
| Exemplo de saída (slides 2 e 5) | PCI-Saude-GroupB/apresentacao/3/roteiro-do-turno.txt |

As consequências citadas na fala do slide 3 são hipóteses a validar com os stakeholders, não achados. Os exemplos das figuras são didáticos.
