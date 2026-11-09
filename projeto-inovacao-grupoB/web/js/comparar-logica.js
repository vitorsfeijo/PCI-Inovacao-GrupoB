// Logica da tela "antes x depois", sem DOM: o que pode ser testado com `node --test`.
//
// "Antes" e o turno so com as normas da lei; "depois", com as regras da equipe.
// Os dois usam os mesmos pacientes e a mesma rota (a selecao e a rota nao
// dependem das regras), entao as diferencas sao as tarefas, o tempo e as
// passagens pela UBS que as regras trazem.

// Diferenca entre duas listas de tarefas, na ordem de `depois`; o que saiu
// vai no fim. Tarefas repetidas contam como varias.
export function diferencaDeTarefas(antes, depois) {
  const restantes = [...antes];
  const linhas = depois.map((texto) => {
    const i = restantes.indexOf(texto);
    if (i === -1) return { texto, tipo: "nova" };
    restantes.splice(i, 1);
    return { texto, tipo: "igual" };
  });
  return linhas.concat(restantes.map((texto) => ({ texto, tipo: "saiu" })));
}

function contar(textos) {
  const contagem = new Map();
  for (const t of textos) contagem.set(t, (contagem.get(t) ?? 0) + 1);
  return [...contagem].map(([texto, vezes]) => ({ texto, vezes }))
    .sort((a, b) => b.vezes - a.vezes || a.texto.localeCompare(b.texto));
}

function passagens(r) {
  return r.paradas.filter((p) => p.desvio_ubs).length;
}

function tarefas(r) {
  return r.paradas.reduce((soma, p) => soma + p.tarefas.length, 0);
}

export function compararResultados(antes, depois) {
  const doAntes = new Map(antes.paradas.map((p) => [p.paciente.id, p]));
  const paradas = depois.paradas.map((p) => {
    const a = doAntes.get(p.paciente.id);
    return {
      ordem: p.ordem,
      ordemAntes: a?.ordem ?? null,
      paciente: p.paciente,
      chegadaAntes: a?.inicio_min ?? null,
      chegadaDepois: p.inicio_min,
      atraso: a ? p.inicio_min - a.inicio_min : null,
      tarefas: diferencaDeTarefas(a?.tarefas ?? [], p.tarefas),
      desvioAntes: Boolean(a?.desvio_ubs),
      desvioDepois: p.desvio_ubs,
      reporAntes: a?.repor ?? [],
      reporDepois: p.repor,
    };
  });
  const linhas = paradas.flatMap((p) => p.tarefas);
  const diferenca = depois.custo_total - antes.custo_total;
  return {
    mesmaRota: JSON.stringify(antes.rota) === JSON.stringify(depois.rota),
    visitas: depois.paradas.length,
    minutos: {
      antes: antes.custo_total, depois: depois.custo_total, diferenca,
      percentual: antes.custo_total ? Math.round((100 * diferenca) / antes.custo_total) : null,
    },
    tarefas: { antes: tarefas(antes), depois: tarefas(depois) },
    passagens: { antes: passagens(antes), depois: passagens(depois) },
    orcamento: depois.orcamento ?? null,
    paradas,
    novas: contar(linhas.filter((l) => l.tipo === "nova").map((l) => l.texto)),
    sairam: contar(linhas.filter((l) => l.tipo === "saiu").map((l) => l.texto)),
    reposicoes: contar(paradas.flatMap((p) => p.reporDepois))
      .map((r) => ({ ...r, antes: paradas.flatMap((p) => p.reporAntes).filter((x) => x === r.texto).length })),
  };
}

// "+37 min (+15%)", "sem diferença", "−5 min (−2%)"
export function variacao(diferenca, percentual = null, unidade = "min") {
  if (diferenca === 0) return "sem diferença";
  const sinal = diferenca > 0 ? "+" : "−";
  const pct = percentual === null ? "" : ` (${sinal}${Math.abs(percentual)}%)`;
  return `${sinal}${Math.abs(diferenca)}${unidade ? ` ${unidade}` : ""}${pct}`;
}
