// Utilitarios de DOM compartilhados pelas telas. Texto da pessoa (nomes de
// regras, de pacientes, mensagens) entra sempre como texto, nunca como HTML.

export function el(tag, atributos = {}, ...filhos) {
  const elemento = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (valor === undefined || valor === null || valor === false) continue;
    if (chave === "class") elemento.className = valor;
    else if (chave.startsWith("on")) elemento.addEventListener(chave.slice(2), valor);
    else if (valor === true) elemento.setAttribute(chave, "");
    else elemento.setAttribute(chave, valor);
  }
  for (const filho of filhos.flat()) {
    if (filho === null || filho === undefined || filho === false) continue;
    elemento.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
  }
  return elemento;
}

export function adiar(funcao, ms) {
  let relogio;
  return (...argumentos) => {
    clearTimeout(relogio);
    relogio = setTimeout(() => funcao(...argumentos), ms);
  };
}

// Oferece um texto para download (salvar regras, salvar roteiro).
export function baixar(texto, nomeDoArquivo) {
  const blob = new Blob([texto], { type: "text/plain;charset=utf-8" });
  const link = el("a", { href: URL.createObjectURL(blob), download: nomeDoArquivo });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
