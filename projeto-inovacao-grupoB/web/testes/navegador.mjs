// Um Chrome sem janela, controlado pelo protocolo de depuracao (CDP), para os
// testes de ponta a ponta. Sem dependencias: o WebSocket vem no Node 22.

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

export async function abrirNavegador(pastaCapturas) {
  const perfil = mkdtempSync(join(tmpdir(), "acs-e2e-"));
  const chrome = spawn(process.env.CHROME || "google-chrome", [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    `--user-data-dir=${perfil}`, "--remote-debugging-port=0", "about:blank",
  ], { stdio: "ignore" });

  let ws;
  let seq = 0;
  const pendentes = new Map();
  const errosDaPagina = [];          // excecoes de JavaScript nao tratadas

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

  async function abrir(url) {
    await cdp("Page.navigate", { url });
    await ate("document.body.dataset.pronto === 'sim'", `a página ${url} carregar`);
  }

  async function largura(largura, altura, celular = false) {
    await cdp("Emulation.setDeviceMetricsOverride",
              { width: largura, height: altura, deviceScaleFactor: 1, mobile: celular });
  }

  async function temaEscuro(escuro) {
    await cdp("Emulation.setEmulatedMedia",
              { features: [{ name: "prefers-color-scheme", value: escuro ? "dark" : "light" }] });
  }

  // URLs que nao devem carregar (ex.: as imagens das ruas, para simular sem internet)
  async function bloquear(padroes) {
    await cdp("Network.setBlockedURLs", { urls: padroes });
  }

  async function fechar() {
    try { ws?.close(); } catch {}
    chrome.kill();
    await esperar(300);
    rmSync(perfil, { recursive: true, force: true });
  }

  try {
    const arquivo = join(perfil, "DevToolsActivePort");
    for (let i = 0; i < 100 && !existsSync(arquivo); i++) await esperar(100);
    if (!existsSync(arquivo)) throw new Error("o Chrome não abriu a porta de depuração");
    const porta = readFileSync(arquivo, "utf8").split("\n")[0];
    const alvo = await (await fetch(`http://127.0.0.1:${porta}/json/new?about:blank`,
                                    { method: "PUT" })).json();
    ws = new WebSocket(alvo.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
    ws.onmessage = (evento) => {
      const msg = JSON.parse(evento.data);
      if (msg.method === "Runtime.exceptionThrown") {
        const d = msg.params.exceptionDetails;
        errosDaPagina.push(d.exception?.description ?? d.text);
      }
      const p = pendentes.get(msg.id);
      if (!p) return;
      pendentes.delete(msg.id);
      msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result);
    };
    await cdp("Page.enable");
    await cdp("Runtime.enable");
    await cdp("Network.enable");
    // o que a politica de conteudo (CSP) do servidor bloquear fica anotado
    await cdp("Page.addScriptToEvaluateOnNewDocument", { source: `
      window.__violacoes = [];
      document.addEventListener('securitypolicyviolation',
        (e) => window.__violacoes.push(e.violatedDirective + ' ' + e.blockedURI));` });
    await largura(1280, 1000);
  } catch (erro) {
    await fechar();
    throw erro;
  }
  return { cdp, avaliar, ate, capturar, abrir, largura, temaEscuro, bloquear, fechar, errosDaPagina };
}

// Roda um cenario e imprime o relato em JSON (lido por backend/testes/test_web.py).
export async function rodarCenario(cenario) {
  const [url, pastaCapturas] = process.argv.slice(2);
  const relato = { passos: [] };
  let navegador;
  try {
    navegador = await abrirNavegador(pastaCapturas);
    await cenario({ ...navegador, url, relato });
    relato.violacoes_csp = await navegador.avaliar("window.__violacoes ?? []");
    relato.erros_da_pagina = navegador.errosDaPagina;
    relato.ok = true;
  } catch (erro) {
    relato.ok = false;
    relato.erro = erro.message;
    try { await navegador?.capturar("falha"); } catch {}
  } finally {
    await navegador?.fechar();
  }
  console.log(JSON.stringify(relato));
  process.exit(0);
}
