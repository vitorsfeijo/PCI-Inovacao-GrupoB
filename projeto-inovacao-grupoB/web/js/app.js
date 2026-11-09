// Ponto de entrada da interface: carrega a descricao dos modelos e os
// exemplos do servidor, monta as telas e cuida das abas.

import { api } from "./api.js";
import { TelaComparar } from "./tela-comparar.js";
import { TelaMapa } from "./tela-mapa.js";
import { TelaPlanejar } from "./tela-planejar.js";
import { TelaRegras } from "./tela-regras.js";

const TELAS = ["regras", "planejar", "comparar", "mapa"];
const aoMostrar = {};                                 // tela -> funcao chamada ao aparecer

function mostrarTela(nome, { focar = false } = {}) {
  if (!TELAS.includes(nome)) nome = "regras";
  for (const tela of TELAS) {
    const ativa = tela === nome;
    document.getElementById(`aba-${tela}`).setAttribute("aria-selected", String(ativa));
    document.getElementById(`aba-${tela}`).tabIndex = ativa ? 0 : -1;
    document.getElementById(`tela-${tela}`).classList.toggle("oculto", !ativa);
  }
  if (location.hash !== `#${nome}`) history.replaceState(null, "", `#${nome}`);
  aoMostrar[nome]?.();
  if (focar) document.getElementById(`aba-${nome}`).focus();
}

function ligarAbas() {
  TELAS.forEach((tela, i) => {
    const aba = document.getElementById(`aba-${tela}`);
    aba.addEventListener("click", () => mostrarTela(tela));
    aba.addEventListener("keydown", (evento) => {          // setas trocam de aba
      const passo = { ArrowRight: 1, ArrowLeft: -1 }[evento.key];
      if (passo) mostrarTela(TELAS[(i + passo + TELAS.length) % TELAS.length], { focar: true });
    });
  });
  window.addEventListener("hashchange", () => mostrarTela(location.hash.slice(1)));
  mostrarTela(location.hash.slice(1));
}

async function iniciar() {
  try {
    const [meta, exemplos] = await Promise.all([api.modelos(), api.exemplos()]);
    let telaPlanejar = null;
    let telaComparar = null;
    const telaRegras = new TelaRegras(document.getElementById("tela-regras"), meta, exemplos, {
      aoMudar: () => {
        telaPlanejar?.atualizarFormulario();
        telaComparar?.atualizar();
      },
    });
    const situacaoDasRegras = () => telaRegras.situacao();
    const irPara = (tela) => mostrarTela(tela, { focar: true });
    const telaMapa = new TelaMapa(document.getElementById("tela-mapa"), { irPara });
    telaPlanejar = new TelaPlanejar(document.getElementById("tela-planejar"), exemplos, {
      situacaoDasRegras,
      irParaRegras: () => irPara("regras"),
      aoPlanejar: (ultimo) => telaMapa.mostrar(ultimo),
      verNoMapa: () => irPara("mapa"),
    });
    telaComparar = new TelaComparar(document.getElementById("tela-comparar"), {
      situacaoDasRegras,
      planejar: telaPlanejar,
      irPara,
    });
    aoMostrar.comparar = () => telaComparar.atualizar();
    aoMostrar.mapa = () => telaMapa.aoAparecer();
    Object.assign(window, { telaRegras, telaPlanejar, telaComparar, telaMapa });
    ligarAbas();
    document.body.dataset.pronto = "sim";            // usado pelos testes de ponta a ponta
  } catch (erro) {
    const caixa = document.getElementById("erro-geral");
    caixa.textContent = `Não foi possível falar com o servidor (${erro.message}). ` +
      "Confira se o comando `python3 acs.py web` continua rodando no terminal.";
    caixa.classList.remove("oculto");
  }
}

iniciar();
