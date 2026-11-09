// Tela de regras: lista de regras, formulario da regra escolhida, problemas,
// avisos e previa do TOML. A logica sem DOM fica em regras-logica.js.

import { api } from "./api.js";
import { adiar, baixar, el } from "./dom.js";
import {
  MODELOS, dadosParaApi, estadoDe, estadoVazio, problemasDaRegra, propagarNome, quemUsa,
  regraNova, resumo, textoPadrao, tituloDoCartao, valorDoCampo,
} from "./regras-logica.js";

const CHAVE_RASCUNHO = "acs-regras-rascunho";

export class TelaRegras {
  constructor(raiz, meta, exemplos, { aoMudar } = {}) {
    this.raiz = raiz;
    this.meta = Object.fromEntries(meta.modelos.map((m) => [m.id, m]));
    this.procedimentos = Object.fromEntries(meta.procedimentos.map((p) => [p.id, p.descricao]));
    this.exemplos = exemplos;
    this.aoMudar = aoMudar ?? (() => {});
    this.estado = estadoVazio();
    this.selecionado = null;              // { modelo, id }
    this.validacao = { ok: null, problemas: [], avisos: [], toml: null };
    this.validarDepois = adiar(() => this.validar(), 300);
    this.$ = (seletor) => raiz.querySelector(seletor);
    this.ligarBarra();
    this.restaurarRascunho();
    this.desenharTudo();
    this.validar();
  }

  descricao = (procedimento) => this.procedimentos[procedimento] ?? procedimento;

  // ---- barra de ferramentas -------------------------------------------------

  ligarBarra() {
    this.$("#botao-novo").addEventListener("click", () => {
      if (this.temRegras() && !confirm("Começar do zero? As regras atuais serão descartadas.")) return;
      this.carregar(estadoVazio());
    });
    const arquivo = this.$("#arquivo");
    this.$("#botao-abrir").addEventListener("click", () => arquivo.click());
    arquivo.addEventListener("change", async () => {
      const escolhido = arquivo.files[0];
      arquivo.value = "";
      if (escolhido) await this.abrirToml(await escolhido.text(), escolhido.name);
    });
    const exemplos = this.$("#exemplos");
    for (const exemplo of this.exemplos.regras) {
      exemplos.append(el("option", { value: exemplo.id },
                         exemplo.descricao ? `${exemplo.id} — ${exemplo.descricao}` : exemplo.id));
    }
    exemplos.addEventListener("change", async () => {
      const id = exemplos.value;
      exemplos.value = "";
      if (!id) return;
      const { toml } = await api.exemploDeRegras(id);
      await this.abrirToml(toml, `${id}.toml`);
    });
    this.$("#botao-baixar").addEventListener("click", () => this.baixar());
  }

  temRegras() {
    return MODELOS.some((m) => this.estado[m].length);
  }

  async abrirToml(texto, nome) {
    const lido = await api.lerToml(texto);
    if (!lido.ok) {
      this.mostrarErroGeral(`Não foi possível abrir ${nome}:`, lido.problemas);
      return;
    }
    if (this.temRegras() && !confirm(`Abrir ${nome}? As regras atuais serão substituídas.`)) return;
    this.carregar(estadoDe(lido.regras));
  }

  carregar(estado) {
    this.estado = estado;
    this.selecionado = null;
    this.mostrarErroGeral(null);
    this.desenharTudo();
    this.mudou();
  }

  baixar() {
    if (!this.validacao.ok || !this.validacao.toml) return;
    baixar(this.validacao.toml, "regras.toml");
  }

  mostrarErroGeral(titulo, itens = []) {
    const caixa = document.getElementById("erro-geral");
    caixa.replaceChildren();
    if (!titulo) {
      caixa.classList.add("oculto");
      return;
    }
    caixa.append(el("strong", {}, titulo), el("ul", { class: "lista-problemas" },
                                              itens.map((i) => el("li", {}, i))));
    caixa.classList.remove("oculto");
  }

  // ---- estado: mudancas, validacao, rascunho ------------------------------

  mudou() {
    this.salvarRascunho();
    this.validarDepois();
    this.aoMudar(this);
  }

  async validar() {
    if (!this.temRegras()) {
      this.validacao = { ok: null, problemas: [], avisos: [], toml: null };
    } else {
      try {
        this.validacao = await api.validarRegras(dadosParaApi(this.estado));
      } catch (erro) {
        this.mostrarErroGeral(`O servidor não respondeu: ${erro.message}`);
        return;
      }
    }
    this.desenharLista();
    this.desenharSituacao();
    this.aoMudar(this);
  }

  salvarRascunho() {
    try {
      localStorage.setItem(CHAVE_RASCUNHO, JSON.stringify(dadosParaApi(this.estado)));
    } catch { /* navegador sem armazenamento: o rascunho so nao fica guardado */ }
  }

  restaurarRascunho() {
    try {
      const salvo = JSON.parse(localStorage.getItem(CHAVE_RASCUNHO) || "null");
      if (salvo) this.estado = estadoDe(salvo);
    } catch { /* rascunho ilegivel ou armazenamento bloqueado: comeca vazio */ }
  }

  // ---- desenho ------------------------------------------------------------

  desenharTudo() {
    this.desenharLista();
    this.desenharFormulario();
    this.desenharSituacao();
  }

  regraSelecionada() {
    if (!this.selecionado) return null;
    const { modelo, id } = this.selecionado;
    const bloco = this.estado[modelo].find((b) => b._id === id);
    return bloco ? { modelo, bloco } : null;
  }

  desenharLista() {
    const lista = this.$("#lista");
    lista.replaceChildren();
    for (const modelo of MODELOS) {
      const meta = this.meta[modelo];
      const grupo = el("section", { class: "grupo", "data-modelo": modelo },
        el("div", { class: "grupo__topo" },
          el("h3", { class: "grupo__titulo" }, meta.titulo),
          el("button", { class: "botao botao--pequeno", type: "button",
                         "data-adicionar": modelo, onclick: () => this.adicionar(modelo) },
             `+ Adicionar ${meta.titulo.toLowerCase()}`)),
        el("p", { class: "grupo__desc" }, meta.descricao));
      if (!this.estado[modelo].length) {
        grupo.append(el("p", { class: "grupo__vazio" }, "Nenhuma ainda."));
      }
      for (const bloco of this.estado[modelo]) {
        const problemas = problemasDaRegra(this.validacao.problemas, modelo, bloco);
        const ativo = this.selecionado?.id === bloco._id;
        grupo.append(el("button", {
          class: `cartao${ativo ? " cartao--ativo" : ""}${problemas.length ? " cartao--erro" : ""}`,
          type: "button", "aria-current": ativo ? "true" : null, "data-id": bloco._id,
          onclick: () => this.selecionar(modelo, bloco._id),
        },
          el("span", { class: "cartao__titulo" },
            tituloDoCartao(modelo, bloco, this.descricao),
            modelo !== "consumo" && bloco.nome && bloco.texto
              ? el("span", { class: "cartao__nome" }, bloco.nome) : null,
            problemas.length
              ? el("span", { class: "cartao__selo" },
                   problemas.length === 1 ? "1 problema" : `${problemas.length} problemas`)
              : null),
          el("span", { class: "cartao__resumo" }, resumo(modelo, bloco, this.descricao))));
      }
      lista.append(grupo);
    }
  }

  desenharSituacao() {
    const { ok, problemas, avisos, toml } = this.validacao;
    const selo = this.$("#estado-regras");
    if (ok === null) {
      selo.className = "selo selo--neutro";
      selo.textContent = this.temRegras() ? "Conferindo…" : "Sem regras";
    } else if (ok) {
      selo.className = "selo selo--ok";
      selo.textContent = "✓ Regras válidas";
    } else {
      selo.className = "selo selo--erro";
      selo.textContent = problemas.length === 1 ? "1 problema" : `${problemas.length} problemas`;
    }
    this.$("#botao-baixar").disabled = !ok;
    this.$("#botao-baixar").title = ok ? "" : "Corrija os problemas para baixar o arquivo";
    for (const [id, itens] of [["#problemas", problemas], ["#avisos", avisos]]) {
      const caixa = this.$(id);
      caixa.classList.toggle("oculto", !itens.length);
      caixa.querySelector("ul").replaceChildren(...itens.map((i) => el("li", {}, i)));
    }
    this.$("#previa").textContent = toml ?? "(as regras aparecem aqui quando estiverem válidas)";
  }

  // ---- acoes --------------------------------------------------------------

  adicionar(modelo) {
    const bloco = regraNova(modelo, this.meta[modelo]);
    this.estado[modelo].push(bloco);
    this.selecionado = { modelo, id: bloco._id };
    this.desenharTudo();
    this.mudou();
    this.mostrarFormularioSeEstreito();
    this.$("#formulario input, #formulario select")?.focus();
  }

  selecionar(modelo, id) {
    this.selecionado = { modelo, id };
    this.desenharLista();
    this.desenharFormulario();
    this.mostrarFormularioSeEstreito();
  }

  // Em tela estreita o formulario fica abaixo da lista, fora da vista.
  mostrarFormularioSeEstreito() {
    if (window.matchMedia("(max-width: 899px)").matches) {
      this.$("#formulario").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  remover() {
    const atual = this.regraSelecionada();
    if (!atual) return;
    const { modelo, bloco } = atual;
    const usos = quemUsa(this.estado, modelo, bloco.nome);
    const aviso = usos.length
      ? ` ${usos.length === 1 ? "Uma regra usa" : `${usos.length} regras usam`} esta e ficará com erro.`
      : "";
    if (!confirm(`Remover “${tituloDoCartao(modelo, bloco, this.descricao)}”?${aviso}`)) return;
    this.estado[modelo] = this.estado[modelo].filter((b) => b._id !== bloco._id);
    this.selecionado = null;
    this.desenharTudo();
    this.mudou();
  }

  // ---- formulario ---------------------------------------------------------

  desenharFormulario() {
    const formulario = this.$("#formulario");
    const atual = this.regraSelecionada();
    if (!atual) {
      formulario.replaceChildren(el("div", { class: "formulario__vazio" },
        "Escolha uma regra na lista ou adicione uma nova."));
      return;
    }
    const { modelo, bloco } = atual;
    const meta = this.meta[modelo];
    const filhos = [
      el("div", { class: "formulario__topo" }, el("h2", {}, meta.titulo)),
      el("p", { class: "painel__intro" }, meta.descricao),
    ];
    let campos = meta.campos;
    if (modelo === "exigencia") {
      filhos.push(this.campoQuando(bloco));
      const porProcedimento = (bloco._quando ?? (bloco.antes_de?.length ? "procedimentos" : "visita"))
        === "procedimentos";
      campos = campos.filter((c) => porProcedimento ? !["custo", "texto"].includes(c.id)
                                                     : c.id !== "antes_de");
    }
    for (const campo of campos) filhos.push(this.campo(modelo, bloco, campo));
    filhos.push(el("div", { class: "formulario__rodape" },
      el("button", { class: "botao botao--perigo", type: "button", onclick: () => this.remover() },
         "Remover regra"),
      el("button", { class: "botao", type: "button",
                     onclick: () => { this.selecionado = null; this.desenharTudo(); } },
         "Fechar")));
    formulario.replaceChildren(...filhos);
  }

  campoQuando(bloco) {
    const valor = bloco._quando ?? (bloco.antes_de?.length ? "procedimentos" : "visita");
    const escolher = (novo) => {
      bloco._quando = novo;
      if (novo === "visita") delete bloco.antes_de;
      else if (bloco.custo === undefined) bloco.custo = 1;
      this.desenharFormulario();
      this.desenharLista();
      this.mudou();
    };
    const opcao = (id, rotulo) => el("label", { class: "opcao" },
      el("input", { type: "radio", name: "quando", value: id, checked: valor === id,
                    onchange: () => escolher(id) }), rotulo);
    return el("fieldset", { class: "quando" },
      el("legend", {}, "Quando o preparo é exigido desses pacientes?"),
      opcao("visita", "Para iniciar a visita (conferência na porta)"),
      opcao("procedimentos", "Antes de procedimentos específicos"));
  }

  campo(modelo, bloco, campo) {
    const id = `campo-${campo.id}`;
    const erro = el("div", { class: "campo__erro", id: `${id}-erro`, "aria-live": "polite" });
    const caixa = el("div", { class: "campo", "data-campo": campo.id });
    const rotulo = [campo.descricao ? capitalizar(campo.descricao) : campo.id,
                    campo.obrigatorio ? null : el("span", { class: "campo__opcional" }, " (opcional)")];
    const ajuda = el("div", { class: "campo__ajuda" }, nomeTecnico(campo));
    // nome com que o campo foi desenhado: ao confirmar uma troca, quem
    // referenciava o nome antigo passa a referenciar o novo
    let nomeAnterior = bloco[campo.id];
    const renomeado = () => {
      if (campo.id !== "nome") return;
      if (nomeAnterior && bloco.nome && nomeAnterior !== bloco.nome &&
          propagarNome(this.estado, modelo, nomeAnterior, bloco.nome)) {
        this.desenharLista();
        this.mudou();
      }
      nomeAnterior = bloco.nome;
    };
    const aplicar = (bruto, { redesenharFormulario = false } = {}) => {
      bloco[campo.id] = valorDoCampo(campo, bruto);
      this.desenharLista();
      if (redesenharFormulario) this.desenharFormulario();
      this.mudou();
    };
    const conferir = adiar(async (valor) => {
      if (valor === undefined || ["procedimentos", "procedimento", "booleano"].includes(campo.tipo)) {
        mostrar(null);
        return;
      }
      try {
        const { erro: mensagem, sugestao } = await api.validarCampo(modelo, campo.id, valor);
        mostrar(mensagem, sugestao);
      } catch { /* o servidor caiu: a validacao do conjunto avisa */ }
    }, 250);
    const mostrar = (mensagem, sugestao) => {
      caixa.classList.toggle("campo--erro", Boolean(mensagem));
      erro.replaceChildren();
      if (!mensagem) return;
      erro.append(mensagem);
      if (sugestao) {
        erro.append(" ", el("button", { class: "botao botao--texto", type: "button", onclick: () => {
          caixa.querySelector("input").value = sugestao;
          aplicar(sugestao);
          renomeado();
          conferir(sugestao);
        } }, `Usar “${sugestao}”`));
      }
    };

    let controle;
    switch (campo.tipo) {
      case "booleano":
        controle = el("label", { class: "opcao" },
          el("input", { type: "checkbox", id, checked: bloco[campo.id] ?? campo.padrao ?? false,
                        onchange: (e) => aplicar(e.target.checked) }), "Sim");
        break;
      case "procedimentos": {
        const marcados = new Set(bloco[campo.id] ?? []);
        controle = el("div", { class: "opcoes", role: "group", "aria-labelledby": `${id}-rotulo` },
          Object.entries(this.procedimentos).map(([pid, descricao]) => el("label", { class: "opcao" },
            el("input", { type: "checkbox", value: pid, checked: marcados.has(pid),
                          onchange: (e) => {
                            e.target.checked ? marcados.add(pid) : marcados.delete(pid);
                            aplicar(Object.keys(this.procedimentos).filter((p) => marcados.has(p)));
                          } }),
            descricao)));
        break;
      }
      case "procedimento":
        controle = el("select", { id, onchange: (e) => aplicar(e.target.value) },
          el("option", { value: "" }, "Escolha…"),
          Object.entries(this.procedimentos).map(([pid, descricao]) =>
            el("option", { value: pid, selected: bloco[campo.id] === pid }, descricao)));
        break;
      case "referencia": {
        const opcoes = this.estado[campo.modelo].filter((b) => b.nome);
        controle = el("select", { id, onchange: (e) => aplicar(e.target.value) },
          el("option", { value: "" }, campo.obrigatorio ? "Escolha…" : "nenhum"),
          opcoes.map((b) => el("option", { value: b.nome, selected: bloco[campo.id] === b.nome },
                                b.texto ? `${b.texto} (${b.nome})` : b.nome)));
        if (!opcoes.length) {
          ajuda.append(` Nenhum ${this.meta[campo.modelo].titulo.toLowerCase()} cadastrado ainda.`);
        }
        break;
      }
      case "inteiro":
        controle = el("input", { type: "number", id, min: campo.minimo, step: 1, inputmode: "numeric",
                                 value: bloco[campo.id] ?? "",
                                 oninput: (e) => { aplicar(e.target.value); conferir(bloco[campo.id]); } });
        break;
      default:                                  // nome e texto
        controle = el("input", { type: "text", id, value: bloco[campo.id] ?? "", autocomplete: "off",
          spellcheck: campo.tipo === "texto",
          placeholder: campo.padrao ? textoPadrao(campo, bloco) : "",
          oninput: (e) => { aplicar(e.target.value); conferir(bloco[campo.id]); },
          onchange: renomeado });
    }
    const temRotuloProprio = ["procedimentos"].includes(campo.tipo);
    caixa.append(
      temRotuloProprio ? el("span", { class: "campo__rotulo", id: `${id}-rotulo` }, rotulo)
                       : el("label", { for: id }, rotulo),
      ajuda, controle, erro);
    if (bloco[campo.id] !== undefined) conferir(bloco[campo.id]);
    return caixa;
  }

  // ---- para as outras telas -----------------------------------------------

  tomlAtual() {
    return this.validacao.ok ? this.validacao.toml : null;
  }

  // O que a tela de planejamento precisa saber: quantas regras, se valem.
  situacao() {
    const total = MODELOS.reduce((soma, m) => soma + this.estado[m].length, 0);
    const conferindo = total > 0 && this.validacao.ok === null;
    return { total, conferindo, ok: total > 0 && this.validacao.ok === true,
             problemas: this.validacao.problemas.length, toml: this.tomlAtual() };
  }
}

function capitalizar(texto) {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function nomeTecnico(campo) {
  const dicas = {
    nome: "Minúsculas, sem acento nem espaço, com hífen entre as palavras.",
    texto: "Como aparece no roteiro do ACS; acentos e espaços são livres.",
    inteiro: campo.minimo !== undefined ? `Número inteiro, a partir de ${campo.minimo}.` : "Número inteiro.",
  };
  return `${campo.id}${dicas[campo.tipo] ? " · " + dicas[campo.tipo] : ""}`;
}
