# Apresentação — semana 2: compilador de regras

Apresentação de **13 slides, para cerca de 10 minutos**, com o mesmo design do pitch da semana 1 ([`../semana-01`](../semana-01)). Está organizada em **Problema → Solução → Na prática → Resultados → Próximos passos** e mostra a inovação do Grupo B no Ciclo 3: a equipe escreve as regras do planejamento em modelos fixos, e um compilador as transforma em PDDL ([`projeto-inovacao-grupoB/`](../../projeto-inovacao-grupoB)).

- `apresentacao.tex`: fonte principal Beamer, 16:9, tema Singapore e as cores da semana 1.
- `apresentacao.pdf`: apresentação compilada.
- `figs/`: fonte LaTeX/TikZ e PDF da figura do fluxo do compilador, com um exemplo de cada passo.
- `figs/capturas/`: capturas da interface web (formulário, roteiro, folha impressa e mapa).
- `roteiro.md`: sugestão de fala, fontes de cada número e ressalvas.
- `compilar.sh` (Linux) e `compilar.ps1` (Windows): compilam as figuras antes do documento principal.

## Compilar

Com uma distribuição LaTeX que inclua Beamer, TikZ, standalone e babel-português:

```sh
# Linux, a partir de qualquer pasta:
sh slides/semana-02/compilar.sh
```

```powershell
# Windows, a partir da raiz do repositório:
powershell -ExecutionPolicy Bypass -File slides/semana-02/compilar.ps1
```

Os arquivos auxiliares ficam em `build/` e `figs/build/`; os PDFs são copiados para junto de seus fontes.

## Capturas da interface

As capturas foram feitas com a interface rodando (`python3 acs.py web`, com o Fast Downward instalado), num navegador sem janela e em resolução dobrada; a folha impressa é a primeira página do PDF que o navegador gera ao imprimir o roteiro. O exemplo é o mesmo em todos os slides: as regras `exemplos/sinteticas-ciclo2.toml` (higienização, máscara e coletor) e 5 pacientes da planilha de avaliação, com início do turno às 08:00. O mapa de ruas é do OpenStreetMap, e a atribuição aparece na própria captura.

## Recorte

Regras e pacientes são **sintéticos**: não são normas nem dados reais. Os números do slide 11 vêm da avaliação documentada no `DESIGN.md` do projeto; as fontes e ressalvas de cada um estão no roteiro de fala.
