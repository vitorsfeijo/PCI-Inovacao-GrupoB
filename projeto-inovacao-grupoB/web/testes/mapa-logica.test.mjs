// node --test web/testes/*.test.mjs   (ou: python3 acs.py testes, que roda isto se houver Node)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  barraDeEscala, distanciaKm, pontosDoMapa, projetar, resumoDaRota, textoKm, trechosDaRota,
} from "../js/mapa-logica.js";

const UBS = { id: "ubs", nome: "UBS", lat: -30.0397, lon: -51.2189 };
const P = {
  p1: { id: "p1", nome: "Ana", lat: -30.0362, lon: -51.2141 },
  p2: { id: "p2", nome: "Bia", lat: -30.0341, lon: -51.2203 },
  p3: { id: "p3", nome: "Caio", lat: -30.0450, lon: -51.2100 },
};
const parada = (ordem, id, desvio = false) =>
  ({ ordem, paciente: { id }, inicio_min: ordem * 30, tarefas: [], desvio_ubs: desvio, repor: [] });
const RESULTADO = {
  rota: ["ubs", "p1", "p2", "ubs"],
  pontos: { ubs: UBS, ...P },
  selecao: { selecionados: ["p1", "p2"], adiados: ["p3"] },
  paradas: [parada(1, "p1"), parada(2, "p2", true)],
};

test("distância em linha reta", () => {
  assert.equal(distanciaKm(UBS, UBS), 0);
  // 1 grau de latitude ~ 111 km
  assert.ok(Math.abs(distanciaKm({ lat: 0, lon: 0 }, { lat: 1, lon: 0 }) - 111.19) < 0.1);
  const km = distanciaKm(UBS, P.p1);
  assert.ok(km > 0.5 && km < 0.7, km);
});

test("trechos: saída, visitas, desvio pela UBS e retorno", () => {
  const trechos = trechosDaRota(RESULTADO);
  assert.deepEqual(trechos.map((t) => [t.de.id, t.para.id, t.tipo]), [
    ["ubs", "p1", "visita"],
    ["p1", "ubs", "desvio"], ["ubs", "p2", "desvio"],
    ["p2", "ubs", "retorno"],
  ]);
  // desvio na primeira visita: ja esta na UBS, entao e um trecho so
  const primeira = trechosDaRota({ ...RESULTADO, paradas: [parada(1, "p1", true)] });
  assert.deepEqual(primeira.map((t) => t.tipo), ["visita", "retorno"]);
});

test("resumo da rota", () => {
  const r = resumoDaRota(RESULTADO);
  assert.equal(r.desvios, 1);
  const aMais = distanciaKm(P.p1, UBS) + distanciaKm(UBS, P.p2) - distanciaKm(P.p1, P.p2);
  assert.ok(Math.abs(r.kmAMaisPelaUbs - aMais) < 1e-9);
  assert.ok(Math.abs(r.km - (distanciaKm(UBS, P.p1) + aMais + distanciaKm(P.p1, P.p2) +
                             distanciaKm(P.p2, UBS))) < 1e-9);
  assert.equal(textoKm(2.44), "2,4 km");
  assert.equal(textoKm(0.437), "440 m");
});

test("pontos do mapa trazem as visitas com a parada e os adiados", () => {
  const { ubs, visitas, adiados } = pontosDoMapa(RESULTADO);
  assert.equal(ubs.nome, "UBS");
  assert.deepEqual(visitas.map((v) => [v.nome, v.parada.ordem]), [["Ana", 1], ["Bia", 2]]);
  assert.deepEqual(adiados.map((p) => p.nome), ["Caio"]);
});

test("projeção cabe na área, mantém o norte para cima e a proporção", () => {
  const pontos = [UBS, ...Object.values(P)];
  const xy = projetar(pontos, 800, 560, 40);
  for (const p of pontos) {
    const { x, y } = xy(p);
    assert.ok(x >= 39.9 && x <= 760.1 && y >= 39.9 && y <= 520.1, `${p.id}: ${x},${y}`);
  }
  assert.ok(xy(P.p2).y < xy(P.p3).y);          // p2 fica mais ao norte que p3
  assert.ok(xy(P.p3).x > xy(P.p2).x);          // e p3 mais a leste
  // mesma escala nos dois eixos (em km): distâncias proporcionais
  const px = (a, b) => Math.hypot(xy(a).x - xy(b).x, xy(a).y - xy(b).y);
  const razao1 = px(UBS, P.p1) / distanciaKm(UBS, P.p1);
  const razao2 = px(P.p2, P.p3) / distanciaKm(P.p2, P.p3);
  assert.ok(Math.abs(razao1 / razao2 - 1) < 0.01, `${razao1} x ${razao2}`);
  // um ponto só: vai para o centro
  assert.deepEqual(projetar([UBS], 100, 100, 10)(UBS), { x: 50, y: 50 });
});

test("barra de escala redonda", () => {
  assert.deepEqual(barraDeEscala(0.005, 120), { km: 0.5, px: 100, texto: "500 m" });
  assert.equal(barraDeEscala(0.01, 120).texto, "1 km");
});
