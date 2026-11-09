// Logica do mapa, sem DOM: o que pode ser testado com `node --test`.

const RAIO_TERRA_KM = 6371;

// Distancia em linha reta (haversine), como o roteirizador usa por padrao.
export function distanciaKm(a, b) {
  const rad = (g) => (g * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 +
            Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * RAIO_TERRA_KM * Math.asin(Math.sqrt(h));
}

// Trechos percorridos no turno, na ordem: da UBS a cada visita e de volta.
// Quando uma visita exige passar na UBS antes (para repor material), o
// trecho vira dois, indo e voltando da UBS ("desvio").
export function trechosDaRota(r) {
  const ubs = r.pontos[r.rota[0]];
  const trechos = [];
  let anterior = ubs;
  for (const parada of r.paradas) {
    const destino = r.pontos[parada.paciente.id] ?? parada.paciente;
    if (parada.desvio_ubs && anterior !== ubs) {
      trechos.push({ de: anterior, para: ubs, tipo: "desvio", antesDe: parada.ordem });
      trechos.push({ de: ubs, para: destino, tipo: "desvio", antesDe: parada.ordem });
    } else {
      trechos.push({ de: anterior, para: destino, tipo: "visita", antesDe: parada.ordem });
    }
    anterior = destino;
  }
  if (anterior !== ubs) trechos.push({ de: anterior, para: ubs, tipo: "retorno", antesDe: null });
  return trechos.map((t) => ({ ...t, km: distanciaKm(t.de, t.para) }));
}

// Total percorrido e quanto as passagens pela UBS acrescentam em relacao a
// ir direto da visita anterior para a seguinte.
export function resumoDaRota(r) {
  const trechos = trechosDaRota(r);
  let kmAMaisPelaUbs = 0;
  let desvios = 0;
  trechos.forEach((t, i) => {
    const volta = trechos[i + 1];
    if (t.tipo === "desvio" && volta?.tipo === "desvio" && volta.antesDe === t.antesDe) {
      kmAMaisPelaUbs += t.km + volta.km - distanciaKm(t.de, volta.para);
      desvios += 1;
    }
  });
  return { km: trechos.reduce((total, t) => total + t.km, 0), kmAMaisPelaUbs, desvios };
}

// "2,4 km"; abaixo de 1 km, em metros arredondados
export function textoKm(km) {
  if (km < 1) return `${Math.round(km * 1000 / 10) * 10} m`;
  return `${String(Math.round(km * 10) / 10).replace(".", ",")} km`;     // 2,4 km; 1 km
}

// Pontos que aparecem no mapa: UBS, visitas (com a ordem) e adiados.
export function pontosDoMapa(r) {
  const ubs = r.pontos[r.rota[0]];
  const visitas = r.paradas.map((p) => ({ ...(r.pontos[p.paciente.id] ?? p.paciente), parada: p }));
  const adiados = r.selecao.adiados.map((id) => r.pontos[id]).filter(Boolean);
  return { ubs, visitas, adiados };
}

// Projecao simples para o desenho sem internet: equiretangular, com a
// longitude encolhida pelo cosseno da latitude media (em escala de bairro,
// a distorcao e desprezivel). Mantem a proporcao e centraliza.
export function projetar(pontos, largura, altura, margem = 30) {
  const validos = pontos.filter((p) => Number.isFinite(p?.lat) && Number.isFinite(p?.lon));
  if (!validos.length) return () => ({ x: largura / 2, y: altura / 2 });
  const latMedia = validos.reduce((s, p) => s + p.lat, 0) / validos.length;
  const fator = Math.cos((latMedia * Math.PI) / 180);
  const xs = validos.map((p) => p.lon * fator);
  const ys = validos.map((p) => p.lat);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const escala = Math.min((largura - 2 * margem) / ((maxX - minX) || 1e-9),
                          (altura - 2 * margem) / ((maxY - minY) || 1e-9));
  const sobraX = (largura - 2 * margem - (maxX - minX) * escala) / 2;
  const sobraY = (altura - 2 * margem - (maxY - minY) * escala) / 2;
  return (p) => ({
    x: margem + sobraX + (p.lon * fator - minX) * escala,
    y: altura - (margem + sobraY + (p.lat - minY) * escala),      // norte para cima
  });
}

// Barra de escala "redonda" (100 m, 200 m, 500 m, 1 km...) que caiba em
// `maximoPx` pixels, dada a escala em km por pixel.
export function barraDeEscala(kmPorPixel, maximoPx = 120) {
  const opcoes = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 20, 50];
  const km = [...opcoes].reverse().find((k) => k / kmPorPixel <= maximoPx) ?? opcoes[0];
  return { km, px: km / kmPorPixel, texto: textoKm(km) };
}
