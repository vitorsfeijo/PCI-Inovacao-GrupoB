# Roteiro de fala — pré-apresentação (27/11)

São 16 slides, na ordem das seções do relatório técnico (`relatorio/main.tex`): **Onde estamos → Problema → Solução → Implementação → Experimentos → Resultados → Impacto → Conclusões → Próximos passos**. A duração da pré-apresentação não foi informada; os tempos abaixo supõem cerca de **12 minutos**. Para encurtar, o slide 2 e o slide 8 podem virar uma frase falada. As fontes e ressalvas ficam aqui, e não na projeção.

| Slide | Duração | Acumulado |
| --- | --- | --- |
| 1. Capa | 15 s | 0:15 |
| 2. A uma semana da entrega | 50 s | 1:05 |
| 3. O problema | 45 s | 1:50 |
| 4. A solução | 50 s | 2:40 |
| 5. Hipóteses e métricas | 1 min | 3:40 |
| 6. Sete modelos fixos | 1 min | 4:40 |
| 7. O que acontece por baixo | 1 min | 5:40 |
| 8. Como avaliamos | 45 s | 6:25 |
| 9. H1: o compilador está correto | 45 s | 7:10 |
| 10. H2: regras mais curtas que o PDDL | 45 s | 7:55 |
| 11. H3: o roteiro sai, mas o ótimo não escala | 1 min | 8:55 |
| 12. Extensões: ou, horários e tradução | 1 min 15 s | 10:10 |
| 13. Impacto e caminho até o uso | 45 s | 10:55 |
| 14. O que aprendemos | 50 s | 11:45 |
| 15. Até 04/12 | 40 s | 12:25 |
| 16. Créditos | 10 s | 12:35 |

## 1. Capa

“Na semana 2 mostramos o compilador de regras. Hoje é a pré-apresentação do relatório técnico: vamos percorrer o texto na ordem das seções e dizer o que já está pronto e o que falta.”

## 2. A uma semana da entrega

“Três grupos. Pronto no relatório: contexto, hipóteses de H1 a H3, implementação, experimentos, resultados, impacto e conclusões. Feito no código, mas ainda não no texto: as alternativas com ‘ou’, as restrições de horário com dois turnos e a tradução de regras por modelo de linguagem. E o que falta: avaliar a tradução, que é a hipótese H4, definir o título, preencher os dados dos autores e revisar.”

**Fonte:** os trechos `\pendente{...}` do `relatorio/main.tex` (resumo, H4, métrica de H4, resultado de H4, LGPD da tradução, créditos, título e dados dos autores) e o último commit (`2e518e9`, “Adiciona regras OU, dois turnos e tradução com Gemini”).

## 3. O problema

“Planejar o turno do ACS vai além de escolher o percurso. A lei exige curso técnico, equipamento e supervisão para pressão e glicemia. Os materiais são finitos e só se repõem na unidade. E cada equipe tem regras próprias, como higienizar as mãos ou usar N95 na suspeita de tuberculose. Modelado em PDDL, o planejador cumpre a lei sem código específico, mas cada regra nova exige editar o domínio em vários pontos, e isso restringe a manutenção a quem programa.”

**Ressalva:** os 10 pacientes são fictícios, com marcas como gestante e suspeita de tuberculose; só as coordenadas são reais. As regras da equipe (higienização, N95) são sintéticas, não normas.

## 4. A solução

“O fluxo é o da semana 2: a equipe escreve a regra num formulário, isso vira um arquivo `regras.toml`, o compilador gera o PDDL e o planejador monta o roteiro. O compilador é determinístico e não usa IA, então a mesma regra gera sempre o mesmo PDDL. E o domínio legal nunca é alterado: as regras só acrescentam exigências.”

**Fonte:** figura `../semana-02/figs/01-compilador.pdf`. A garantia de que a lei não é afrouxada está em `compilador/dominio.py`.

## 5. Hipóteses e métricas

“H1: regras nos modelos, compiladas, equivalem ao PDDL escrito à mão; medimos igualdade estrutural e custo ótimo igual em cada instância. H2: descrever a regra exige menos linhas que alterar o PDDL. H3: com as regras ativas, o roteiro de 10 pacientes sai em até 120 segundos por busca. H1 a H3 foram confirmadas. H4 é a extensão: alternativas e horários cabem nos modelos, e um modelo de linguagem traduz regras em linguagem natural. Essa ainda está em avaliação.”

**Ressalva:** no relatório, o texto de H4 e sua métrica estão marcados como pendentes. Na parte de “cabem nos modelos” há implementação e testes; na parte do modelo de linguagem não há medição ainda.

## 6. Sete modelos fixos

“Os cinco modelos da semana 2: recurso, preparo, pré-requisito, consumo e exigência por paciente. Dois são novos, em verde: a alternativa, em que um de dois preparos basta antes da medição, e o período, em que pacientes com uma marca só podem ser visitados de manhã ou à tarde. O que não cabe nos modelos fica de fora, de propósito, em vez de virar um PDDL que ninguém consegue conferir.”

**Fonte:** tabela de modelos do `projeto-inovacao-grupoB/README.md`.

## 7. O que acontece por baixo

“O pipeline: seleção dos pacientes, rota, compilação, busca, limpeza e roteiro. Três pontos técnicos. Na instanciação com poda, a combinação é descartada assim que uma precondição fixa falha: com sete regras, 4,7 bilhões de combinações viram 9.449 ações. Na busca, usamos o Fast Downward com LM-cut, e, para muitas regras, janelas: planeja-se de forma ótima as próximas três visitas e avança-se uma. E a limpeza remove ações redundantes sem nunca aumentar o custo.”

**Fonte:** seção 3 do relatório e `DESIGN.md` (“Instanciação com poda”, “Estratégia de busca”). O Fast Downward é opcional; sem ele, o sistema usa o planejador do Ciclo 2.

## 8. Como avaliamos

“Dois experimentos. Para H1, 24 instâncias de 2 a 4 pacientes, com capacidades reduzidas para forçar reposições, e oito alterações propositais nas regras como controle negativo. Para H2 e H3, sete regras novas, sozinhas e acumuladas, com 1 a 10 pacientes. Mesma planilha, mesma rota, limite de 120 segundos por busca. Cada configuração rodou uma vez, porque o resultado é determinístico; os tempos indicam ordem de grandeza.”

**Fonte:** seção 4 do relatório. Ambiente: Core Ultra 5 245KF, 16 GB, Windows 11, Python 3.14.

## 9. H1: o compilador está correto

“Comparamos três regras do Ciclo 2, escritas como modelos, com o domínio estendido que o outro grupo escreveu à mão. A estrutura é igual, e 24 de 24 instâncias são equivalentes. As oito alterações propositais foram acusadas pela comparação estrutural.”

**Ressalva:** a comparação de comportamento só revela uma alteração quando a instância exercita aquela regra; por isso há as duas comparações (`DESIGN.md`, “Controle negativo”).

## 10. H2: regras mais curtas que o PDDL

“Para cada regra, as barras azuis são as linhas de TOML e as laranjas, as linhas de PDDL alteradas. De 7 a 18 linhas contra 13 a 60. Em média, cada linha escrita evita 3,1 linhas de PDDL, espalhadas por até nove ações.”

**Fonte:** Tabela 1 do relatório e `exemplos/avaliacao/resultados.md`. Valores do gráfico (TOML/PDDL): R1 8/27, R2 13/36, R3 7/13, R4 18/60, R5 18/60, R6 17/52, R7 12/41. Linhas sem comentários.

## 11. H3: o roteiro sai, mas o ótimo não escala

“Cada regra sozinha soma de 1 a 9 minutos a um turno ótimo de 386. O primeiro plano do Fast Downward sai em até 0,2 segundo em todos os casos. Mas provar o ótimo só é possível até quatro regras acumuladas, em 31 segundos; a partir de cinco passa de 120. Para isso usamos as janelas: com as sete regras e 10 pacientes, 430 minutos em 16 segundos. O planejador do Ciclo 2 sozinho não termina a partir de seis regras.”

**Fonte:** Tabelas 1 e 2 do relatório e `DESIGN.md` (“Qualidade dos planos: janelas”). Os 430 min estão, por estimativa, cerca de 5% acima do ótimo, que é desconhecido. O README fala em “~30 s” até o roteiro com o `auto`, e o relatório em 16 s só para a busca das janelas; se perguntarem, são medidas diferentes.

**Ressalva:** regras e pacientes sintéticos; “1 a 9 minutos” é cada regra sozinha, no plano ótimo.

## 12. Extensões: ou, horários e tradução

“À esquerda, as duas regras novas, como se escrevem. Na alternativa, a conferência do aparelho vale com um de dois preparos antes da pressão. No período, pacientes marcados como gestante só são visitados de manhã, e o planejador passa a ter dois turnos. À direita, a tradução: a pessoa descreve a regra em português, o modelo de linguagem propõe blocos candidatos, o compilador os confere e a equipe revisa no formulário. Está implementado e testado, mas a avaliação de H4 ainda falta: quantas regras geradas compilam e coincidem com um gabarito.”

**Fonte:** `exemplos/alternativa-e-turnos.toml` (só com a lista de preparos quebrada em duas linhas para caber) e `HOWTORUN.md`, “Testar OR, manhã e tarde e a tradução”. Testes em `backend/testes/test_novas_regras.py`. O código usa o Gemini ou um servidor compatível com Chat Completions.

**Ressalva:** não há resultado de tradução para citar. Não dizer taxa de acerto. O servidor envia ao provedor a descrição, o catálogo de modelos e os nomes de recursos e preparos, nunca dados de pacientes; a pessoa deve manter dados pessoais fora do texto.

## 13. Impacto e caminho até o uso

“Socialmente, a equipe mantém as próprias regras sem depender de quem programa. Economicamente, cada regra mostra o seu custo antes de ser adotada; o ganho frente ao planejamento manual não foi medido. Quanto à LGPD, os dados são fictícios, o sistema roda localmente e a tradução só recebe o texto da regra. Para transferência, os parceiros naturais são as secretarias municipais de saúde e o e-SUS Território. O protótipo está entre os níveis 3 e 4 de maturidade. Faltam integrar o cadastro do e-SUS, usar distâncias pelas ruas e operar sem conexão.”

**Fonte:** seção 5 do relatório.

## 14. O que aprendemos

“O que foi refutado: nossa tese inicial era que o planejamento acharia planos que um programa comum não acha. Corrigido, o programa procedural acha os mesmos planos. O que se sustentou foi o custo de manutenção: diante de regras novas, a correção procedural falha, e o PDDL se adapta sem mudar código. Isso motivou o compilador. Os limites: o ótimo com muitas regras é desconhecido, a rota é escolhida só pela distância, sem considerar as regras, e os dados são sintéticos, com cada configuração executada uma vez.”

**Fonte:** seção 6 do relatório e `DESIGN.md`, “Limitações e observações”. Falha herdada do Ciclo 2, caso perguntem: voltar da UBS para a casa não desfaz preparos como a higienização.

## 15. Até 04/12

“No relatório: avaliar a hipótese H4 com descrições de regras e gabarito, e atualizar resumo, implementação, resultados e créditos com as extensões. Para a entrega: fechar as pendências, que são o título, os dados dos autores e a revisão final, e ensaiar a apresentação final, com demonstração na interface.”

**Condução:** a divisão dos itens entre os três é uma sugestão a combinar antes do dia. O teste com usuários que não programam tem material pronto (`exemplos/avaliacao/teste-usuario/`), mas está só como próximo passo no relatório; incluir só se houver tempo.

## 16. Créditos

“Obrigado. O planejador original é do Grupo B do Ciclo 2; o compilador, a interface e as extensões são deste ciclo.”
