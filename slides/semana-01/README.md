# Pitch para stakeholders — semana 1

Apresentação de **11 slides, para cerca de 10 minutos**, organizada em **Problema → Solução → Exemplos → Próximos passos**. O problema (slides 2–3) e a solução (slides 4–5) aparecem explicitamente, cada um numa frase, antes de qualquer detalhe técnico. O pitch termina com perguntas aos stakeholders; **a inovação do Grupo C será definida depois da escuta**.

- `pitch.tex`: fonte principal Beamer, 16:9, tema Singapore e cores da referência fornecida.
- `pitch.pdf`: apresentação compilada.
- `figs/`: fontes LaTeX/TikZ e PDFs independentes das figuras.
- `roteiro.md`: sugestão de fala e fontes internas que sustentam o conteúdo.
- `versao-anterior/`: pitch de 9 slides (tex, pdf, roteiro e figuras) antes da reestruturação problema/solução.
- `compilar.ps1`: compila as figuras antes do documento principal.

## Compilar

Com uma distribuição LaTeX que inclua Beamer, TikZ, standalone e babel-português:

```powershell
# A partir da raiz do repositório:
powershell -ExecutionPolicy Bypass -File slides/semana-01/compilar.ps1
```

O script pode ser chamado de qualquer pasta. Os arquivos auxiliares ficam em `build/` e `figs/build/`; os PDFs são copiados para junto de seus fontes. O documento principal usa `\includegraphics` para incluir os PDFs das figuras, sem exigir shell escape.

Para compilar manualmente, entre em `figs/`, execute `pdflatex` para cada figura (exceto `estilo.tex`), volte à pasta `semana-01` e execute `pdflatex pitch.tex` duas vezes.

## Recorte

A apresentação fornecida pelo usuário orientou a aparência e a organização dos arquivos. Seus resultados quantitativos pertencem a outro trabalho e não foram reutilizados. Os créditos do projeto-base e do grupo apresentador estão no slide final, com nomes abreviados. A capa identifica apenas os apresentadores. As ressalvas e notas explicativas ficam no roteiro. A data da sessão foi deixada em aberto.

O diagrama do fluxo apresenta a opção de realimentação já implementada no projeto-base. A figura das rotas é um exemplo fictício de precedência, sem estimativas de distância. “Atende à regra de prioridade” refere-se apenas à regra ilustrada, não à validade integral de um atendimento.

A figura de reposição também é didática: os estoques ilustram consumo e reposição, sem representar quantidades normativas. As regras adicionais são explicitamente hipotéticas, conforme o domínio estendido do projeto. Os valores de 6 visitas, 266 minutos e excedente de 26 minutos vêm do roteiro simulado salvo pelo Grupo B; não representam desempenho observado em campo. Fontes e ressalvas estão no roteiro de fala.
