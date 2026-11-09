// Logica da tela de planejamento, sem DOM: o que pode ser testado com `node --test`.

export const TAMANHO_MAXIMO_PLANILHA = 2_000_000;   // o mesmo limite do servidor

// Opcoes do formulario -> o que a API recebe. Campos vazios ficam de fora
// (vale o padrao da linha de comando).
const OPCOES_NUMERICAS = ["orcamento", "max_pacientes", "limite", "semente"];
const OPCOES_ESCOLHA = ["estrategia", "planejador", "metodo"];
const OPCOES_SIM_NAO = ["sem_selecao", "sem_precedencia", "sem_limpeza"];

export function pedidoDe(formulario) {
  const pedido = {};
  if (formulario.regras_toml) pedido.regras_toml = formulario.regras_toml;

  switch (formulario.fonte) {
    case "csv":
      if (!formulario.csv) throw new Error("Escolha o arquivo da planilha (.csv).");
      if (formulario.csv.length > TAMANHO_MAXIMO_PLANILHA) {
        throw new Error("A planilha passa de 2 MB.");
      }
      pedido.planilha = { csv: formulario.csv };
      break;
    case "sintetica": {
      const n = inteiro(formulario.pacientes_sinteticos, "Número de pacientes");
      const semente = inteiro(formulario.semente_sintetica ?? 0, "Semente");
      if (n === undefined || n < 1) throw new Error("Número de pacientes: pelo menos 1.");
      pedido.planilha = { sintetica: [n, semente ?? 0] };
      break;
    }
    default:
      pedido.planilha = { exemplo: formulario.exemplo || "exemplo-ciclo2" };
  }

  const opcoes = {};
  for (const chave of OPCOES_NUMERICAS) {
    const valor = chave === "limite" ? numero(formulario[chave], "Limite de tempo")
                                     : inteiro(formulario[chave], ROTULOS[chave]);
    if (valor !== undefined) opcoes[chave] = valor;
  }
  for (const chave of OPCOES_ESCOLHA) {
    if (formulario[chave] && formulario[chave] !== "padrao") opcoes[chave] = formulario[chave];
  }
  for (const chave of OPCOES_SIM_NAO) if (formulario[chave]) opcoes[chave] = true;
  if (Object.keys(opcoes).length) pedido.opcoes = opcoes;
  return pedido;
}

const ROTULOS = { orcamento: "Tempo do turno", max_pacientes: "Máximo de pacientes",
                  semente: "Semente da rota" };

function vazio(bruto) {
  return bruto === undefined || bruto === null || String(bruto).trim() === "";
}

function inteiro(bruto, rotulo) {
  if (vazio(bruto)) return undefined;
  const valor = Number(bruto);
  if (!Number.isInteger(valor) || valor < 0) throw new Error(`${rotulo}: use um número inteiro.`);
  return valor;
}

function numero(bruto, rotulo) {
  if (vazio(bruto)) return undefined;
  const valor = Number(String(bruto).replace(",", "."));
  if (!Number.isFinite(valor) || valor <= 0) throw new Error(`${rotulo}: use um número positivo.`);
  return valor;
}

// ---- tempos --------------------------------------------------------------

// 432 -> "7h12"; 45 -> "45 min"
export function duracao(minutos) {
  if (minutos < 60) return `${minutos} min`;
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return `${h}h${String(m).padStart(2, "0")}`;
}

// ("08:00", 25) -> "08:25"; sem horario de inicio valido, null
export function horario(inicio, minutosDeTurno) {
  const partes = /^(\d{1,2}):(\d{2})$/.exec(inicio ?? "");
  if (!partes) return null;
  const total = Number(partes[1]) * 60 + Number(partes[2]) + minutosDeTurno;
  const h = Math.floor(total / 60) % 24;
  return `${String(h).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

// ---- resultado -----------------------------------------------------------

export function rotuloGrupo(grupo) {
  return (grupo ?? "").replaceAll("_", " ");
}

// Numeros do topo do roteiro.
export function resumoDoResultado(r) {
  const passagens = r.paradas.filter((p) => p.desvio_ubs).length;
  const orcamento = r.orcamento ?? null;
  return {
    visitas: r.paradas.length,
    minutos: r.custo_total,
    duracao: duracao(r.custo_total),
    passagensUbs: passagens,
    adiados: r.selecao.adiados.map((id) => r.pontos[id] ?? { id, nome: id }),
    orcamento,
    folga: orcamento === null ? null : orcamento - r.custo_total,
    busca: `${r.busca.planejador} · ${r.busca.metodo} · ` +
           `${r.busca.otimo ? "plano ótimo" : "sem garantia de ser ótimo"} · ` +
           `${r.busca.segundos.toFixed(1).replace(".", ",")} s`,
  };
}

// A UBS de onde o turno sai e para onde volta (primeiro ponto da rota).
export function ubsDo(r) {
  return r.pontos[r.rota[0]] ?? { nome: "UBS" };
}

// Tarefa terminada sem roteiro (ou com erro inesperado) -> o que mostrar.
export function explicarFalha(tarefa) {
  if (tarefa.estado === "erro") {
    return { titulo: "Erro inesperado no servidor",
             itens: [tarefa.erro ?? "sem detalhes"],
             dica: "Veja as mensagens abaixo e o terminal onde o `acs.py web` está rodando." };
  }
  const falha = tarefa.resultado?.falha ?? { tipo: "erro", mensagens: [] };
  const mensagens = falha.mensagens.filter((m) => !m.startsWith("Motivo informado"));
  switch (falha.tipo) {
    case "interrompida":
      return { titulo: "A busca parou no limite de tempo",
               itens: mensagens.slice(0, 1),
               dica: "Isso não quer dizer que o turno é impossível. Aumente o limite de " +
                     "tempo ou diminua o máximo de pacientes (em Turno) e tente de novo." };
    case "impossivel":
      return { titulo: "Nenhum roteiro cumpre as regras neste turno",
               itens: mensagens.slice(0, 1),
               dica: "Reveja a seleção de pacientes, os recursos (capacidade) ou as regras." };
    default:
      return { titulo: "As regras ou a planilha têm problemas",
               itens: mensagens,
               dica: "Corrija na tela Regras ou na planilha e planeje de novo." };
  }
}
