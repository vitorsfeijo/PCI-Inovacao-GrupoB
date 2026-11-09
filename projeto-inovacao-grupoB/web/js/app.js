// Ponto de entrada da interface: carrega a descricao dos modelos e os
// exemplos do servidor e monta as telas.

import { api } from "./api.js";
import { TelaRegras } from "./tela-regras.js";

async function iniciar() {
  try {
    const [meta, exemplos] = await Promise.all([api.modelos(), api.exemplos()]);
    window.telaRegras = new TelaRegras(document.getElementById("tela-regras"), meta, exemplos);
    document.body.dataset.pronto = "sim";            // usado pelos testes de ponta a ponta
  } catch (erro) {
    const caixa = document.getElementById("erro-geral");
    caixa.textContent = `Não foi possível falar com o servidor (${erro.message}). ` +
      "Confira se o comando `python3 acs.py web` continua rodando no terminal.";
    caixa.classList.remove("oculto");
  }
}

iniciar();
