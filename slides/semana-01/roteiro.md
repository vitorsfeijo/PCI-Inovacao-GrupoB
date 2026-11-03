# Roteiro de fala — aproximadamente 10 minutos

Nove slides, com tempo para explicar os exemplos. As marcações somam 10 minutos e devem ser ajustadas após um ensaio; a conversa com os stakeholders acontece depois. As ressalvas ficam no roteiro, sem notas pequenas na projeção.

| Slide | Duração | Tempo acumulado |
| --- | --- | --- |
| 1. Apresentação | 30 s | 0:30 |
| 2. Prioridades | 1 min | 1:30 |
| 3. Regras e restrições | 1 min 15 s | 2:45 |
| 4. Construção do plano | 1 min 15 s | 4:00 |
| 5. Reposição de material | 1 min 30 s | 5:30 |
| 6. Impedimentos | 1 min 15 s | 6:45 |
| 7. Novas regras | 1 min 15 s | 8:00 |
| 8. Roteiro de trabalho | 1 min 30 s | 9:30 |
| 9. Encerramento | 30 s | 10:00 |

## 1. Planejamento de visitas domiciliares

“Somos o Grupo C e vamos trabalhar sobre um projeto desenvolvido pelo Grupo B no ciclo anterior. Ele propõe apoiar a organização das visitas domiciliares dos agentes comunitários de saúde. O foco desta apresentação é como o planejamento considera regras, condições para o atendimento e recursos disponíveis. Vamos mostrar o funcionamento e alguns exemplos do que o protótipo já faz. A partir da conversa com vocês, vamos definir onde inovar no próximo ciclo.”

## 2. Uma rota precisa respeitar as prioridades

“Imaginem que a equipe tenha definido que a visita A precisa acontecer antes da visita B. Os dois roteiros passam pelas mesmas casas e retornam à unidade. Mas, na primeira sequência, B aparece antes de A, contrariando a regra de prioridade. Na segunda, a ordem atende à orientação.

Esse exemplo mostra por que a organização de um turno precisa considerar mais do que os endereços. O sistema precisa saber quais decisões são aceitáveis para aquele conjunto de visitas. Uma sequência pode parecer adequada no mapa e ainda assim não cumprir uma condição importante. É essa ligação entre a rota e as regras do atendimento que o projeto procura representar.”

**Condução:** apontar A e B nas duas sequências. A condição “A antes de B” precisa ser explicitada na fala, pois essa frase foi retirada do slide.

**Ressalva:** exemplo fictício, sem cálculo de distância. Não dizer que a primeira rota é mais curta. A sequência de baixo atende à regra ilustrada, sem demonstrar a viabilidade integral de um atendimento. Não é uma recomendação clínica.

## 3. Regras e restrições do planejamento

“O projeto reúne três tipos de informação. Primeiro, as prioridades: quem está em atraso e quem deve ser visitado antes. Elas ajudam a selecionar as visitas e a organizar sua ordem.

Segundo, as condições necessárias para realizar as ações previstas. O modelo considera, por exemplo, habilitação, equipamento e assistência profissional. Uma ação só pode entrar no plano se suas condições forem atendidas.

Terceiro, os recursos disponíveis. Alguns materiais são consumidos, e a disponibilidade de assistência também é limitada no modelo. Por isso, uma decisão numa residência pode afetar o que será possível fazer nas seguintes. O planejamento acompanha essas mudanças ao construir a sequência de ações. Essa é uma diferença importante em relação a olhar cada visita isoladamente.”

**Ressalva:** são condições representadas pelo protótipo acadêmico. Regras e parâmetros precisam ser conferidos com a equipe antes do uso real. Quantidades de insumos e janelas de assistência são parâmetros escolhidos pelo projeto, não exigências normativas. Não interpretar o orçamento de tempo como garantia rígida: o slide 8 evidencia essa limitação.

## 4. Construção do plano de visitas

“O funcionamento pode ser acompanhado em quatro etapas. Primeiro, o sistema seleciona as visitas usando as informações disponíveis. Depois propõe uma ordem para percorrer as casas. A terceira etapa busca uma sequência de ações que permita realizar os atendimentos, considerando as regras e os recursos.

Quando aquela ordem não permite um plano, o projeto já tem uma opção de voltar à etapa anterior e tentar outra rota. É o retorno indicado pela seta no alto. Quando encontra um plano, transforma o resultado num roteiro com as paradas e o que fazer em cada uma.

Assim, o planejamento envolve tanto a ordem das visitas quanto as ações necessárias durante o turno. Nos próximos exemplos, vamos detalhar uma reposição de material e situações em que simplesmente mudar a ordem não resolve o problema.”

**Condução:** percorrer as quatro etapas e depois indicar a seta de retorno. As tentativas acontecem na preparação do plano; não apresentar isso como acompanhamento e replanejamento durante a execução real do turno.

**Se perguntarem pela implementação:** o roteirizador propõe a ordem; o planejador lógico trabalha sobre essa ordem. A opção --realimentar conecta as etapas. Não é uma busca única que garante a melhor rota global. Há limites de tempo e de tentativas: não encontrar um plano não prova que todas as alternativas sejam inviáveis.

## 5. A reposição de material faz parte do plano

“Neste exemplo, temos três visitas, A, B e C, e cada uma consome uma unidade de um material. O agente sai com apenas uma unidade. Depois da visita A, o estoque chega a zero. Se o roteiro apenas mandasse seguir para B, não haveria material para a ação prevista.

No modelo do projeto, existe a possibilidade de passar pela unidade para repor esse material. O planejamento pode incluir essa ação na sequência. Aqui, após a reposição, o estoque volta a duas unidades: uma será consumida em B e outra em C.

O ponto é que a passagem pela unidade deixa de ser apenas um endereço no mapa: ela tem uma função no plano, pois modifica os recursos disponíveis para as próximas visitas. O sistema precisa relacionar o consumo numa parada com as condições exigidas nas demais. Esse exemplo ajuda a visualizar por que planejar ações e recursos junto com a rota pode ser útil.”

**Condução:** acompanhar o estoque 1 → 0 → 2 → 1 → 0. Pausar em “zero” antes de indicar a reposição. O retorno final à unidade foi omitido do desenho para destacar essa parte do turno.

**Ressalva:** ilustração didática das ações de consumo e reposição já existentes. As quantidades não são resultado experimental nem regra clínica. O exemplo abstrai outras condições, como assistência, habilitação e tempo. Não afirmar que uma reposição torna qualquer turno viável ou que o protótipo sempre escolhe o melhor momento global para realizá-la.

## 6. Nem todo impedimento se resolve com outra rota

“A possibilidade de testar outras rotas não significa insistir em novas sequências para qualquer problema. O projeto diferencia algumas situações.

Se uma visita aparece antes de outra que deveria ter prioridade, mudar a ordem pode resolver aquele conflito. Já a falta de uma condição exigida para um atendimento não desaparece porque as casas foram reordenadas. O mesmo ocorre quando a disponibilidade de assistência considerada pelo modelo é insuficiente para as visitas previstas.

Nesses casos, o resultado indica uma limitação dos dados ou dos recursos fornecidos ao planejamento. Isso pode apoiar uma avaliação da equipe sobre o que precisa mudar. Rever recursos ou atendimentos é uma decisão operacional da equipe; o sistema não cria recursos nem deve escolher sozinho como contornar uma condição necessária.”

**Ressalva:** realimentacao.py verifica previamente falta de habilitação/equipamento e insuficiência das janelas de assistência para as visitas condicionadas. São diagnósticos específicos, não uma explicação completa de toda falha possível. Esgotar tentativas ou tempo de busca é diferente de comprovar impossibilidade. A revisão de recursos e atendimentos é uma consequência para discussão humana, não uma funcionalidade automática demonstrada.

## 7. Novas regras passam a fazer parte do planejamento

“Outra parte interessante foi testar o comportamento do sistema quando as regras mudam. O grupo criou uma versão experimental com três regras hipotéticas adicionais: consumo de solução alcoólica para higienização, disponibilidade de máscaras para determinadas visitas e capacidade limitada de um coletor, com troca na unidade.

Cada uma acrescenta uma condição ou um recurso que precisa ser acompanhado ao longo do turno. Não basta olhar a quantidade inicial: o planejamento precisa considerar o que será consumido e quando será necessária uma reposição.

Nos testes, o mecanismo de busca continuou o mesmo, mas passou a usar essas novas regras descritas no modelo. A possibilidade de incorporar condições diferentes é uma característica relevante para a continuidade do projeto. Isso ainda exige modelagem e avaliação técnica: não significa que qualquer regra possa ser cadastrada automaticamente ou que todas as regras da rotina já estejam representadas.”

**Ressalva:** os três protocolos são explicitamente sintéticos no projeto. Não apresentá-los como norma, recomendação assistencial ou configuração pronta para uso. O E10 sustenta a adaptação às novas regras sem alteração do código de busca. Não demonstra menor tempo de deslocamento, benefício clínico ou superioridade universal. Mais regras também aumentam a dificuldade da busca. A inovação do Grupo C ainda não está definida.

## 8. O resultado é um roteiro de trabalho

“A saída do projeto é uma lista de paradas com as tarefas de cada visita, os tempos estimados e indicações de reposição. Este é um exemplo simulado que o próprio grupo salvou. Ele contém seis visitas, com duração estimada de 266 minutos para um orçamento de 240 minutos. O sistema mostra um alerta de 26 minutos a mais.

Isso é importante para interpretar o resultado: produzir uma sequência de ações não significa que todos os limites operacionais estejam resolvidos. Esse roteiro ainda precisaria ser revisto pela equipe antes de ser usado. O exemplo não representa uma medição em campo.

À direita está um resumo da segunda parada, em que o roteiro indica passar na unidade antes da visita para repor material. A saída completa também organiza as tarefas por atendimento e o registro da visita. Assim, a equipe recebe algo que pode inspecionar e discutir. A adequação desse formato à rotina e a utilidade dos alertas são aspectos que ainda precisam de validação com profissionais.”

**Condução:** mostrar primeiro o resumo do turno, depois o excedente e, por último, o trecho da parada. O foco é a informação entregue ao agente.

**Fonte dos valores:** PCI-Saude-GroupB/apresentacao/3/roteiro-do-turno.txt: seis visitas, 266 minutos estimados, orçamento de 240 e excedente de 26. A segunda parada é “Paciente 03” e inclui reposição de fitas de glicemia. O slide resume a instrução para “material” e omite os procedimentos, sem modificar os números. “Registro da visita no sistema” é uma tarefa indicada na saída; não afirmar que o protótipo possui integração automática com um sistema assistencial.

## 9. Encerramento e créditos

“O projeto mostra como prioridades, condições e recursos podem participar da construção de um plano de visitas. Essa é a base que vamos aproveitar no próximo ciclo. O trabalho original é do Grupo B; nós, do Grupo C, vamos definir a inovação a partir do que aprendermos com vocês. Obrigado pela participação. Agora podemos conversar sobre como esses exemplos se aproximam, ou se afastam, da rotina de trabalho de vocês.”

Créditos completos: projeto original de Gabriel Pieruccini Knopp, Arthur Andrade da Silva e Izadora Candotti de Oliveira; apresentação e próximo ciclo por Luis Henrique Caselani Macedo Junior, Manuela Cristina Zen Dalmonte e Vítor Santana Feijó. Nos slides, os nomes estão abreviados.

## Conversa após a apresentação

Sem projetar um questionário, pedir exemplos de situações reais em que regras, prioridades ou recursos afetam a organização das visitas. Se necessário, retomar um exemplo apresentado. Anotar a situação, como a equipe resolve hoje e o que indicaria que uma melhoria foi útil. Não solicitar nomes ou dados identificáveis de pacientes. O objetivo é definir o recorte de inovação depois da escuta.

## Base factual e rastreabilidade

Caminhos relativos à raiz do repositório.

| Conteúdo | Fonte interna |
| --- | --- |
| Grupo apresentador e objetivo do ciclo | README.md |
| Autoria e estrutura do projeto-base | PCI-Saude-GroupB/README.md |
| Seleção, prioridade, atraso e estimativa de tempo | PCI-Saude-GroupB/acsplan/selecao/politica.py |
| Precedências | PCI-Saude-GroupB/acsplan/geo/roteirizador.py |
| Condições, consumo e reposição | PCI-Saude-GroupB/acsplan/logica/dominios/dominio-legal.pddl |
| Regras hipotéticas | PCI-Saude-GroupB/acsplan/logica/dominios/dominio-estendido.pddl |
| Outras rotas e diagnósticos | PCI-Saude-GroupB/acsplan/logica/realimentacao.py e cli.py |
| Novas regras e limites da evidência | PCI-Saude-GroupB/docs/05-analise-e-conclusoes.md, especialmente E7, E9 e E10 |
| Escopo e limites | PCI-Saude-GroupB/docs/06-veredito-sobre-planning.md |
| Saída em paradas, tarefas, reposições e alertas | PCI-Saude-GroupB/acsplan/saida/roteiro.py |
| Exemplo de saída do slide 8 | PCI-Saude-GroupB/apresentacao/3/roteiro-do-turno.txt |

As conclusões consolidadas foram priorizadas sobre as expectativas do documento inicial. Não foram transpostos números da apresentação visual de referência, que trata de outro trabalho. Os exemplos das figuras são didáticos, não medições experimentais. A inovação permanece aberta para definição após o encontro com os stakeholders.

