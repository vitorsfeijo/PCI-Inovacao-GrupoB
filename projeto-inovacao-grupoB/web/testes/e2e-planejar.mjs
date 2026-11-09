// Teste de ponta a ponta da tela de planejamento, num Chrome sem janela.
//
//   CHROME=google-chrome node web/testes/e2e-planejar.mjs URL_DO_SERVIDOR PASTA_DAS_CAPTURAS
//
// Planeja de verdade (poucos pacientes, para ser rapido): sem regras, com as
// regras sinteticas abertas na tela Regras, e com uma planilha sem a coluna
// que uma regra exige (o erro tem de aparecer explicado).

import { readFileSync } from "node:fs";
import { rodarCenario } from "./navegador.mjs";

// planilha do Ciclo 2 sem a ultima coluna (exige_protecao_respiratoria)
const PLANILHA_SEM_COLUNA = readFileSync(
  new URL("../../backend/acsplan/dados/microarea_exemplo.csv", import.meta.url), "utf8")
  .trim().split(/\r?\n/).map((linha) => linha.split(",").slice(0, -1).join(",")).join("\n") + "\n";

const AJUDANTES = `
window.__e2e = {
  form() { return document.getElementById('pedido'); },
  escolher(nome, valor) { this.form().querySelector('input[name=' + nome + '][value=' + valor + ']').click(); },
  preencher(nome, valor) {
    const e = this.form().elements[nome];
    e.value = valor; e.dispatchEvent(new Event('change', { bubbles: true }));
  },
  planejar() { document.getElementById('botao-planejar').click(); },
  estado() { return document.getElementById('resultado').dataset.estado; },
  paradas() { return [...document.querySelectorAll('#resultado .parada:not(.parada--ubs)')]; },
  texto(seletor) { return document.querySelector(seletor)?.textContent ?? null; },
};`;

const PRAZO_PLANEJAR = 150_000;

await rodarCenario(async ({ cdp, avaliar, ate, capturar, abrir, largura, temaEscuro, url, relato }) => {
  const ajudar = () => avaliar(`${AJUDANTES}; window.confirm = () => true; true`);
  const aba = (nome) => avaliar(`document.getElementById('aba-${nome}').click(); true`);
  // a tela marca #resultado[data-estado] ao terminar (roteiro ou falha)
  const planejar = async () => {
    await avaliar("delete document.getElementById('resultado').dataset.estado; __e2e.planejar(); true");
    await ate(`document.getElementById('resultado').dataset.estado &&
               !document.getElementById('botao-planejar').disabled`,
              "o planejamento terminar", PRAZO_PLANEJAR);
  };

  await abrir(url);
  await avaliar("localStorage.clear(); true");
  await abrir(`${new URL(url).origin}/#planejar`);
  await ajudar();
  relato.aba_pelo_endereco = await avaliar("!document.getElementById('tela-planejar').classList.contains('oculto')");

  // 1. sem regras: a opcao "regras da equipe" fica desabilitada
  relato.situacao_sem_regras = await avaliar("__e2e.texto('#situacao-regras')");
  relato.equipe_desabilitada = await avaliar("__e2e.form().querySelector('input[value=equipe]').disabled");
  await capturar("p1-formulario");

  // 2. erro de preenchimento pego no navegador
  await avaliar("__e2e.escolher('fonte', 'sintetica'); __e2e.preencher('pacientes_sinteticos', '0'); __e2e.planejar(); true");
  relato.erro_preenchimento = await avaliar("__e2e.texto('#erro-pedido')");
  relato.detalhe_sintetica_visivel = await avaliar(
    "!document.querySelector('[data-fonte=sintetica]').classList.contains('oculto')");

  // 3. planejar sem regras: 4 pacientes da planilha de exemplo
  await avaliar(`__e2e.escolher('fonte', 'exemplo'); __e2e.preencher('exemplo', 'exemplo-ciclo2');
                 __e2e.preencher('max_pacientes', '4'); __e2e.preencher('inicio', '08:00'); true`);
  await planejar();
  relato.estado_sem_regras = await avaliar("__e2e.estado()");
  relato.paradas_sem_regras = await avaliar("__e2e.paradas().length");
  relato.adiados_sem_regras = await avaliar(
    "document.querySelectorAll('#resultado .caixa--neutra li').length");
  relato.origem_sem_regras = await avaliar("__e2e.texto('.roteiro__topo p')");
  relato.hora_primeira = await avaliar("__e2e.paradas()[0].querySelector('.parada__hora').textContent");
  await capturar("p2-roteiro-sem-regras");
  relato.passos.push("sem-regras");

  // 4. abrir as regras sinteticas na tela Regras e voltar
  await aba("regras");
  await avaliar(`(() => { const s = document.getElementById('exemplos');
                 s.value = 'sinteticas-ciclo2'; s.dispatchEvent(new Event('change')); return true; })()`);
  await ate("document.getElementById('estado-regras').textContent.includes('válidas')", "as regras valerem");
  await aba("planejar");
  relato.endereco_planejar = await avaliar("location.hash");
  relato.situacao_com_regras = await avaliar("__e2e.texto('#situacao-regras')");
  relato.equipe_marcada = await avaliar("__e2e.form().querySelector('input[value=equipe]').checked");
  await planejar();
  relato.estado_com_regras = await avaliar("__e2e.estado()");
  relato.paradas_com_regras = await avaliar("__e2e.paradas().length");
  relato.tarefas_com_regras = await avaliar(
    "[...document.querySelectorAll('#resultado .tarefas li')].map(l => l.textContent.trim())");
  relato.origem_com_regras = await avaliar("__e2e.texto('.roteiro__topo p')");
  await capturar("p3-roteiro-com-regras");
  relato.passos.push("com-regras");

  // 5. imprimir: so o roteiro
  await cdp("Emulation.setEmulatedMedia", { media: "print" });
  relato.impressao = await avaliar(`({
    formulario: getComputedStyle(document.getElementById('pedido')).display,
    cabecalho: getComputedStyle(document.querySelector('.cabecalho')).display,
    roteiro: getComputedStyle(document.querySelector('.roteiro')).display })`);
  await capturar("p4-impressao");
  await cdp("Emulation.setEmulatedMedia", { media: "" });
  relato.passos.push("impressao");

  // 6. tema escuro e celular com o roteiro na tela
  await temaEscuro(true);
  await capturar("p5-roteiro-escuro");
  await temaEscuro(false);
  await largura(390, 900, true);
  relato.rolagem_horizontal = await avaliar("document.documentElement.scrollWidth > window.innerWidth");
  await capturar("p6-celular");
  await largura(1280, 1000);

  // 7. planilha da equipe sem a coluna que a regra de mascara exige
  await avaliar(`(() => {
    const dt = new DataTransfer();
    dt.items.add(new File([${JSON.stringify(PLANILHA_SEM_COLUNA)}], 'pacientes.csv', { type: 'text/csv' }));
    const entrada = document.getElementById('arquivo-csv');
    entrada.files = dt.files;
    entrada.dispatchEvent(new Event('change', { bubbles: true }));
    return true; })()`);
  await ate("__e2e.texto('#nome-csv').includes('pacientes')", "a planilha ser lida");
  relato.nome_csv = await avaliar("__e2e.texto('#nome-csv')");
  relato.fonte_csv = await avaliar("__e2e.form().elements.fonte.value");
  await planejar();
  relato.estado_falha = await avaliar("__e2e.estado()");
  relato.falha = await avaliar("__e2e.texto('#resultado .caixa--erro')");
  await capturar("p7-falha");
  relato.passos.push("falha");
});
