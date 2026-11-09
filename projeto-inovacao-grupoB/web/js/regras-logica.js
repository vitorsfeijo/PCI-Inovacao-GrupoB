// Logica da tela de regras, sem DOM: o que pode ser testado com `node --test`.
//
// O estado e um objeto { recurso: [...], preparo: [...], consumo: [...],
// exigencia: [...] }, cada regra um objeto com os campos do TOML e um `_id`
// interno (so para a interface saber qual cartao e qual formulario).

export const MODELOS = ["recurso", "preparo", "consumo", "exigencia"];

let proximoId = 1;
export function novoId() {
  return `r${proximoId++}`;
}

export function estadoVazio() {
  return Object.fromEntries(MODELOS.map((m) => [m, []]));
}

// Regras vindas da API (sem _id) -> estado da interface.
export function estadoDe(dados) {
  const estado = estadoVazio();
  for (const modelo of MODELOS) {
    for (const bloco of dados?.[modelo] ?? []) estado[modelo].push({ ...bloco, _id: novoId() });
  }
  return estado;
}

// Valor digitado no formulario -> valor do TOML (ou undefined = campo vazio).
export function valorDoCampo(campo, bruto) {
  switch (campo.tipo) {
    case "inteiro": {
      if (bruto === "" || bruto === null || bruto === undefined) return undefined;
      const numero = Number(bruto);
      return Number.isInteger(numero) ? numero : bruto;   // a validacao explica o erro
    }
    case "booleano":
      return Boolean(bruto);
    case "procedimentos":
      return Array.isArray(bruto) && bruto.length ? [...bruto] : undefined;
    default: {
      const texto = typeof bruto === "string" ? bruto.trim() : bruto;
      return texto === "" || texto === null ? undefined : texto;
    }
  }
}

// Regra do estado -> bloco para a API: sem _id e sem campos vazios. Na
// exigencia "antes de procedimentos", custo e texto nao se aplicam.
export function blocoLimpo(modelo, bloco) {
  const limpo = {};
  for (const [campo, valor] of Object.entries(bloco)) {
    if (campo.startsWith("_") || valor === undefined || valor === null || valor === "") continue;
    if (Array.isArray(valor) && valor.length === 0) continue;
    limpo[campo] = valor;
  }
  if (modelo === "exigencia" && limpo.antes_de) {
    delete limpo.custo;
    delete limpo.texto;
  }
  return limpo;
}

export function dadosParaApi(estado) {
  return Object.fromEntries(MODELOS.map((m) => [m, estado[m].map((b) => blocoLimpo(m, b))]));
}

// Rotulo da regra como o compilador escreve nas mensagens de erro, para
// achar os problemas de cada cartao.
export function rotuloNasMensagens(modelo, bloco) {
  if (modelo === "consumo") return `consumo de "${bloco.recurso}" por "${bloco.procedimento}"`;
  const palavra = { recurso: "recurso", preparo: "preparo", exigencia: "exigência" }[modelo];
  return `${palavra} "${bloco.nome}"`;
}

export function problemasDaRegra(problemas, modelo, bloco) {
  const rotulo = rotuloNasMensagens(modelo, bloco);
  return problemas.filter((p) => p.startsWith(rotulo));
}

// Resumo de uma linha, em portugues, para o cartao.
export function resumo(modelo, bloco, descricaoProcedimento = (p) => p) {
  const lista = (ps) => (ps ?? []).map(descricaoProcedimento).join(", ");
  switch (modelo) {
    case "recurso":
      return [bloco.capacidade !== undefined && `${bloco.capacidade} por carga`,
              bloco.custo_reposicao !== undefined && `repor em ${bloco.custo_reposicao} min`]
        .filter(Boolean).join(" · ");
    case "preparo": {
      const partes = [];
      if (bloco.custo !== undefined) partes.push(`${bloco.custo} min`);
      if (bloco.consome) partes.push(`gasta ${bloco.consome}`);
      if (bloco.exigido_antes_de?.length) partes.push(`antes de: ${lista(bloco.exigido_antes_de)}`);
      if (bloco.desfeito_ao_sair === false) partes.push("vale o turno todo");
      return partes.join(" · ");
    }
    case "consumo":
      return `${descricaoProcedimento(bloco.procedimento ?? "?")} gasta ` +
             `${bloco.quantidade ?? 1} de ${bloco.recurso ?? "?"}`;
    case "exigencia":
      return [`marca ${bloco.marca ?? "?"}`, `exige ${bloco.preparo ?? "?"}`,
              bloco.antes_de?.length ? `antes de: ${lista(bloco.antes_de)}` : "no início da visita"]
        .join(" · ");
  }
  return "";
}

export function tituloDoCartao(modelo, bloco, descricaoProcedimento = (p) => p) {
  if (modelo === "consumo") {
    return bloco.procedimento ? `${descricaoProcedimento(bloco.procedimento)}` : "(novo consumo)";
  }
  return bloco.texto || bloco.nome || "(sem nome)";
}

// Campos de outras regras que apontam para um recurso ou preparo.
const REFERENCIAS = {
  recurso: [["preparo", "consome"], ["consumo", "recurso"]],
  preparo: [["exigencia", "preparo"]],
};

export function quemUsa(estado, modelo, nome) {
  if (!nome) return [];
  return (REFERENCIAS[modelo] ?? []).flatMap(([outro, campo]) =>
    estado[outro].filter((b) => b[campo] === nome).map((b) => ({ modelo: outro, bloco: b })));
}

// Ao renomear um recurso ou preparo, quem o referencia acompanha.
export function propagarNome(estado, modelo, antigo, novo) {
  if (!antigo || antigo === novo) return 0;
  let trocas = 0;
  for (const [outro, campo] of REFERENCIAS[modelo] ?? []) {
    for (const bloco of estado[outro]) {
      if (bloco[campo] === antigo) {
        bloco[campo] = novo;
        trocas++;
      }
    }
  }
  return trocas;
}

// Texto de exemplo de um campo com valor padrao ("repor-{nome}").
export function textoPadrao(campo, bloco) {
  return (campo.padrao ?? "").toString().replaceAll("{nome}", bloco.nome || "…");
}

// Regra nova, com os valores padrao do formulario.
export function regraNova(modelo, metaModelo) {
  const bloco = { _id: novoId() };
  for (const campo of metaModelo.campos) {
    if (campo.tipo === "booleano" && campo.padrao !== undefined) bloco[campo.id] = campo.padrao;
    if (campo.tipo === "inteiro" && (campo.padrao ?? campo.sugestao) !== undefined) {
      bloco[campo.id] = campo.padrao ?? campo.sugestao;     // ex.: repor em 3 min
    }
  }
  if (modelo === "exigencia") bloco.custo = 1;
  return bloco;
}
