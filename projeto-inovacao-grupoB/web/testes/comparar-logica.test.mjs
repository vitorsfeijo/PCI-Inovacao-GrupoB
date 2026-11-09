// node --test web/testes/*.test.mjs   (ou: python3 acs.py testes, que roda isto se houver Node)
import { test } from "node:test";
import assert from "node:assert/strict";
import { compararResultados, diferencaDeTarefas, variacao } from "../js/comparar-logica.js";

test("diferença de tarefas: novas na ordem do depois, as que saíram no fim", () => {
  assert.deepEqual(diferencaDeTarefas(["A", "B", "C"], ["A", "H", "B", "C"]), [
    { texto: "A", tipo: "igual" }, { texto: "H", tipo: "nova" },
    { texto: "B", tipo: "igual" }, { texto: "C", tipo: "igual" }]);
  assert.deepEqual(diferencaDeTarefas(["A", "B"], ["B"]), [
    { texto: "B", tipo: "igual" }, { texto: "A", tipo: "saiu" }]);
  // repetidas contam como várias
  assert.deepEqual(diferencaDeTarefas(["H"], ["H", "H"]).map((l) => l.tipo), ["igual", "nova"]);
});

const paciente = (id) => ({ id, nome: `Paciente ${id}` });
const parada = (ordem, id, inicio, tarefas, repor = []) =>
  ({ ordem, paciente: paciente(id), inicio_min: inicio, tarefas, desvio_ubs: repor.length > 0, repor });

const ANTES = {
  rota: ["ubs", "p2", "p8", "ubs"], custo_total: 240, orcamento: 260,
  paradas: [parada(1, "p2", 19, ["PA", "Registrar"]),
            parada(2, "p8", 142, ["Glicemia", "Registrar"], ["fitas de glicemia"])],
};
const DEPOIS = {
  rota: ["ubs", "p2", "p8", "ubs"], custo_total: 279, orcamento: 260,
  paradas: [parada(1, "p2", 21, ["Higienizar", "PA", "Registrar"]),
            parada(2, "p8", 150, ["Higienizar", "Glicemia", "Registrar"],
                   ["fitas de glicemia", "coletor"])],
};

test("comparação dos dois turnos", () => {
  const c = compararResultados(ANTES, DEPOIS);
  assert.equal(c.mesmaRota, true);
  assert.deepEqual(c.minutos, { antes: 240, depois: 279, diferenca: 39, percentual: 16 });
  assert.deepEqual(c.tarefas, { antes: 4, depois: 6 });
  assert.deepEqual(c.passagens, { antes: 1, depois: 1 });
  assert.equal(c.orcamento, 260);
  assert.deepEqual(c.novas, [{ texto: "Higienizar", vezes: 2 }]);
  assert.deepEqual(c.sairam, []);
  assert.deepEqual(c.reposicoes, [{ texto: "coletor", vezes: 1, antes: 0 },
                                  { texto: "fitas de glicemia", vezes: 1, antes: 1 }]);
  assert.equal(c.paradas[1].atraso, 8);
  assert.equal(c.paradas[1].desvioAntes, true);
  assert.deepEqual(c.paradas[0].tarefas.map((t) => t.tipo), ["nova", "igual", "igual"]);
});

test("parada que não existia antes e rota diferente", () => {
  const depois = { ...DEPOIS, rota: ["ubs", "p8", "p9", "ubs"],
                   paradas: [...DEPOIS.paradas, parada(3, "p9", 200, ["PA"])] };
  const c = compararResultados(ANTES, depois);
  assert.equal(c.mesmaRota, false);
  assert.equal(c.paradas[2].chegadaAntes, null);
  assert.equal(c.paradas[2].atraso, null);
  assert.deepEqual(c.paradas[2].tarefas, [{ texto: "PA", tipo: "nova" }]);
});

test("variação legível", () => {
  assert.equal(variacao(37, 15), "+37 min (+15%)");
  assert.equal(variacao(-5, -2), "−5 min (−2%)");
  assert.equal(variacao(0, 0), "sem diferença");
  assert.equal(variacao(2, null, ""), "+2");
});
