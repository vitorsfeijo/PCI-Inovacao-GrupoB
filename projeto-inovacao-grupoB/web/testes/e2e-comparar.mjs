// Teste de ponta a ponta da tela "antes x depois", num Chrome sem janela.
//
//   CHROME=google-chrome node web/testes/e2e-comparar.mjs URL_DO_SERVIDOR PASTA_DAS_CAPTURAS
//
// Abre as regras sinteticas, escolhe 5 pacientes da planilha de avaliacao na
// aba Planejar e compara o turno sem e com as regras (planeja de verdade).

import { rodarCenario } from "./navegador.mjs";

const PRAZO_COMPARAR = 200_000;

await rodarCenario(async ({ avaliar, ate, capturar, abrir, largura, temaEscuro, url, relato }) => {
  const aba = (nome) => avaliar(`document.getElementById('aba-${nome}').click(); true`);
  const texto = (seletor) => avaliar(`document.querySelector(${JSON.stringify(seletor)})?.textContent ?? null`);

  await abrir(url);
  await avaliar("localStorage.clear(); true");
  await abrir(`${new URL(url).origin}/#comparar`);

  // 1. sem regras nao ha o que comparar
  relato.regras_sem_regras = await texto("#comparar-regras");
  relato.botao_sem_regras = await avaliar("document.getElementById('botao-comparar').disabled");
  await capturar("c1-sem-regras");

  // 2. regras sinteticas (aba Regras) e 5 pacientes da avaliacao (aba Planejar)
  await aba("regras");
  await avaliar(`(() => { const s = document.getElementById('exemplos');
                 s.value = 'sinteticas-ciclo2'; s.dispatchEvent(new Event('change')); return true; })()`);
  await ate("document.getElementById('estado-regras').textContent.includes('válidas')", "as regras valerem");
  await aba("planejar");
  await avaliar(`(() => { const f = document.getElementById('pedido').elements;
                 f.exemplo.value = 'avaliacao'; f.max_pacientes.value = '5'; f.inicio.value = '07:30';
                 f.exemplo.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
  await aba("comparar");
  relato.regras_com_regras = await texto("#comparar-regras");
  relato.turno = await texto("#comparar-turno");
  relato.botao_com_regras = await avaliar("document.getElementById('botao-comparar').disabled");

  // 3. comparar
  await avaliar("document.getElementById('botao-comparar').click(); true");
  await ate("document.getElementById('comparacao').dataset.estado && " +
            "!document.getElementById('botao-comparar').disabled", "a comparação terminar", PRAZO_COMPARAR);
  relato.estado = await avaliar("document.getElementById('comparacao').dataset.estado");
  relato.numeros = await avaliar(
    "[...document.querySelectorAll('#comparacao .numero')].map(n => n.innerText.replace(/\\n+/g, ' | '))");
  relato.mudancas = await avaliar(
    "[...document.querySelectorAll('#comparacao .caixa--neutra li')].map(l => l.textContent)");
  relato.paradas = await avaliar("document.querySelectorAll('#comparacao .parada').length");
  relato.tarefas_novas = await avaliar("document.querySelectorAll('#comparacao .tarefas li.tarefa--nova').length");
  relato.tarefas_todas = await avaliar("document.querySelectorAll('#comparacao .tarefas li').length");
  relato.primeira_chegada = await texto("#comparacao .parada .parada__hora");
  await capturar("c2-comparacao");
  relato.passos.push("comparar");

  // 4. so o que mudou
  await avaliar(`(() => { const c = document.getElementById('so-mudancas');
                 c.click(); return true; })()`);
  relato.tarefas_so_mudancas = await avaliar("document.querySelectorAll('#comparacao .tarefas li').length");
  await capturar("c3-so-mudancas");
  relato.passos.push("so-mudancas");

  // 5. tema escuro e celular
  await temaEscuro(true);
  await capturar("c4-escuro");
  await temaEscuro(false);
  await largura(390, 900, true);
  relato.rolagem_horizontal = await avaliar("document.documentElement.scrollWidth > window.innerWidth");
  await capturar("c5-celular");
  relato.passos.push("aparencia");
});
