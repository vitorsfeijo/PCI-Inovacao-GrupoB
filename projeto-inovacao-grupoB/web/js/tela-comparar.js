// Tela "antes x depois": planeja o mesmo turno duas vezes (so com as normas
// da lei e com as regras da equipe) e mostra o que as regras mudam.
// Pacientes e turno vem do formulario da tela de planejamento.
// A logica sem DOM fica em comparar-logica.js.

import { planejarEAguardar } from "./api.js";
import { compararResultados, variacao } from "./comparar-logica.js";
import { el } from "./dom.js";
import { duracao, explicarFalha, horario, rotuloGrupo } from "./planejar-logica.js";

export class TelaComparar {
  // planejar: a TelaPlanejar (pedidoAtual, descricaoDoTurno, inicioDoTurno)
  constructor(raiz, { situacaoDasRegras, planejar, irPara }) {
    this.raiz = raiz;
    this.situacaoDasRegras = situacaoDasRegras;
    this.planejar = planejar;
    this.rodando = false;
    this.comparacao = null;
    this.$ = (seletor) => raiz.querySelector(seletor);
    this.$("#botao-comparar").addEventListener("click", () => this.comparar());
    this.$("#comparar-ir-regras").addEventListener("click", () => irPara("regras"));
    this.$("#comparar-ir-planejar").addEventListener("click", () => irPara("planejar"));
    this.$("#so-mudancas").addEventListener("change", () => this.desenharComparacao());
    this.atualizar();
  }

  // Chamado quando a aba aparece e quando as regras mudam.
  atualizar() {
    const regras = this.situacaoDasRegras();
    let texto;
    if (regras.total === 0) texto = "nenhuma regra criada ainda: crie ou abra regras na aba Regras";
    else if (regras.conferindo) texto = "conferindo…";
    else if (regras.ok) texto = `${regras.total} ${regras.total === 1 ? "regra válida" : "regras válidas"}`;
    else texto = `${regras.total} regras, com problemas: corrija na aba Regras para comparar`;
    this.$("#comparar-regras").textContent = texto;
    this.$("#comparar-turno").textContent = this.planejar.descricaoDoTurno();
    this.$("#botao-comparar").disabled = this.rodando || !regras.ok;
  }

  async comparar() {
    if (this.rodando) return;
    const erro = this.$("#erro-comparar");
    erro.textContent = "";
    const regras = this.situacaoDasRegras();
    if (!regras.ok) return;
    let pedidos;
    try {
      pedidos = { antes: this.planejar.pedidoAtual({ regras_toml: null }),
                  depois: this.planejar.pedidoAtual({ regras_toml: regras.toml }) };
    } catch (e) {
      erro.textContent = `${e.message} (na aba Planejar)`;
      return;
    }
    this.inicio = this.planejar.inicioDoTurno;
    this.definirRodando(true);
    try {
      const [antes, depois] = await Promise.all(["antes", "depois"].map((lado) =>
        planejarEAguardar(pedidos[lado], (_mensagens, segundos) =>
          this.mostrarProgresso(lado, `planejando… ${segundos} s`))
          .then((tarefa) => {
            this.mostrarProgresso(lado, tarefa.resultado?.codigo === 0 ? "pronto" : "sem roteiro");
            return tarefa;
          })));
      this.mostrarResultado(antes, depois);
    } catch (e) {
      erro.textContent = `Não foi possível comparar: ${e.message}`;
    } finally {
      this.definirRodando(false);
    }
  }

  definirRodando(rodando) {
    this.rodando = rodando;
    const botao = this.$("#botao-comparar");
    botao.textContent = rodando ? "Comparando…" : "Comparar";
    this.$("#comparar-progresso").classList.toggle("oculto", !rodando);
    if (rodando) {
      this.mostrarProgresso("antes", "na fila");
      this.mostrarProgresso("depois", "na fila");
    }
    this.atualizar();
  }

  mostrarProgresso(lado, texto) {
    this.$(`#progresso-${lado}`).textContent = texto;
  }

  mostrarResultado(antes, depois) {
    const saida = this.$("#comparacao");
    const ok = (t) => t.estado === "pronta" && t.resultado?.codigo === 0;
    if (ok(antes) && ok(depois)) {
      this.comparacao = compararResultados(antes.resultado, depois.resultado);
      saida.dataset.estado = "comparacao";
      this.desenharComparacao();
    } else {
      this.comparacao = null;
      saida.dataset.estado = "falha";
      saida.replaceChildren(el("div", { class: "painel" },
        ...[["antes", "Só com as normas da lei", antes], ["depois", "Com as regras da equipe", depois]]
          .filter(([, , t]) => !ok(t))
          .map(([, rotulo, t]) => {
            const { titulo, itens, dica } = explicarFalha(t);
            return el("div", { class: "caixa caixa--erro" },
              el("h3", {}, `${rotulo}: ${titulo.toLowerCase()}`),
              itens.length ? el("ul", { class: "lista-problemas" }, itens.map((i) => el("li", {}, i))) : null,
              el("p", { class: "caixa__dica" }, dica));
          })));
    }
    if (window.matchMedia("(max-width: 899px)").matches) {
      saida.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  // ---- desenho ------------------------------------------------------------

  desenharComparacao() {
    const c = this.comparacao;
    if (!c) return;
    const soMudancas = this.$("#so-mudancas").checked;
    const m = c.minutos;
    const folga = (minutos) => (c.orcamento === null ? null : c.orcamento - minutos);
    const cabe = (minutos) => {
      const f = folga(minutos);
      return f === null ? null : f >= 0 ? "cabe no turno" : `passa ${-f} min do turno`;
    };

    const numeros = el("div", { class: "numeros" },
      this.numero("Duração", `${duracao(m.antes)} → ${duracao(m.depois)}`,
                  variacao(m.diferenca, m.percentual),
                  c.orcamento === null ? null : `antes: ${cabe(m.antes)}; depois: ${cabe(m.depois)}`,
                  folga(m.depois) !== null && folga(m.depois) < 0),
      this.numero("Tarefas", `${c.tarefas.antes} → ${c.tarefas.depois}`,
                  variacao(c.tarefas.depois - c.tarefas.antes, null, "")),
      this.numero("Voltas à UBS", `${c.passagens.antes} → ${c.passagens.depois}`,
                  variacao(c.passagens.depois - c.passagens.antes, null, "")),
      this.numero("Visitas", String(c.visitas),
                  c.mesmaRota ? "mesmos pacientes, mesma rota" : "a rota mudou"));

    const novas = c.novas.length || c.reposicoes.some((r) => r.vezes !== r.antes) || c.sairam.length
      ? el("div", { class: "caixa caixa--neutra" },
          el("h3", {}, "O que as regras mudaram no turno"),
          el("ul", { class: "lista-problemas" },
            c.novas.map((n) => el("li", {}, el("strong", {}, n.texto), ` — ${vezes(n.vezes)}`)),
            c.reposicoes.filter((r) => r.vezes !== r.antes).map((r) =>
              el("li", {}, el("strong", {}, `Passar na UBS para repor ${r.texto}`),
                 ` — ${vezes(r.vezes)}${r.antes ? ` (antes: ${vezes(r.antes)})` : ""}`)),
            c.sairam.map((n) => el("li", {}, el("s", {}, n.texto), ` — saiu ${vezes(n.vezes)}`))))
      : el("div", { class: "caixa caixa--neutra" },
          el("h3", {}, "As regras não mudaram as tarefas deste turno"),
          el("p", { class: "caixa__dica" }, "Talvez nenhum paciente selecionado tenha os " +
             "procedimentos ou as marcas a que as regras se aplicam."));

    const paradas = el("ol", { class: "paradas" }, c.paradas.map((p) => this.parada(p, soMudancas)));

    this.$("#comparacao").replaceChildren(el("div", { class: "painel" },
      el("h2", {}, "Antes × depois"),
      el("p", { class: "campo__ajuda" }, "Antes: só as normas da lei. Depois: com as regras da equipe."),
      numeros, novas,
      el("div", { class: "legenda" },
        el("span", { class: "tarefa--nova" }, "+ tarefa nova"),
        el("span", { class: "tarefa--saiu" }, "− tarefa que saiu")),
      paradas));
  }

  numero(rotulo, valor, detalhe, extra = null, alerta = false) {
    return el("div", { class: `numero${alerta ? " numero--alerta" : ""}` },
      el("span", {}, rotulo), el("strong", {}, valor),
      el("small", { class: "numero__variacao" }, detalhe),
      extra ? el("small", {}, extra) : null);
  }

  parada(p, soMudancas) {
    const hora = (min) => horario(this.inicio, min) ?? `${min} min`;
    const chegada = p.chegadaAntes === null
      ? `chegada ≈ ${hora(p.chegadaDepois)}`
      : p.atraso === 0 ? `chegada ≈ ${hora(p.chegadaDepois)} (igual)`
        : `chegada ≈ ${hora(p.chegadaAntes)} → ${hora(p.chegadaDepois)} (${variacao(p.atraso)})`;
    const desvio = p.desvioDepois || p.desvioAntes
      ? el("div", { class: `parada__desvio${p.desvioDepois && !p.desvioAntes ? " parada__desvio--novo" : ""}` },
          !p.desvioDepois ? "− Não passa mais na UBS antes desta visita"
            : `${p.desvioAntes ? "" : "+ "}Passar na UBS antes desta visita` +
              (p.reporDepois.length ? ` para repor ${p.reporDepois.join(", ")}` : ""))
      : null;
    const linhas = p.tarefas.filter((t) => !soMudancas || t.tipo !== "igual");
    const grupo = rotuloGrupo(p.paciente.grupo);
    return el("li", { class: "parada" },
      desvio,
      el("div", { class: "parada__topo" },
        el("span", { class: "parada__ordem" }, String(p.ordem)),
        el("div", {},
          el("strong", {}, p.paciente.nome),
          grupo ? el("span", { class: "campo__ajuda" }, ` · ${grupo}`) : null,
          el("div", { class: "parada__hora" }, chegada))),
      linhas.length
        ? el("ul", { class: "tarefas tarefas--comparacao" }, linhas.map((t) =>
            el("li", { class: `tarefa--${t.tipo}` },
               t.tipo === "nova" ? "+ " : t.tipo === "saiu" ? "− " : "", t.texto)))
        : el("p", { class: "campo__ajuda tarefas" }, "sem mudanças nas tarefas"));
  }
}

function vezes(n) {
  return n === 1 ? "1 vez" : `${n} vezes`;
}
