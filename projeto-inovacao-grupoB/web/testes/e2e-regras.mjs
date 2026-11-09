// Teste de ponta a ponta da tela de regras, num Chrome sem janela, controlado
// pelo protocolo de depuracao (CDP). Sem dependencias: o WebSocket vem no Node 22.
//
//   CHROME=google-chrome node web/testes/e2e-regras.mjs URL_DO_SERVIDOR PASTA_DAS_CAPTURAS
//
// Imprime um JSON com o que observou; quem confere e o teste em Python
// (backend/testes/test_web.py), que tambem sobe o servidor.

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, pastaCapturas] = process.argv.slice(2);
const perfil = mkdtempSync(join(tmpdir(), "acs-e2e-"));
const chrome = spawn(process.env.CHROME || "google-chrome", [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  `--user-data-dir=${perfil}`, "--remote-debugging-port=0", "about:blank",
], { stdio: "ignore" });

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

async function portaDoChrome() {
  const arquivo = join(perfil, "DevToolsActivePort");
  for (let i = 0; i < 100; i++) {
    if (existsSync(arquivo)) return readFileSync(arquivo, "utf8").split("\n")[0];
    await esperar(100);
  }
  throw new Error("o Chrome não abriu a porta de depuração");
}

let ws;
let seq = 0;
const pendentes = new Map();
function cdp(metodo, params = {}) {
  const id = ++seq;
  ws.send(JSON.stringify({ id, method: metodo, params }));
  return new Promise((resolve, reject) => pendentes.set(id, { resolve, reject }));
}

async function avaliar(expressao) {
  const r = await cdp("Runtime.evaluate", { expression: expressao, awaitPromise: true,
                                            returnByValue: true });
  if (r.exceptionDetails) {
    throw new Error(`na página: ${r.exceptionDetails.exception?.description ?? r.exceptionDetails.text}`);
  }
  return r.result.value;
}

async function ate(condicao, descricao, prazo = 8000) {
  const fim = Date.now() + prazo;
  while (Date.now() < fim) {
    if (await avaliar(`Boolean(${condicao})`)) return;
    await esperar(80);
  }
  throw new Error(`esperei e não aconteceu: ${descricao}`);
}

async function capturar(nome) {
  const { data } = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  writeFileSync(join(pastaCapturas, `${nome}.png`), Buffer.from(data, "base64"));
}

// Ajudantes injetados na pagina: preencher e clicar como uma pessoa faria.
const AJUDANTES = `
window.__e2e = {
  campo(id) { return document.querySelector('#formulario [data-campo="' + id + '"]'); },
  digitar(id, valor) {
    const e = this.campo(id).querySelector('input');
    e.focus(); e.value = valor;
    e.dispatchEvent(new Event('input', { bubbles: true }));
    e.dispatchEvent(new Event('change', { bubbles: true }));
    e.blur();
  },
  escolher(id, valor) {
    const e = this.campo(id).querySelector('select');
    e.value = valor; e.dispatchEvent(new Event('change', { bubbles: true }));
  },
  marcar(id, valores) {
    for (const c of this.campo(id).querySelectorAll('input[type=checkbox]'))
      if (valores.includes(c.value) !== c.checked) c.click();
  },
  cartao(texto) {
    return [...document.querySelectorAll('.cartao')].find(c => c.textContent.includes(texto));
  },
  selo() { return document.getElementById('estado-regras').textContent; },
  previa() { return document.getElementById('previa').textContent; },
};`;

const relato = { passos: [] };
try {
  const porta = await portaDoChrome();
  const alvo = await (await fetch(`http://127.0.0.1:${porta}/json/new?about:blank`,
                                  { method: "PUT" })).json();
  ws = new WebSocket(alvo.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  ws.onmessage = (evento) => {
    const msg = JSON.parse(evento.data);
    const p = pendentes.get(msg.id);
    if (!p) return;
    pendentes.delete(msg.id);
    msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result);
  };
  await cdp("Page.enable");
  await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride",
            { width: 1280, height: 1000, deviceScaleFactor: 1, mobile: false });

  await cdp("Page.navigate", { url });
  await ate("document.body.dataset.pronto === 'sim'", "a página carregar");
  await avaliar("localStorage.clear(); window.confirm = () => true; true");
  await cdp("Page.navigate", { url });                       // recomeca sem rascunho
  await ate("document.body.dataset.pronto === 'sim'", "a página recarregar");
  await avaliar(`${AJUDANTES}; window.confirm = () => true; true`);
  relato.selo_inicial = await avaliar("__e2e.selo()");
  await capturar("1-vazia");

  // 1. recurso com nome invalido -> sugestao aceita
  await avaliar("document.querySelector('[data-adicionar=recurso]').click(); true");
  await avaliar("__e2e.digitar('nome', 'Álcool Gel'); true");
  await ate("document.querySelector('#campo-nome-erro button')", "a sugestão de nome aparecer");
  relato.erro_do_nome = await avaliar("document.getElementById('campo-nome-erro').textContent");
  await capturar("2-sugestao-de-nome");
  await avaliar("document.querySelector('#campo-nome-erro button').click(); true");
  await avaliar(`__e2e.digitar('capacidade', '6'); __e2e.digitar('custo_reposicao', '3');
                 __e2e.digitar('texto', 'solução alcoólica'); true`);
  relato.passos.push("recurso");

  // 2. preparo que consome o recurso
  await avaliar("document.querySelector('[data-adicionar=preparo]').click(); true");
  await avaliar(`__e2e.digitar('nome', 'higienizar-maos'); __e2e.digitar('estado', 'maos-higienizadas');
                 __e2e.digitar('custo', '2'); __e2e.escolher('consome', 'alcool-gel');
                 __e2e.marcar('exigido_antes_de', ['pressao','glicemia','temperatura','medicacao','antropometria']);
                 __e2e.digitar('texto', 'Higienizar as mãos'); true`);
  await ate("__e2e.selo().includes('válidas')", "as regras ficarem válidas");
  relato.previa_valida = await avaliar("__e2e.previa()");
  relato.baixar_habilitado = await avaliar("!document.getElementById('botao-baixar').disabled");
  await capturar("3-preparo-valido");
  relato.passos.push("preparo");

  // 3. renomear o recurso: o preparo acompanha
  await avaliar("__e2e.cartao('solução alcoólica').click(); true");
  await avaliar("__e2e.digitar('nome', 'alcool'); true");
  await ate("__e2e.previa().includes('consome = \"alcool\"')", "o preparo acompanhar a troca de nome");
  relato.previa_renomeada = await avaliar("__e2e.previa()");
  relato.passos.push("renomear");

  // 4. erro de proposito: capacidade 0
  await avaliar("__e2e.digitar('capacidade', '0'); true");
  await ate("__e2e.selo().includes('problema')", "o selo de problema aparecer");
  relato.selo_com_erro = await avaliar("__e2e.selo()");
  relato.problemas = await avaliar("[...document.querySelectorAll('#problemas li')].map(l => l.textContent)");
  relato.cartao_com_erro = await avaliar("Boolean(document.querySelector('.cartao--erro'))");
  relato.baixar_com_erro = await avaliar("!document.getElementById('botao-baixar').disabled");
  relato.erro_no_campo = await avaliar("document.getElementById('campo-capacidade-erro').textContent");
  await capturar("4-com-erro");
  relato.passos.push("erro");

  // 5. abrir um exemplo
  await avaliar(`(() => { const s = document.getElementById('exemplos');
                 s.value = 'sinteticas-ciclo2'; s.dispatchEvent(new Event('change')); return true; })()`);
  await ate("document.querySelectorAll('.cartao').length === 7", "o exemplo carregar (7 regras)");
  await ate("__e2e.selo().includes('válidas')", "o exemplo ser válido");
  relato.previa_exemplo = await avaliar("__e2e.previa()");
  await avaliar("__e2e.cartao('Conferir a proteção').click(); true");
  relato.quando_marcado = await avaliar("document.querySelector('input[name=quando]:checked').value");
  await capturar("5-exemplo-exigencia");
  relato.passos.push("exemplo");

  // 6. rascunho sobrevive ao recarregar
  await cdp("Page.navigate", { url });
  await ate("document.body.dataset.pronto === 'sim'", "recarregar");
  await ate("document.querySelectorAll('.cartao').length === 7", "o rascunho voltar");
  relato.passos.push("rascunho");

  // 7. tema escuro do sistema
  await cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  await avaliar("__e2e = undefined; true");
  await avaliar(`${AJUDANTES}; __e2e.cartao('Higienizar as mãos').click(); true`);
  relato.fundo_escuro = await avaliar("getComputedStyle(document.body).backgroundColor");
  await capturar("7-tema-escuro");
  await cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });

  // 8. tela estreita (celular)
  await cdp("Emulation.setDeviceMetricsOverride", { width: 390, height: 900, deviceScaleFactor: 1, mobile: true });
  relato.rolagem_horizontal = await avaliar("document.documentElement.scrollWidth > window.innerWidth");
  relato.altura_exemplos_celular = await avaliar("document.getElementById('exemplos').offsetHeight");
  await capturar("6-celular");
  relato.ok = true;
} catch (erro) {
  relato.ok = false;
  relato.erro = erro.message;
  try { await capturar("falha"); } catch {}
} finally {
  try { ws?.close(); } catch {}
  chrome.kill();
  await esperar(300);
  rmSync(perfil, { recursive: true, force: true });
}
console.log(JSON.stringify(relato));
process.exit(0);
