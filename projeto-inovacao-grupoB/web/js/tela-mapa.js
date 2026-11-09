// Tela do mapa: a rota do ultimo roteiro planejado. Com internet, sobre o
// mapa de ruas do OpenStreetMap (Leaflet, em web/vendor/); sem internet, ou
// se a pessoa preferir, um desenho simples em SVG com os mesmos pontos.
// A logica sem DOM fica em mapa-logica.js.

import { adiar, el } from "./dom.js";
import {
  barraDeEscala, distanciaKm, pontosDoMapa, projetar, resumoDaRota, textoKm, trechosDaRota,
} from "./mapa-logica.js";
import { duracao, horario, rotuloGrupo } from "./planejar-logica.js";

const RUAS = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATRIBUICAO = '&copy; <a href="https://www.openstreetmap.org/copyright">colaboradores do OpenStreetMap</a>';
const ESPERA_RUAS_MS = 5000;     // sem nenhuma imagem de rua nesse tempo: desenho simples
const SVG = "http://www.w3.org/2000/svg";

function svg(tag, atributos = {}, ...filhos) {
  const elemento = document.createElementNS(SVG, tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (valor !== undefined && valor !== null) elemento.setAttribute(chave, valor);
  }
  for (const filho of filhos.flat()) {
    if (filho === null || filho === undefined) continue;
    elemento.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
  }
  return elemento;
}

function cor(variavel) {
  return getComputedStyle(document.documentElement).getPropertyValue(variavel).trim();
}

export class TelaMapa {
  constructor(raiz, { irPara }) {
    this.raiz = raiz;
    this.ultimo = null;            // { resultado, inicio }
    this.modo = "ruas";            // "ruas" ou "desenho"
    this.mapa = null;              // Leaflet, quando no modo ruas
    this.marcadores = new Map();   // ordem (ou "ubs") -> marcador Leaflet / elemento SVG
    this.$ = (seletor) => raiz.querySelector(seletor);
    this.$("#mapa-ir-planejar").addEventListener("click", () => irPara("planejar"));
    for (const opcao of raiz.querySelectorAll("input[name=modo-mapa]")) {
      opcao.addEventListener("change", () => {
        this.aviso("");
        this.modo = opcao.value;
        this.desenhar();
      });
    }
    window.matchMedia("(prefers-color-scheme: dark)")
      .addEventListener?.("change", () => this.desenhar());
    // o desenho simples usa o tamanho real da caixa: redesenha se ela mudar
    const redesenhar = adiar(() => {
      if (this.modo === "desenho" && this.ultimo && !this.raiz.classList.contains("oculto")) {
        this.desenhar();
      }
    }, 200);
    let tamanho = "";
    new ResizeObserver(([entrada]) => {
      const novo = `${Math.round(entrada.contentRect.width)}x${Math.round(entrada.contentRect.height)}`;
      if (novo !== tamanho) {
        tamanho = novo;
        redesenhar();
      }
    }).observe(this.$("#mapa"));
  }

  // Chamado quando um roteiro novo fica pronto na tela de planejamento.
  mostrar(ultimo) {
    this.ultimo = ultimo;
    this.precisaDesenhar = true;
    if (!this.raiz.classList.contains("oculto")) this.desenhar();
  }

  // Chamado quando a aba aparece (o Leaflet precisa do tamanho visivel).
  aoAparecer() {
    if (this.precisaDesenhar) this.desenhar();
    else this.mapa?.invalidateSize();
  }

  aviso(texto) {
    const caixa = this.$("#mapa-aviso");
    caixa.textContent = texto;
    caixa.classList.toggle("oculto", !texto);
  }

  // ---- desenho ------------------------------------------------------------

  desenhar() {
    this.precisaDesenhar = false;
    const temRoteiro = Boolean(this.ultimo);
    this.$("#mapa-vazio").classList.toggle("oculto", temRoteiro);
    this.$("#mapa-conteudo").classList.toggle("oculto", !temRoteiro);
    if (!temRoteiro) return;
    if (this.modo === "ruas" && (typeof window.L === "undefined" || navigator.onLine === false)) {
      this.cairParaDesenho("Sem internet: mostrando um desenho simples, sem as ruas.");
      return;
    }
    this.$(`input[name=modo-mapa][value=${this.modo}]`).checked = true;
    this.desenharLista();
    this.desenharResumo();
    this.limparMapa();
    if (this.modo === "ruas") this.desenharRuas();
    else this.desenharSimples();
    this.$("#mapa").dataset.modo = this.modo;                    // usado pelos testes
  }

  cairParaDesenho(motivo) {
    this.modo = "desenho";
    this.desenhar();
    this.aviso(motivo);
  }

  limparMapa() {
    this.mapa?.remove();
    this.mapa = null;
    clearTimeout(this.relogioRuas);
    this.marcadores.clear();
    this.$("#mapa").replaceChildren();
    this.$("#mapa").className = "mapa";
  }

  desenharResumo() {
    const r = this.ultimo.resultado;
    const rota = resumoDaRota(r);
    this.$("#mapa-resumo").textContent =
      `${r.paradas.length} visitas · ${textoKm(rota.km)} a pé em linha reta` +
      (rota.desvios ? ` (+${textoKm(rota.kmAMaisPelaUbs)} por ${rota.desvios === 1 ? "1 passagem" : `${rota.desvios} passagens`} pela UBS)` : "") +
      ` · ${duracao(r.custo_total)} de turno`;
  }

  desenharLista() {
    const r = this.ultimo.resultado;
    const { ubs, visitas, adiados } = pontosDoMapa(r);
    const hora = (min) => horario(this.ultimo.inicio, min) ?? `${min} min`;
    const item = (chave, numero, titulo, detalhe, classe = "") =>
      el("li", {},
        el("button", { type: "button", class: `ponto ${classe}`, "data-ponto": chave,
                       onclick: () => this.destacar(chave) },
          el("span", { class: "ponto__numero" }, numero),
          el("span", {}, el("strong", {}, titulo), el("small", {}, detalhe))));
    this.$("#mapa-lista").replaceChildren(
      item("ubs", "U", ubs.nome, `saída ${hora(0)} · volta ≈ ${hora(r.custo_total)}`, "ponto--ubs"),
      ...visitas.map((v) => item(String(v.parada.ordem), String(v.parada.ordem), v.nome,
        [`chegada ≈ ${hora(v.parada.inicio_min)}`, `${v.parada.tarefas.length} tarefas`,
         v.parada.desvio_ubs ? "passa na UBS antes" : null].filter(Boolean).join(" · "),
        v.parada.desvio_ubs ? "ponto--desvio" : "")),
      ...(adiados.length
        ? [el("li", { class: "mapa__subtitulo" }, "Ficam para outro turno"),
           ...adiados.map((p) => item(`adiado-${p.id}`, "–", p.nome, rotuloGrupo(p.grupo), "ponto--adiado"))]
        : []));
  }

  destacar(chave) {
    for (const botao of this.raiz.querySelectorAll(".ponto")) {
      botao.classList.toggle("ponto--ativo", botao.dataset.ponto === chave);
    }
    const alvo = this.marcadores.get(chave);
    if (!alvo) return;
    if (this.modo === "ruas") {
      this.mapa.setView(alvo.getLatLng(), Math.max(this.mapa.getZoom(), 16), { animate: false });
      alvo.openPopup();
    } else {
      for (const g of this.$("#mapa").querySelectorAll(".svg-ponto--ativo")) {
        g.classList.remove("svg-ponto--ativo");
      }
      alvo.classList.add("svg-ponto--ativo");
    }
  }

  popup(chave) {
    const r = this.ultimo.resultado;
    const hora = (min) => horario(this.ultimo.inicio, min) ?? `${min} min de turno`;
    if (chave === "ubs") {
      return el("div", {}, el("strong", {}, r.pontos[r.rota[0]].nome),
                el("div", {}, `saída ${hora(0)} · volta ≈ ${hora(r.custo_total)}`));
    }
    const parada = r.paradas.find((p) => String(p.ordem) === chave);
    return el("div", { class: "popup" },
      el("strong", {}, `${parada.ordem}. ${parada.paciente.nome}`),
      parada.paciente.grupo ? el("span", {}, ` · ${rotuloGrupo(parada.paciente.grupo)}`) : null,
      el("div", {}, `chegada ≈ ${hora(parada.inicio_min)}`),
      parada.desvio_ubs
        ? el("div", { class: "popup__desvio" }, "Passar na UBS antes desta visita" +
             (parada.repor.length ? `: repor ${parada.repor.join(", ")}` : ""))
        : null,
      el("ul", {}, parada.tarefas.map((t) => el("li", {}, t))));
  }

  // ---- modo ruas (Leaflet + OpenStreetMap) --------------------------------

  desenharRuas() {
    const L = window.L;
    const r = this.ultimo.resultado;
    const { ubs, visitas, adiados } = pontosDoMapa(r);
    const caixa = this.$("#mapa");
    caixa.classList.add("mapa--ruas");
    this.mapa = L.map(caixa, { zoomSnap: 0.5 });
    let carregou = false;
    const ruas = L.tileLayer(RUAS, { maxZoom: 19, attribution: ATRIBUICAO });
    ruas.on("tileload", () => { carregou = true; });
    ruas.addTo(this.mapa);
    this.relogioRuas = setTimeout(() => {
      if (!carregou && this.modo === "ruas") {
        this.cairParaDesenho("As imagens das ruas não carregaram (sem internet?): " +
                             "mostrando um desenho simples.");
      }
    }, ESPERA_RUAS_MS);

    const destaque = cor("--destaque");
    const aviso = cor("--aviso");
    const linha = (t) => L.polyline([[t.de.lat, t.de.lon], [t.para.lat, t.para.lon]], {
      color: t.tipo === "desvio" ? aviso : destaque, weight: 4, opacity: 0.85,
      dashArray: t.tipo === "desvio" ? "8 8" : null,
    }).addTo(this.mapa);
    trechosDaRota(r).forEach(linha);

    for (const p of adiados) {
      L.circleMarker([p.lat, p.lon], { radius: 6, color: cor("--texto-suave"), weight: 2,
                                        fillOpacity: 0.3 })
        .bindTooltip(`${p.nome} (fica para outro turno)`).addTo(this.mapa);
    }
    const icone = (texto, classe) => L.divIcon({
      className: `marcador ${classe}`, html: texto, iconSize: [28, 28], iconAnchor: [14, 14],
      popupAnchor: [0, -14] });
    const marcar = (chave, ponto, texto, classe) => {
      const m = L.marker([ponto.lat, ponto.lon], { icon: icone(texto, classe), title: ponto.nome })
        .bindPopup(() => this.popup(chave)).addTo(this.mapa);
      m.on("click", () => this.destacar(chave));
      this.marcadores.set(chave, m);
    };
    marcar("ubs", ubs, "U", "marcador--ubs");
    for (const v of visitas) {
      marcar(String(v.parada.ordem), v, String(v.parada.ordem),
             v.parada.desvio_ubs ? "marcador--desvio" : "");
    }
    const todos = [ubs, ...visitas, ...adiados].map((p) => [p.lat, p.lon]);
    this.mapa.fitBounds(todos, { padding: [30, 30] });
  }

  // ---- modo desenho (SVG, sem internet) ------------------------------------

  desenharSimples() {
    const r = this.ultimo.resultado;
    const { ubs, visitas, adiados } = pontosDoMapa(r);
    const caixa = this.$("#mapa");
    caixa.classList.add("mapa--desenho");
    const largura = Math.max(caixa.clientWidth, 200) || 800;     // pixels reais da caixa
    const altura = Math.max(caixa.clientHeight, 200) || 560;
    const xy = projetar([ubs, ...visitas, ...adiados], largura, altura, Math.min(40, largura / 10));

    const trechos = trechosDaRota(r).map((t) => {
      const a = xy(t.de);
      const b = xy(t.para);
      return svg("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: `svg-trecho svg-trecho--${t.tipo}` });
    });
    const ponto = (chave, p, texto, classe, titulo) => {
      const { x, y } = xy(p);
      const g = svg("g", { class: `svg-ponto ${classe}`, transform: `translate(${x} ${y})`,
                           tabindex: "0", role: "button", "aria-label": titulo },
        svg("title", {}, titulo),
        classe.includes("ubs") ? svg("rect", { x: -14, y: -14, width: 28, height: 28, rx: 4 })
          : classe.includes("adiado") ? svg("circle", { r: 6 })
          : svg("circle", { r: 14 }),
        texto ? svg("text", { "text-anchor": "middle", dy: "0.35em" }, texto) : null);
      g.addEventListener("click", () => this.destacar(chave));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") this.destacar(chave); });
      this.marcadores.set(chave, g);
      return g;
    };

    // barra de escala a partir de dois pontos distantes
    const outro = visitas.at(-1) ?? adiados[0];
    let escala = null;
    if (outro) {
      const a = xy(ubs);
      const b = xy(outro);
      const px = Math.hypot(a.x - b.x, a.y - b.y);
      if (px > 0) {
        const barra = barraDeEscala(distanciaKm(ubs, outro) / px);
        escala = svg("g", { class: "svg-escala", transform: `translate(20 ${altura - 20})` },
          svg("line", { x1: 0, y1: 0, x2: barra.px, y2: 0 }),
          svg("line", { x1: 0, y1: -5, x2: 0, y2: 5 }),
          svg("line", { x1: barra.px, y1: -5, x2: barra.px, y2: 5 }),
          svg("text", { x: barra.px / 2, y: -8, "text-anchor": "middle" }, barra.texto));
      }
    }

    caixa.append(svg("svg", { viewBox: `0 0 ${largura} ${altura}`, role: "img",
                              "aria-label": "Desenho da rota do turno" },
      svg("text", { x: largura - 20, y: 28, "text-anchor": "end", class: "svg-norte" }, "N ↑"),
      trechos,
      adiados.map((p) => ponto(`adiado-${p.id}`, p, null, "svg-ponto--adiado",
                               `${p.nome} (fica para outro turno)`)),
      ponto("ubs", ubs, "U", "svg-ponto--ubs", ubs.nome),
      visitas.map((v) => ponto(String(v.parada.ordem), v, String(v.parada.ordem),
                               v.parada.desvio_ubs ? "svg-ponto--desvio" : "",
                               `${v.parada.ordem}. ${v.nome}`)),
      escala));
  }
}
