// Teste de ponta a ponta do mapa, num Chrome sem janela.
//
//   CHROME=google-chrome node web/testes/e2e-mapa.mjs URL_DO_SERVIDOR PASTA_DAS_CAPTURAS
//
// As imagens das ruas (OpenStreetMap) ficam bloqueadas: o teste nao depende
// da internet e confere que, sem elas, a tela cai para o desenho simples.
// Defina MAPA_COM_RUAS=1 para deixar as ruas carregarem (so para olhar).

import { rodarCenario } from "./navegador.mjs";

const PRAZO_PLANEJAR = 150_000;

await rodarCenario(async ({ avaliar, ate, capturar, abrir, largura, temaEscuro, bloquear, url, relato }) => {
  const aba = (nome) => avaliar(`document.getElementById('aba-${nome}').click(); true`);
  const conta = (seletor) => avaliar(`document.querySelectorAll(${JSON.stringify(seletor)}).length`);
  const texto = (seletor) => avaliar(`document.querySelector(${JSON.stringify(seletor)})?.textContent ?? null`);
  if (!process.env.MAPA_COM_RUAS) await bloquear(["*tile.openstreetmap.org*"]);

  await abrir(url);
  await avaliar("localStorage.clear(); true");
  await abrir(`${new URL(url).origin}/#mapa`);

  // 1. sem roteiro: convite para planejar
  relato.vazio_visivel = await avaliar("!document.getElementById('mapa-vazio').classList.contains('oculto')");

  // 2. planejar 5 pacientes da avaliacao com as regras sinteticas
  await aba("regras");
  await avaliar(`(() => { const s = document.getElementById('exemplos');
                 s.value = 'sinteticas-ciclo2'; s.dispatchEvent(new Event('change')); return true; })()`);
  await ate("document.getElementById('estado-regras').textContent.includes('válidas')", "as regras valerem");
  await avaliar("document.getElementById('mapa-ir-planejar') && true");
  await aba("planejar");
  await avaliar(`(() => { const f = document.getElementById('pedido').elements;
                 f.exemplo.value = 'avaliacao'; f.max_pacientes.value = '5';
                 f.exemplo.dispatchEvent(new Event('change', { bubbles: true }));
                 document.getElementById('botao-planejar').click(); return true; })()`);
  await ate("document.getElementById('resultado').dataset.estado === 'roteiro' && " +
            "!document.getElementById('botao-planejar').disabled", "o roteiro ficar pronto", PRAZO_PLANEJAR);
  // passagens pela UBS que viram trecho a mais (antes da 1a visita, ja esta na UBS)
  relato.desvios = await avaliar(`[...document.querySelectorAll('#resultado .parada:not(.parada--ubs)')]
    .slice(1).filter((p) => p.querySelector('.parada__desvio')).length`);
  await avaliar("document.getElementById('ver-no-mapa').click(); true");
  relato.endereco = await avaliar("location.hash");

  // 3. mapa de ruas (Leaflet): marcadores e linhas, mesmo sem as imagens
  await ate("document.querySelectorAll('#mapa .leaflet-marker-icon').length > 0", "os marcadores aparecerem");
  relato.modo_inicial = await avaliar("document.getElementById('mapa').dataset.modo");
  relato.marcadores = await conta("#mapa .leaflet-marker-icon");
  relato.linhas_e_adiados = await conta("#mapa .leaflet-overlay-pane path");
  relato.resumo = await texto("#mapa-resumo");
  relato.itens_lista = await conta("#mapa-lista .ponto");
  await avaliar("document.querySelector('#mapa-lista [data-ponto=\"3\"]').click(); true");
  await ate("document.querySelector('.leaflet-popup-content')", "o balão da visita 3 abrir");
  relato.balao = await texto(".leaflet-popup-content");
  if (process.env.MAPA_COM_RUAS) await new Promise((r) => setTimeout(r, 4000));   // imagens das ruas
  await capturar("m1-ruas");
  relato.passos.push("ruas");

  if (!process.env.MAPA_COM_RUAS) {
    // 4. as ruas nao carregam: cai para o desenho simples, com aviso
    await ate("document.getElementById('mapa').dataset.modo === 'desenho'", "cair para o desenho", 9000);
    relato.aviso = await texto("#mapa-aviso");
    relato.radio_desenho = await avaliar("document.querySelector('input[name=modo-mapa][value=desenho]').checked");
    relato.svg_pontos = await conta("#mapa svg .svg-ponto");
    relato.svg_trechos = await conta("#mapa svg .svg-trecho");
    relato.svg_desvios = await conta("#mapa svg .svg-trecho--desvio");
    relato.escala = await texto("#mapa svg .svg-escala text");
    await avaliar("document.querySelector('#mapa-lista [data-ponto=\"2\"]').click(); true");
    relato.svg_destacado = await avaliar(
      "document.querySelector('#mapa svg .svg-ponto--ativo title')?.textContent ?? null");
    await capturar("m2-desenho");
    relato.passos.push("desenho");

    // 5. tema escuro e celular
    await temaEscuro(true);
    await esperarQuadro();
    await capturar("m3-desenho-escuro");
    await temaEscuro(false);
    await largura(390, 900, true);
    relato.rolagem_horizontal = await avaliar("document.documentElement.scrollWidth > window.innerWidth");
    await capturar("m4-celular");
    relato.passos.push("aparencia");
  }

  async function esperarQuadro() {
    await avaliar("new Promise(r => requestAnimationFrame(() => r(true)))");
  }
});
