#!/bin/sh
# Compila as figuras e depois a apresentacao (equivalente ao compilar.ps1).
#   sh slides/semana-02/compilar.sh      (de qualquer pasta)
set -e
MOTOR="${1:-pdflatex}"
cd "$(dirname "$0")"

compilar() {   # compilar ARQUIVO.tex [PASSADAS]
    nome="${1%.tex}"
    mkdir -p build
    i=0
    while [ "$i" -lt "${2:-1}" ]; do
        if ! "$MOTOR" -interaction=nonstopmode -halt-on-error -file-line-error \
                -output-directory=build "$1" > "build/$nome-console.txt" 2>&1; then
            tail -n 45 "build/$nome-console.txt"
            echo "Falha ao compilar $1. Consulte build/$nome.log." >&2
            exit 1
        fi
        i=$((i + 1))
    done
    cp "build/$nome.pdf" "$nome.pdf"
    echo "Compilado: $nome.pdf"
}

(cd figs && compilar 01-compilador.tex)
compilar apresentacao.tex 2
