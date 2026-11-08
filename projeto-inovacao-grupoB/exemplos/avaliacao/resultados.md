# Resultados das medições (etapa 8.4)

Gerado por `python -m testes.medicoes` em 2026-11-08, Python 3.14.4, Fast Downward instalado. Planilha de avaliação, mesma rota em todas as execuções.

## A. Cada regra sozinha

Esforço: linhas de TOML (sem comentários) que a pessoa escreve, contra linhas do domínio PDDL que o compilador altera. Turno ótimo no turno completo da planilha de avaliação; Δ em relação ao turno sem regras.

| Regra | TOML (linhas) | PDDL alterado (linhas) | Ações novas | Ações modificadas | Compila | Roteiro conferido | Turno ótimo | Δ turno | Busca ótima |
|---|---|---|---|---|---|---|---|---|---|
| r1-lancetas | 8 | 27 | 1 | 1 | sim | sim | 389 | +3 | 0.6 s |
| r2-termometro | 13 | 36 | 2 | 3 | sim | sim | 387 | +1 | 1.3 s |
| r3-balanca | 7 | 13 | 1 | 1 | sim | sim | 388 | +2 | 0.3 s |
| r4-avental | 18 | 60 | 4 | 5 | sim | sim | 395 | +9 | 0.6 s |
| r5-n95 | 18 | 60 | 4 | 5 | sim | sim | 389 | +3 | 1.0 s |
| r6-luvas-gestante | 17 | 52 | 3 | 3 | sim | sim | 387 | +1 | 1.3 s |
| r7-algodao | 12 | 41 | 1 | 2 | sim | sim | 389 | +3 | 0.6 s |

Turno ótimo sem regras: 386 min. Busca ótima: Fast Downward, A* com LM-cut, limite de 120 s.

## B. Regras acumuladas

As regras entram uma a uma (R1, R1–R2, ...), e por fim junto com as três regras sintéticas do Ciclo 2. Combinações sem poda: o que a instanciação original do Ciclo 2 testaria.

| Regras | Combinações sem poda | Ações com poda | Instanciação | Ciclo 2 (h_add) | FD 1º plano | FD ótimo (LM-cut) |
|---|---|---|---|---|---|---|
| nenhuma | 33.325 | 266 | 0.00 s | 427 min, 0.1 s | 412 min, 0.1 s | 386 min, 0.2 s |
| R1 | 1.777.177 | 1.188 | 0.02 s | 444 min, 0.5 s | 415 min, 0.1 s | 389 min, 0.6 s |
| R1–R2 | 1.778.750 | 1.220 | 0.02 s | 445 min, 2.5 s | 417 min, 0.1 s | 390 min, 4.8 s |
| R1–R3 | 1.778.751 | 1.221 | 0.02 s | 447 min, 2.5 s | 420 min, 0.1 s | 392 min, 6.6 s |
| R1–R4 | 1.780.564 | 1.263 | 0.02 s | 537 min, 6.1 s | 429 min, 0.1 s | 401 min, 31.0 s |
| R1–R5 | 1.782.377 | 1.305 | 0.02 s | 601 min, 34.5 s | 479 min, 0.1 s | > 120 s |
| R1–R6 | 3.540.870 | 1.337 | 0.02 s | > 120 s | 483 min, 0.1 s | > 120 s |
| R1–R7 | 4.676.963.922 | 9.449 | 0.21 s | > 120 s | 486 min, 0.1 s | > 120 s |
| R1–R7 + 3 do Ciclo 2 | 565.907.493.560 | 90.545 | 1.84 s | > 120 s | 550 min, 0.2 s | > 120 s |

Limite de 120 s por busca. Os tempos do Fast Downward incluem a tradução do PDDL. Custos antes da limpeza do plano.

## C. Sete regras, número de pacientes

Pacientes escolhidos para que as marcas apareçam; janelas de supervisão iguais ao número de pacientes.

| Pacientes | Ações | Ciclo 2 (h_add) | FD 1º plano | FD ótimo (LM-cut) |
|---|---|---|---|---|
| 1 (p7) | 333 | 63 min, 0.0 s | 83 min, 0.1 s | 63 min, 0.1 s |
| 2 (p6, p8) | 532 | 152 min, 1.3 s | 168 min, 0.1 s | 150 min, 0.1 s |
| 3 (p3, p6, p7) | 731 | 203 min, 3.0 s | 226 min, 0.1 s | 156 min, 1.0 s |
| 5 (p3, p5, p6, p7, p8) | 1129 | > 120 s | 337 min, 0.1 s | > 120 s |
| 10 (todos os 10) | 9449 | > 120 s | 486 min, 0.1 s | > 120 s |

Sete regras ativas. Limite de 120 s por busca.
