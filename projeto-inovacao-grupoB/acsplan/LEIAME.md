# acsplan (cópia parcial do Ciclo 2)

Esta pasta é uma **cópia parcial e sem alterações** do pacote `acsplan` do
Grupo B do Ciclo 2 (Gabriel Pieruccini Knopp, Arthur Andrade da Silva e
Izadora Candotti de Oliveira), tirada de `PCI-Saude-GroupB/acsplan` no commit
`9ba6cca` deste repositório.

Ela existe para que o compilador de regras funcione sozinho, sem depender da
pasta do Ciclo 2. O código do Ciclo 2 **não é editado aqui**: tudo o que é
novo fica em `../compilador/`. Este arquivo é o único acréscimo.

## O que foi copiado

| Pasta | Arquivos | Uso no compilador |
|---|---|---|
| `dados/` | `carregador.py`, `gerador.py`, `modelos.py`, `microarea_exemplo.csv`, `microarea_exemplo.json` | planilha de pacientes e instâncias de teste |
| `geo/` | `distancias.py`, `_rede.py`, `genetico.py`, `roteirizador.py` | ordem das paradas |
| `logica/` | `planejador.py`, `gerador_problema.py`, `dominios/dominio-legal.pddl`, `dominios/dominio-estendido.pddl` | parser PDDL, busca, problema legal; o domínio estendido é a referência do teste de equivalência |
| `selecao/` | `politica.py` | quem entra no turno |

Os `__init__.py` de cada pasta também foram copiados (são vazios).

## O que ficou de fora

Linha de comando (`cli.py`, `__main__.py`), experimentos, testes do Ciclo 2,
mapa e inspeção, roteiro do ACS (`saida/`), executor procedural,
realimentação, verificação cruzada e compilação de precondições negativas.
Nada disso é usado pelo compilador.

## Conferir que a cópia continua idêntica

Com a pasta do Ciclo 2 ao lado, a partir da raiz do repositório:

```bash
diff -rq --exclude=__pycache__ --exclude=LEIAME.md --exclude=cache_osrm \
    PCI-Saude-GroupB/acsplan projeto-inovacao-grupoB/acsplan | grep -v "^Only in PCI"
```

Sem saída, a cópia é idêntica ao original.
