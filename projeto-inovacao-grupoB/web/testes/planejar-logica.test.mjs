// node --test web/testes/*.test.mjs   (ou: python3 acs.py testes, que roda isto se houver Node)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  duracao, explicarFalha, horario, pedidoDe, resumoDoResultado, rotuloGrupo, ubsDo,
} from "../js/planejar-logica.js";

const BASE = { fonte: "exemplo", exemplo: "avaliacao", estrategia: "padrao",
               planejador: "padrao", metodo: "padrao" };

test("pedido mínimo: planilha de exemplo, sem regras nem opções", () => {
  assert.deepEqual(pedidoDe(BASE), { planilha: { exemplo: "avaliacao" } });
  assert.deepEqual(pedidoDe({ ...BASE, exemplo: "" }), { planilha: { exemplo: "exemplo-ciclo2" } });
});

test("pedido completo vira as opções da API", () => {
  const pedido = pedidoDe({
    ...BASE, regras_toml: "[[recurso]]\n", orcamento: "480", max_pacientes: " 6 ",
    limite: "30,5", semente: "", estrategia: "janelas", planejador: "ciclo2", metodo: "nn2opt",
    sem_selecao: true, sem_precedencia: false, sem_limpeza: true,
  });
  assert.deepEqual(pedido, {
    regras_toml: "[[recurso]]\n",
    planilha: { exemplo: "avaliacao" },
    opcoes: { orcamento: 480, max_pacientes: 6, limite: 30.5, estrategia: "janelas",
              planejador: "ciclo2", metodo: "nn2opt", sem_selecao: true, sem_limpeza: true },
  });
});

test("planilha enviada e pacientes inventados", () => {
  assert.deepEqual(pedidoDe({ ...BASE, fonte: "csv", csv: "id,nome\n" }).planilha, { csv: "id,nome\n" });
  assert.throws(() => pedidoDe({ ...BASE, fonte: "csv", csv: null }), /Escolha o arquivo/);
  assert.throws(() => pedidoDe({ ...BASE, fonte: "csv", csv: "x".repeat(2_000_001) }), /2 MB/);
  assert.deepEqual(pedidoDe({ ...BASE, fonte: "sintetica", pacientes_sinteticos: "4",
                              semente_sintetica: "" }).planilha, { sintetica: [4, 0] });
  assert.throws(() => pedidoDe({ ...BASE, fonte: "sintetica", pacientes_sinteticos: "0" }), /pelo menos 1/);
});

test("números inválidos são recusados antes de ir ao servidor", () => {
  assert.throws(() => pedidoDe({ ...BASE, orcamento: "4h" }), /Duração|Tempo do turno/);
  assert.throws(() => pedidoDe({ ...BASE, max_pacientes: "2.5" }), /Máximo de pacientes/);
  assert.throws(() => pedidoDe({ ...BASE, limite: "-1" }), /Limite/);
});

test("tempos legíveis", () => {
  assert.equal(duracao(45), "45 min");
  assert.equal(duracao(60), "1h00");
  assert.equal(duracao(432), "7h12");
  assert.equal(horario("08:00", 25), "08:25");
  assert.equal(horario("7:30", 432), "14:42");
  assert.equal(horario("23:50", 20), "00:10");
  assert.equal(horario("", 25), null);
});

const RESULTADO = {
  codigo: 0, regras: "regras.toml", avisos: [], orcamento: 400, custo_total: 432,
  selecao: { selecionados: ["p1", "p2"], adiados: ["p3"] },
  rota: ["ubs", "p2", "p1", "ubs"],
  pontos: { ubs: { id: "ubs", nome: "UBS Centro" }, p1: { id: "p1", nome: "Ana" },
            p2: { id: "p2", nome: "Bia" }, p3: { id: "p3", nome: "Caio", grupo: "pessoa_idosa" } },
  busca: { planejador: "Fast Downward", metodo: "janelas (k=3)", otimo: false, segundos: 12.34 },
  paradas: [{ ordem: 1, desvio_ubs: false }, { ordem: 2, desvio_ubs: true }],
};

test("resumo do roteiro", () => {
  const r = resumoDoResultado(RESULTADO);
  assert.equal(r.visitas, 2);
  assert.equal(r.duracao, "7h12");
  assert.equal(r.passagensUbs, 1);
  assert.deepEqual(r.adiados.map((p) => p.nome), ["Caio"]);
  assert.equal(r.folga, -32);
  assert.equal(r.busca, "Fast Downward · janelas (k=3) · sem garantia de ser ótimo · 12,3 s");
  assert.equal(resumoDoResultado({ ...RESULTADO, orcamento: null }).folga, null);
  assert.equal(ubsDo(RESULTADO).nome, "UBS Centro");
  assert.equal(rotuloGrupo("pessoa_idosa"), "pessoa idosa");
});

test("falhas explicadas pelo tipo", () => {
  const com = (tipo, mensagens) => ({ estado: "pronta", resultado: { codigo: 1, falha: { tipo, mensagens } } });
  assert.match(explicarFalha(com("interrompida", ["parou", "Motivo informado: x"])).dica,
               /não quer dizer que o turno é impossível/);
  assert.match(explicarFalha(com("impossivel", ["nenhuma"])).titulo, /Nenhum roteiro/);
  const erro = explicarFalha(com("erro", ["a planilha não tem a coluna x", "outra"]));
  assert.equal(erro.itens.length, 2);
  assert.match(explicarFalha({ estado: "erro", erro: "KeyError: x" }).titulo, /inesperado/);
});
