// Tela de planejamento: escolhe regras, pacientes e turno, pede o
// planejamento ao servidor, acompanha o progresso e mostra o roteiro.
// A logica sem DOM fica em planejar-logica.js.

import { api } from "./api.js";
import { baixar, el } from "./dom.js";
import {
  TAMANHO_MAXIMO_PLANILHA, duracao, explicarFalha, horario, pedidoDe, resumoDoResultado,
  rotuloGrupo, ubsDo,
} from "./planejar-logica.js";

const INTERVALO_CONSULTA = 500;     // ms entre consultas ao andamento da tarefa

export class TelaPlanejar {
  // situacaoDasRegras: () => { total, ok, conferindo, problemas, toml } (da tela de regras)
  constructor(raiz, exemplos, { situacaoDasRegras, irParaRegras, aoPlanejar } = {}) {
    this.raiz = raiz;
    this.situacaoDasRegras = situacaoDasRegras;
    this.aoPlanejar = aoPlanejar ?? (() => {});
    this.csv = null;
    this.preferencia = "equipe";        // regras da equipe, quando validas
    this.rodando = false;
    this.ultimo = null;                 // { resultado, inicio } do ultimo roteiro
    this.$ = (seletor) => raiz.querySelector(seletor);
    this.form = this.$("#pedido");

    const planilhas = this.$("#planilha-exemplo");
    for (const p of exemplos.planilhas) planilhas.append(el("option", { value: p.id }, p.descricao));

    for (const opcao of this.form.querySelectorAll("input[name=regras]")) {
      opcao.addEventListener("change", () => { this.preferencia = opcao.value; });
    }
    this.form.addEventListener("change", () => this.atualizarFormulario());
    this.form.addEventListener("submit", (evento) => { evento.preventDefault(); this.planejar(); });
    this.$("#ir-para-regras").addEventListener("click", () => irParaRegras?.());
    this.$("#escolher-csv").addEventListener("click", () => this.$("#arquivo-csv").click());
    this.$("#arquivo-csv").addEventListener("change", (evento) => this.lerCsv(evento.target));
    this.atualizarFormulario();
  }

  // ---- formulario ---------------------------------------------------------

  // Chamado tambem quando as regras mudam na outra tela.
  atualizarFormulario() {
    const regras = this.situacaoDasRegras();
    const equipe = this.form.querySelector('input[name=regras][value=equipe]');
    const texto = this.$("#situacao-regras");
    equipe.disabled = !regras.ok;
    if (regras.total === 0) texto.textContent = "(nenhuma regra criada ainda)";
    else if (regras.conferindo) texto.textContent = "(conferindo…)";
    else if (regras.ok) texto.textContent = `(${regras.total} ${regras.total === 1 ? "regra válida" : "regras válidas"})`;
    else texto.textContent = `(${regras.total} regras, com problemas: corrija para usá-las)`;
    const usar = regras.ok && this.preferencia === "equipe";
    this.form.querySelector(`input[name=regras][value=${usar ? "equipe" : "nenhuma"}]`).checked = true;

    const fonte = this.form.elements.fonte.value;
    for (const detalhe of this.raiz.querySelectorAll("[data-fonte]")) {
      detalhe.classList.toggle("oculto", detalhe.dataset.fonte !== fonte);
    }
  }

  async lerCsv(entrada) {
    const arquivo = entrada.files[0];
    entrada.value = "";
    if (!arquivo) return;
    const nome = this.$("#nome-csv");
    if (arquivo.size > TAMANHO_MAXIMO_PLANILHA) {
      this.csv = null;
      nome.textContent = `${arquivo.name} passa de 2 MB`;
      return;
    }
    this.csv = await arquivo.text();
    const linhas = this.csv.trim().split(/\r?\n/).length - 1;
    nome.textContent = `${arquivo.name} · ${linhas} ${linhas === 1 ? "paciente" : "pacientes"}`;
    this.form.elements.fonte.value = "csv";
    this.atualizarFormulario();
  }

  lerFormulario() {
    const f = this.form.elements;
    const regras = this.situacaoDasRegras();
    const usarEquipe = f.regras.value === "equipe" && regras.ok;
    return {
      regras_toml: usarEquipe ? regras.toml : null,
      fonte: f.fonte.value,
      exemplo: f.exemplo.value,
      csv: this.csv,
      pacientes_sinteticos: f.pacientes_sinteticos.value,
      semente_sintetica: f.semente_sintetica.value,
      orcamento: f.orcamento.value,
      max_pacientes: f.max_pacientes.value,
      limite: f.limite.value,
      semente: f.semente.value,
      estrategia: f.estrategia.value,
      planejador: f.planejador.value,
      metodo: f.metodo.value,
      sem_selecao: f.sem_selecao.checked,
      sem_precedencia: f.sem_precedencia.checked,
      sem_limpeza: f.sem_limpeza.checked,
    };
  }

  // ---- planejar e acompanhar ----------------------------------------------

  async planejar() {
    if (this.rodando) return;
    const erro = this.$("#erro-pedido");
    erro.textContent = "";
    let pedido;
    try {
      pedido = pedidoDe(this.lerFormulario());
    } catch (e) {
      erro.textContent = e.message;
      return;
    }
    const inicio = this.form.elements.inicio.value;
    this.definirRodando(true);
    const comeco = Date.now();
    try {
      const { id } = await api.planejar(pedido);
      let tarefa;
      do {
        await new Promise((r) => setTimeout(r, INTERVALO_CONSULTA));
        tarefa = await api.tarefa(id);
        this.mostrarProgresso(tarefa.mensagens, Math.round((Date.now() - comeco) / 1000));
      } while (tarefa.estado === "na fila" || tarefa.estado === "rodando");
      this.mostrarTarefa(tarefa, inicio);
    } catch (e) {
      erro.textContent = `Não foi possível planejar: ${e.message}`;
      this.$("#progresso").classList.add("oculto");
    } finally {
      this.definirRodando(false);
    }
  }

  definirRodando(rodando) {
    this.rodando = rodando;
    const botao = this.$("#botao-planejar");
    botao.disabled = rodando;
    botao.textContent = rodando ? "Planejando…" : "Planejar o turno";
    if (rodando) {
      this.$("#progresso").classList.remove("oculto");
      this.mostrarProgresso([], 0);
    }
  }

  mostrarProgresso(mensagens, segundos) {
    this.$("#progresso-titulo").textContent = `Planejando… ${segundos} s`;
    this.$("#progresso-mensagens").replaceChildren(
      ...mensagens.filter((m) => m.trim()).map((m) => el("li", {}, m.trim())));
  }

  mostrarTarefa(tarefa, inicio) {
    this.$("#progresso").classList.add("oculto");
    const saida = this.$("#resultado");
    if (tarefa.estado === "pronta" && tarefa.resultado?.codigo === 0) {
      this.ultimo = { resultado: tarefa.resultado, inicio };
      saida.replaceChildren(...this.roteiro(tarefa.resultado, inicio, tarefa.mensagens));
      this.aoPlanejar(this.ultimo);
    } else {
      saida.replaceChildren(this.falha(tarefa));
    }
    saida.dataset.estado = tarefa.estado === "pronta" && tarefa.resultado?.codigo === 0
      ? "roteiro" : "falha";                                  // usado pelos testes
    if (window.matchMedia("(max-width: 899px)").matches) {
      saida.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  // ---- desenho do resultado -------------------------------------------------

  falha(tarefa) {
    const { titulo, itens, dica } = explicarFalha(tarefa);
    return el("div", { class: "painel" },
      el("div", { class: "caixa caixa--erro" },
        el("h3", {}, titulo),
        itens.length ? el("ul", { class: "lista-problemas" }, itens.map((i) => el("li", {}, i))) : null,
        el("p", { class: "caixa__dica" }, dica)),
      this.mensagens(tarefa.mensagens, true));
  }

  roteiro(r, inicio, mensagens) {
    const resumo = resumoDoResultado(r);
    const ubs = ubsDo(r);
    const quando = (min) => {
      const hora = horario(inicio, min);
      return hora ? `${hora} (${min} min de turno)` : `${min} min de turno`;
    };

    const numeros = el("div", { class: "numeros" },
      this.numero(resumo.visitas, resumo.visitas === 1 ? "visita" : "visitas"),
      this.numero(resumo.duracao, "duração estimada",
                  resumo.folga === null ? null
                    : resumo.folga >= 0 ? `cabe no turno de ${resumo.orcamento} min`
                                        : `passa ${-resumo.folga} min do turno`,
                  resumo.folga !== null && resumo.folga < 0),
      this.numero(resumo.passagensUbs, resumo.passagensUbs === 1 ? "volta à UBS para repor"
                                                                  : "voltas à UBS para repor"),
      this.numero(resumo.adiados.length, "ficam para outro turno"));

    const paradas = el("ol", { class: "paradas" },
      el("li", { class: "parada parada--ubs" },
         el("strong", {}, `Saída: ${ubs.nome}`),
         horario(inicio, 0) ? el("span", { class: "parada__hora" }, horario(inicio, 0)) : null),
      r.paradas.map((p) => this.parada(p, quando)),
      el("li", { class: "parada parada--ubs" },
         el("strong", {}, `Retorno: ${ubs.nome}`),
         el("span", { class: "parada__hora" }, `fim ≈ ${quando(r.custo_total)}`)));

    const adiados = resumo.adiados.length
      ? el("div", { class: "caixa caixa--neutra" },
          el("h3", {}, "Ficam para outro turno"),
          el("ul", { class: "lista-problemas" },
             resumo.adiados.map((p) => el("li", {}, p.nome,
               p.grupo ? el("span", { class: "campo__ajuda" }, ` (${rotuloGrupo(p.grupo)})`) : null))))
      : null;

    const avisos = r.avisos.length
      ? el("div", { class: "caixa caixa--aviso" }, el("h3", {}, "Avisos das regras"),
           el("ul", { class: "lista-problemas" }, r.avisos.map((a) => el("li", {}, a))))
      : null;

    return [el("div", { class: "painel roteiro" },
      el("div", { class: "roteiro__topo" },
        el("div", {},
          el("h2", {}, "Roteiro do turno"),
          el("p", { class: "campo__ajuda" },
             r.regras ? "Com as regras da equipe" : "Só com as normas da lei", " · ", resumo.busca)),
        el("div", { class: "roteiro__acoes" },
          el("button", { class: "botao", type: "button", onclick: () => window.print() }, "Imprimir"),
          el("button", { class: "botao", type: "button",
                         onclick: () => baixar(r.texto + "\n", "roteiro.txt") }, "Baixar (.txt)"))),
      numeros, avisos, paradas, adiados,
      this.mensagens(mensagens, false))];
  }

  numero(valor, rotulo, detalhe = null, alerta = false) {
    return el("div", { class: `numero${alerta ? " numero--alerta" : ""}` },
      el("strong", {}, String(valor)), el("span", {}, rotulo),
      detalhe ? el("small", {}, detalhe) : null);
  }

  parada(p, quando) {
    const desvio = p.desvio_ubs
      ? el("div", { class: "parada__desvio" },
          el("strong", {}, "Antes: passar na UBS"),
          p.repor.length ? ` para repor ${p.repor.join(", ")}` : null)
      : null;
    const grupo = rotuloGrupo(p.paciente.grupo);
    return el("li", { class: "parada" },
      desvio,
      el("div", { class: "parada__topo" },
        el("span", { class: "parada__ordem" }, String(p.ordem)),
        el("div", {},
          el("strong", {}, p.paciente.nome),
          grupo ? el("span", { class: "campo__ajuda" }, ` · ${grupo}`) : null,
          el("div", { class: "parada__hora" }, `chegada ≈ ${quando(p.inicio_min)}`))),
      el("ul", { class: "tarefas" },
         p.tarefas.map((t) => el("li", {}, el("label", {}, el("input", { type: "checkbox" }), " ", t)))));
  }

  mensagens(mensagens, aberto) {
    const linhas = (mensagens ?? []).filter((m) => m.trim());
    if (!linhas.length) return null;
    return el("details", { class: "previa mensagens-finais", open: aberto },
      el("summary", {}, "Como foi planejado (mensagens do planejador)"),
      el("pre", {}, linhas.join("\n")));
  }
}
