# Pré-apresentação — semana 4 (27/11)

Apresentação de **16 slides, para cerca de 12 minutos**, com o mesmo design das semanas 1 e 2. Ela percorre o relatório técnico ([`../../relatorio/main.tex`](../../relatorio/main.tex)) na ordem das suas seções: **Onde estamos → Problema → Solução → Implementação → Experimentos → Resultados → Impacto → Conclusões → Próximos passos**. Mostra o que já está pronto, o que foi implementado mas ainda não está no texto (alternativas, horários e tradução por modelo de linguagem) e o que falta para a entrega de 04/12.

- `apresentacao.tex`: fonte principal Beamer, 16:9, tema Singapore e as cores das semanas anteriores.
- `apresentacao.pdf`: apresentação compilada (gerada por `compilar.sh`).
- `roteiro.md`: sugestão de fala, tempos, fontes de cada número e ressalvas.
- `compilar.sh` (Linux) e `compilar.ps1` (Windows): compilam a apresentação.

A figura do fluxo do compilador vem de [`../semana-02/figs/`](../semana-02/figs), já compilada; nada foi duplicado.

## Compilar

Com uma distribuição LaTeX que inclua Beamer, TikZ e babel-português:

```sh
# Linux, a partir de qualquer pasta:
sh slides/semana-04/compilar.sh
```

```powershell
# Windows, a partir da raiz do repositório:
powershell -ExecutionPolicy Bypass -File slides/semana-04/compilar.ps1
```

Os arquivos auxiliares ficam em `build/`; o PDF é copiado para junto do fonte.

## Recorte

- **Números:** os do relatório (Tabelas 1 e 2) e do `DESIGN.md`. Regras e pacientes são **sintéticos**.
- **H4 (tradução):** não há resultado; o slide 12 diz isso. Não foi incluída nenhuma taxa de acerto.
- **Pendências do relatório** (título, dados dos autores, texto das extensões) aparecem no slide 2 como o que falta.
