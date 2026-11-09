// Chamadas a API do servidor local (backend/servidor/http.py).

async function pedir(caminho, corpo) {
  const opcoes = corpo === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  };
  const resposta = await fetch(caminho, opcoes);
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || `erro ${resposta.status} em ${caminho}`);
  return dados;
}

export const api = {
  modelos: () => pedir("/api/modelos"),
  exemplos: () => pedir("/api/exemplos"),
  exemploDeRegras: (id) => pedir(`/api/exemplos/regras/${encodeURIComponent(id)}`),
  validarCampo: (modelo, campo, valor) => pedir("/api/regras/campo", { modelo, campo, valor }),
  validarRegras: (regras) => pedir("/api/regras/validar", { regras }),
  lerToml: (toml) => pedir("/api/regras/ler", { toml }),
  planejar: (pedido) => pedir("/api/planejar", pedido),
  tarefa: (id) => pedir(`/api/tarefas/${encodeURIComponent(id)}`),
};

// Cria a tarefa de planejamento e consulta o andamento ate terminar.
// aoProgresso(mensagens, segundos) e chamado a cada consulta.
export async function planejarEAguardar(pedido, aoProgresso = () => {}, intervalo = 500) {
  const comeco = Date.now();
  const { id } = await api.planejar(pedido);
  let tarefa;
  do {
    await new Promise((r) => setTimeout(r, intervalo));
    tarefa = await api.tarefa(id);
    aoProgresso(tarefa.mensagens, Math.round((Date.now() - comeco) / 1000));
  } while (tarefa.estado === "na fila" || tarefa.estado === "rodando");
  return tarefa;
}
