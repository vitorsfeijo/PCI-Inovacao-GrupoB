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
