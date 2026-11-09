// node --test web/testes/*.test.mjs   (ou: python3 acs.py testes, que roda isto se houver Node)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  blocoLimpo, dadosParaApi, estadoDe, problemasDaRegra, propagarNome, quemUsa,
  regraNova, resumo, textoPadrao, valorDoCampo,
} from "../js/regras-logica.js";

const SINTETICAS = {
  recurso: [{ nome: "alcool", capacidade: 6, custo_reposicao: 3 },
            { nome: "coletor", capacidade: 3, custo_reposicao: 3, acao_reposicao: "trocar-coletor" }],
  preparo: [{ nome: "higienizar-maos", estado: "maos-higienizadas", custo: 2, consome: "alcool",
              desfeito_ao_sair: true, exigido_antes_de: ["pressao", "glicemia"] },
            { nome: "vestir-mascara", estado: "mascara-vestida", custo: 2 }],
  consumo: [{ procedimento: "glicemia", recurso: "coletor" }],
  exigencia: [{ nome: "protecao", marca: "exige-protecao-respiratoria", preparo: "vestir-mascara",
                custo: 1 }],
};

test("valores do formulário viram valores do TOML", () => {
  assert.equal(valorDoCampo({ tipo: "inteiro" }, "6"), 6);
  assert.equal(valorDoCampo({ tipo: "inteiro" }, ""), undefined);
  assert.equal(valorDoCampo({ tipo: "inteiro" }, "seis"), "seis");    // a API explica o erro
  assert.equal(valorDoCampo({ tipo: "nome" }, "  alcool "), "alcool");
  assert.equal(valorDoCampo({ tipo: "nome" }, "   "), undefined);
  assert.equal(valorDoCampo({ tipo: "booleano" }, false), false);
  assert.deepEqual(valorDoCampo({ tipo: "procedimentos" }, ["pressao"]), ["pressao"]);
  assert.equal(valorDoCampo({ tipo: "procedimentos" }, []), undefined);
});

test("bloco limpo: sem _id, sem vazios; antes_de tira custo e texto", () => {
  assert.deepEqual(blocoLimpo("recurso", { _id: "r1", nome: "a", capacidade: 2, texto: "" }),
                   { nome: "a", capacidade: 2 });
  assert.deepEqual(
    blocoLimpo("exigencia", { nome: "x", marca: "m", preparo: "p", custo: 1, texto: "t",
                              antes_de: ["glicemia"] }),
    { nome: "x", marca: "m", preparo: "p", antes_de: ["glicemia"] });
  assert.deepEqual(blocoLimpo("exigencia", { nome: "x", marca: "m", preparo: "p", custo: 1,
                                             antes_de: [] }),
                   { nome: "x", marca: "m", preparo: "p", custo: 1 });
});

test("ida e volta: dados da API -> estado -> dados da API", () => {
  assert.deepEqual(dadosParaApi(estadoDe(SINTETICAS)), SINTETICAS);
});

test("renomear um recurso atualiza quem o usa", () => {
  const estado = estadoDe(SINTETICAS);
  assert.equal(quemUsa(estado, "recurso", "coletor").length, 1);
  assert.equal(quemUsa(estado, "recurso", "alcool").length, 1);
  assert.equal(propagarNome(estado, "recurso", "alcool", "alcool-gel"), 1);
  assert.equal(estado.preparo[0].consome, "alcool-gel");
  assert.equal(propagarNome(estado, "preparo", "vestir-mascara", "vestir-n95"), 1);
  assert.equal(estado.exigencia[0].preparo, "vestir-n95");
  assert.equal(propagarNome(estado, "consumo", "x", "y"), 0);
});

test("problemas são atribuídos à regra certa", () => {
  const problemas = [
    'recurso "fitas": o nome "fitas" já é usado pelo domínio de entrada',
    'preparo "higienizar-maos", campo \'estado\': ...',
    'consumo de "coletor" por "glicemia": aparece mais de uma vez',
    'exigência "protecao": não há preparo "x"',
  ];
  assert.equal(problemasDaRegra(problemas, "recurso", { nome: "fitas" }).length, 1);
  assert.equal(problemasDaRegra(problemas, "recurso", { nome: "fita" }).length, 0);
  assert.equal(problemasDaRegra(problemas, "preparo", { nome: "higienizar-maos" }).length, 1);
  assert.equal(problemasDaRegra(problemas, "consumo",
                                { procedimento: "glicemia", recurso: "coletor" }).length, 1);
  assert.equal(problemasDaRegra(problemas, "exigencia", { nome: "protecao" }).length, 1);
});

test("resumos legíveis", () => {
  const desc = (p) => ({ glicemia: "medir glicemia capilar", pressao: "aferir pressão" }[p] ?? p);
  assert.equal(resumo("recurso", SINTETICAS.recurso[0]), "6 por carga · repor em 3 min");
  assert.equal(resumo("preparo", SINTETICAS.preparo[0], desc),
               "2 min · gasta alcool · antes de: aferir pressão, medir glicemia capilar");
  assert.equal(resumo("consumo", SINTETICAS.consumo[0], desc), "medir glicemia capilar gasta 1 de coletor");
  assert.match(resumo("exigencia", SINTETICAS.exigencia[0]), /no início da visita/);
  assert.match(resumo("preparo", { custo: 2, desfeito_ao_sair: false }), /vale o turno todo/);
});

test("regra nova traz os padrões e o texto padrão usa o nome", () => {
  const meta = { campos: [{ id: "desfeito_ao_sair", tipo: "booleano", padrao: true },
                          { id: "quantidade", tipo: "inteiro", padrao: 1 },
                          { id: "custo_reposicao", tipo: "inteiro", minimo: 0, sugestao: 3 },
                          { id: "nome", tipo: "nome" }] };
  const nova = regraNova("preparo", meta);
  assert.equal(nova.desfeito_ao_sair, true);
  assert.equal(nova.quantidade, 1);
  assert.equal(nova.custo_reposicao, 3);           // vem preenchido, não só sugerido
  assert.ok(nova._id);
  assert.equal(textoPadrao({ padrao: "repor-{nome}" }, { nome: "alcool" }), "repor-alcool");
});
