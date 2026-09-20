/* ===== Meios de Pagamento — v2 (experimental) =====
   Consome o mesmo dados/meios_pagamento_mensal.json da v1, mas com layout,
   narrativa e gráficos próprios. Nada aqui é compartilhado com js/app.js. */

const ARQUIVO_DADOS = "dados/meios_pagamento_mensal.json";
const CORES = {
  Pix: "#2a78d6", TED: "#eb6834", Boleto: "#1baf7a",
  Cheque: "#eda100", TEC: "#e87ba4", DOC: "#4a3aa7",
};
const PERIODOS = [
  { codigo: "tudo", rotulo: "Desde sempre" },
  { codigo: "10a", rotulo: "10A" },
  { codigo: "5a", rotulo: "5A" },
  { codigo: "1a", rotulo: "1A" },
  { codigo: "ytd", rotulo: "YTD" },
];

if (window.ChartDataLabels) Chart.register(window.ChartDataLabels);

let dados = null;
let graficoParticipacao = null;
let graficoEvolucao = null;

let participMetrica = "quantidade"; // "quantidade" | "valor"
let participPeriodo = "10a";
let evoMetrica = "quantidade";      // "quantidade" | "valor" | "ticket"
let evoPeriodo = "5a";

// ---------- Formatação ----------
const nf = (casas = 1) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const fmtMesAno = (anoMes) => { const [a, m] = anoMes.split("-"); return `${MESES[Number(m) - 1]}/${a}`; };
const fmtPct = (x, casas = 1) => (x == null ? "—" : `${nf(casas).format(x)}%`);

function fmtValor(x) {
  if (x == null) return "—";
  const abs = Math.abs(x);
  if (abs >= 1e6) return `R$ ${nf(2).format(x / 1e6)} tri`;
  if (abs >= 1e3) return `R$ ${nf(1).format(x / 1e3)} bi`;
  return `R$ ${nf(0).format(x)} mi`;
}
function fmtQtd(x) {
  if (x == null) return "—";
  const abs = Math.abs(x);
  if (abs >= 1e6) return `${nf(2).format(x / 1e6)} bi`;
  if (abs >= 1e3) return `${nf(1).format(x / 1e3)} mi`;
  return `${nf(0).format(x)} mil`;
}
function fmtTicket(x) { return x == null ? "—" : `R$ ${nf(2).format(x)}`; }
function fmtCampo(campo, x) {
  if (campo === "quantidade") return fmtQtd(x);
  if (campo === "ticket") return fmtTicket(x);
  return fmtValor(x);
}
const rotuloMetrica = (campo) => campo === "quantidade" ? "quantidade" : campo === "ticket" ? "ticket médio" : "valor";
const cssVar = (nome) => getComputedStyle(document.body).getPropertyValue(nome).trim();
const num = (x) => (x == null ? 0 : x);

function pilulaForma(forma) {
  return `<span class="pilula-forma"><span class="ponto-v2" style="background:${CORES[forma]}"></span>${forma}</span>`;
}

/** Calcula e guarda em dados.series[forma].ticket a série de ticket médio (R$/transação). */
function prepararSeriesTicket() {
  dados.formas.forEach((f) => {
    const v = dados.series[f].valor, q = dados.series[f].quantidade;
    dados.series[f].ticket = v.map((valor, i) => {
      const qtd = q[i];
      if (valor == null || qtd == null || qtd === 0) return null;
      return (valor * 1000) / qtd;
    });
  });
}

/** Converte um código de período em índices [i0, i1] sobre dados.labels. */
function periodoParaIndices(codigo) {
  const last = dados.labels.length - 1;
  if (codigo === "10a") return [Math.max(0, last - 119), last];
  if (codigo === "5a") return [Math.max(0, last - 59), last];
  if (codigo === "1a") return [Math.max(0, last - 11), last];
  if (codigo === "ytd") {
    const anoAtual = dados.labels[last].slice(0, 4);
    const idx = dados.labels.findIndex((l) => l.startsWith(anoAtual));
    return [idx < 0 ? last : idx, last];
  }
  return [0, last]; // "tudo"
}

/** CAGR anual (%) entre o 1º e o último valor positivo da série dentro de [i0, i1]. */
function cagrAA(serie, i0, i1) {
  let iPrim = -1, iUlt = -1;
  for (let k = i0; k <= i1; k++) {
    if (serie[k] != null && serie[k] > 0) { if (iPrim < 0) iPrim = k; iUlt = k; }
  }
  if (iPrim < 0 || iUlt === iPrim) return null;
  const v0 = serie[iPrim], vn = serie[iUlt];
  const anos = (iUlt - iPrim) / 12;
  if (anos <= 0 || v0 <= 0) return null;
  return ((vn / v0) ** (1 / anos) - 1) * 100;
}

/** "2026-05" -> "2º/26" (trimestre + ano curto). */
function fmtTrimestre(anoMes) {
  const [a, m] = anoMes.split("-");
  const tri = Math.floor((Number(m) - 1) / 3) + 1;
  return `${tri}º/${a.slice(2)}`;
}

/** Agrega a série mensal por trimestre-calendário dentro de [i0, i1] e calcula a fatia (%) de cada forma por período. */
function agregarParticipacaoPorTrimestre(i0, i1, campo) {
  const periodos = [];
  const somaPorPeriodo = {}; // chave "ano-Tn" -> {forma: soma}
  for (let k = i0; k <= i1; k++) {
    const label = dados.labels[k];
    const tri = Math.floor((Number(label.slice(5, 7)) - 1) / 3) + 1;
    const chave = `${label.slice(0, 4)}-T${tri}`;
    if (!somaPorPeriodo[chave]) { somaPorPeriodo[chave] = { rotulo: fmtTrimestre(label) }; periodos.push(chave); }
    dados.formas.forEach((f) => {
      const v = num(dados.series[f][campo][k]);
      somaPorPeriodo[chave][f] = (somaPorPeriodo[chave][f] || 0) + v;
    });
  }
  const rotulos = periodos.map((p) => somaPorPeriodo[p].rotulo);
  const share = {}; // forma -> [% por período, na mesma ordem de `periodos`]
  dados.formas.forEach((f) => { share[f] = []; });
  periodos.forEach((p) => {
    const total = dados.formas.reduce((s, f) => s + somaPorPeriodo[p][f], 0);
    dados.formas.forEach((f) => {
      share[f].push(total ? (somaPorPeriodo[p][f] / total) * 100 : null);
    });
  });
  return { periodos: rotulos, share };
}

// ---------- Renderização: cabeçalho ----------
function renderCabecalho() {
  const meta = dados.meta;
  document.getElementById("meta-periodo").textContent =
    `${fmtMesAno(meta.periodo.inicio)} a ${fmtMesAno(meta.periodo.fim)}`;
  document.getElementById("rodape-fonte-v2").textContent =
    `Fonte: ${meta.fonte}. Atualizado em ${new Date(meta.gerado_em).toLocaleDateString("pt-BR")}.`;
}

// ---------- Narrativa ----------
function liderPorQuantidade() {
  return [...dados.kpis.por_forma].sort((a, b) => b.part_qtd_pct - a.part_qtd_pct)[0];
}

function renderNarrativaAbertura() {
  const lider = liderPorQuantidade();
  const mesRef = dados.kpis.totais.mes_ref;
  const anoInicio = dados.meta.periodo.inicio.slice(0, 4);
  document.getElementById("txt-abertura").innerHTML =
    `Desde ${anoInicio}, o Banco Central acompanha, mês a mês, como o Brasil movimenta dinheiro. `
    + `Hoje, em ${fmtMesAno(mesRef)}, o <strong>${lider.forma}</strong> já responde por `
    + `<strong>${fmtPct(lider.part_qtd_pct)}</strong> de todas as transações registradas — `
    + `a maior fatia entre as seis formas de pagamento acompanhadas nesta série.`;
}

function renderNarrativaMeio(periodos, share) {
  const alvo = document.getElementById("txt-meio");
  if (periodos.length < 2) {
    const ultimos = dados.formas
      .map((f) => ({ forma: f, pct: share[f][share[f].length - 1] }))
      .filter((x) => x.pct != null)
      .sort((a, b) => b.pct - a.pct);
    const [top1, top2] = ultimos;
    alvo.innerHTML = top1
      ? `No trimestre ${periodos[0] || "—"}, considerando ${rotuloMetrica(participMetrica)}, o <strong>${top1.forma}</strong> `
        + `liderava com ${fmtPct(top1.pct)}${top2 ? `, seguido por <strong>${top2.forma}</strong> (${fmtPct(top2.pct)})` : ""}.`
      : "Sem dados suficientes no período selecionado.";
    return;
  }
  const iIni = 0, iFim = periodos.length - 1;
  let maiorGanho = null, maiorPerda = null;
  dados.formas.forEach((f) => {
    const ini = share[f][iIni], fim = share[f][iFim];
    if (ini == null || fim == null) return;
    const delta = fim - ini;
    if (!maiorGanho || delta > maiorGanho.delta) maiorGanho = { forma: f, ini, fim, delta };
    if (!maiorPerda || delta < maiorPerda.delta) maiorPerda = { forma: f, ini, fim, delta };
  });
  if (!maiorGanho) { alvo.textContent = "Sem dados suficientes no período selecionado."; return; }
  alvo.innerHTML =
    `Entre ${periodos[iIni]} e ${periodos[iFim]}, a participação do <strong>${maiorGanho.forma}</strong> `
    + `(em ${rotuloMetrica(participMetrica)}) passou de ${fmtPct(maiorGanho.ini)} para ${fmtPct(maiorGanho.fim)}`
    + (maiorPerda && maiorPerda.forma !== maiorGanho.forma
      ? `, enquanto o <strong>${maiorPerda.forma}</strong> perdeu espaço: de ${fmtPct(maiorPerda.ini)} para ${fmtPct(maiorPerda.fim)}.`
      : ".");
}

function renderNarrativaFechamento(i0, i1) {
  const campo = evoMetrica === "ticket" ? "ticket" : evoMetrica;
  const ranking = dados.formas
    .map((f) => ({ forma: f, fim: dados.series[f][campo][i1], cagr: cagrAA(dados.series[f][campo], i0, i1) }))
    .filter((x) => x.fim != null)
    .sort((a, b) => b.fim - a.fim);
  const alvo = document.getElementById("txt-fechamento");
  const lider = ranking[0];
  if (!lider || lider.cagr == null) {
    alvo.textContent = "Não há variação suficiente no período selecionado para calcular uma taxa de crescimento.";
    return;
  }
  const contraste = ranking.find((x) => x.forma !== lider.forma && x.cagr != null);
  alvo.innerHTML =
    `No período de ${fmtMesAno(dados.labels[i0])} a ${fmtMesAno(dados.labels[i1])}, o <strong>${lider.forma}</strong> `
    + `cresceu a uma taxa média de ${fmtPct(lider.cagr, 1)} ao ano em ${rotuloMetrica(evoMetrica)}`
    + (contraste
      ? `, enquanto o <strong>${contraste.forma}</strong> ${contraste.cagr >= 0 ? "avançou" : "recuou"} `
        + `${fmtPct(Math.abs(contraste.cagr), 1)} ao ano no mesmo período.`
      : ".");
}

// ---------- Gráfico 1: participação por trimestre (colunas empilhadas) ----------
function renderGraficoParticipacao() {
  const [i0, i1] = periodoParaIndices(participPeriodo);
  const { periodos, share } = agregarParticipacaoPorTrimestre(i0, i1, participMetrica);

  document.getElementById("desc-participacao").textContent =
    `Fatia de cada forma de pagamento no total de ${rotuloMetrica(participMetrica)} de cada trimestre `
    + `(${periodos[0] || "—"}–${periodos[periodos.length - 1] || "—"}).`;

  const ctx = document.getElementById("gParticipacaoAno");
  const datasets = dados.formas.map((f) => ({
    label: f,
    data: share[f],
    backgroundColor: CORES[f],
    maxBarThickness: 46,
    datalabels: {
      color: "#fff",
      font: { family: "IBM Plex Sans", weight: 700, size: 10 },
      textStrokeColor: "rgba(0,0,0,.55)",
      textStrokeWidth: 3,
      formatter: (v) => (v != null && v >= 6 ? `${Math.round(v)}%` : ""),
    },
  }));

  // Cada trimestre é uma única coluna empilhada; abaixo desse limite de espaço por
  // coluna, a área do gráfico cresce e vira scroll horizontal em vez de espremer.
  const PX_POR_GRUPO = 34;
  const wrapper = document.getElementById("participacaoScrollInner");
  const larguraMinima = periodos.length * PX_POR_GRUPO;
  const larguraContainer = wrapper.parentElement.clientWidth;
  wrapper.style.width = larguraMinima > larguraContainer ? `${larguraMinima}px` : "100%";

  if (graficoParticipacao) graficoParticipacao.destroy();
  graficoParticipacao = new Chart(ctx, {
    type: "bar",
    data: { labels: periodos, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: cssVar("--texto"), usePointStyle: true, boxWidth: 8, font: { family: "IBM Plex Sans" } } },
        tooltip: { callbacks: { label: (i) => `${i.dataset.label}: ${fmtPct(i.parsed.y)}` } },
      },
      scales: {
        x: { stacked: true, ticks: { color: cssVar("--texto-suave"), autoSkip: true, maxRotation: 0 }, grid: { display: false } },
        y: {
          stacked: true, beginAtZero: true, max: 100,
          ticks: { color: cssVar("--texto-suave"), callback: (v) => `${v}%` },
          grid: { color: cssVar("--borda") },
        },
      },
    },
  });

  renderTabelaParticipacao(periodos, share);
  renderNarrativaMeio(periodos, share);
}

function renderTabelaParticipacao(periodos, share) {
  const thead = document.querySelector("#tabela-participacao thead");
  const tbody = document.querySelector("#tabela-participacao tbody");
  thead.innerHTML = `<tr><th>Forma</th>${periodos.map((p) => `<th>${p}</th>`).join("")}</tr>`;
  tbody.innerHTML = dados.formas.map((f) => `
    <tr><td>${pilulaForma(f)}</td>${share[f].map((v) => `<td>${fmtPct(v)}</td>`).join("")}</tr>
  `).join("");
}

// ---------- Gráfico 2: linha do tempo ----------
function renderGraficoEvolucao() {
  const [i0, i1] = periodoParaIndices(evoPeriodo);
  const campo = evoMetrica === "ticket" ? "ticket" : evoMetrica;
  const labelsPeriodo = dados.labels.slice(i0, i1 + 1);

  document.getElementById("desc-evolucao").textContent =
    `Série mensal de ${rotuloMetrica(evoMetrica)} por forma de pagamento, `
    + `de ${fmtMesAno(dados.labels[i0])} a ${fmtMesAno(dados.labels[i1])}.`;

  const ctx = document.getElementById("gEvolucaoV2");
  const datasets = dados.formas.map((f) => ({
    label: f,
    data: dados.series[f][campo].slice(i0, i1 + 1),
    borderColor: CORES[f],
    backgroundColor: CORES[f],
    borderWidth: 2,
    pointRadius: 0,
    pointHoverRadius: 4,
    tension: 0.25,
  }));

  if (graficoEvolucao) graficoEvolucao.destroy();
  graficoEvolucao = new Chart(ctx, {
    type: "line",
    data: { labels: labelsPeriodo.map(fmtMesAno), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: cssVar("--texto"), usePointStyle: true, boxWidth: 8, font: { family: "IBM Plex Sans" } } },
        tooltip: { callbacks: { label: (i) => `${i.dataset.label}: ${fmtCampo(campo, i.parsed.y)}` } },
        datalabels: { display: false },
      },
      scales: {
        x: { ticks: { color: cssVar("--texto-suave"), maxTicksLimit: 12, autoSkip: true }, grid: { display: false } },
        y: { ticks: { color: cssVar("--texto-suave"), callback: (v) => fmtCampo(campo, v) }, grid: { color: cssVar("--borda") } },
      },
    },
  });

  renderTabelaEvolucao(i0, i1, campo);
  renderNarrativaFechamento(i0, i1);
}

/** Tabela-resumo por ano (soma para valor/quantidade, média para ticket médio) — evita centenas de linhas mensais. */
function renderTabelaEvolucao(i0, i1, campo) {
  const anos = [];
  const agregPorAno = {};
  for (let k = i0; k <= i1; k++) {
    const ano = dados.labels[k].slice(0, 4);
    if (!agregPorAno[ano]) { agregPorAno[ano] = {}; anos.push(ano); }
    dados.formas.forEach((f) => {
      const v = dados.series[f][campo][k];
      if (!agregPorAno[ano][f]) agregPorAno[ano][f] = { soma: 0, n: 0 };
      if (v != null) { agregPorAno[ano][f].soma += v; agregPorAno[ano][f].n += 1; }
    });
  }
  const thead = document.querySelector("#tabela-evolucao thead");
  const tbody = document.querySelector("#tabela-evolucao tbody");
  thead.innerHTML = `<tr><th>Forma</th>${anos.map((a) => `<th>${a}</th>`).join("")}</tr>`;
  tbody.innerHTML = dados.formas.map((f) => `
    <tr><td>${pilulaForma(f)}</td>${anos.map((a) => {
      const c = agregPorAno[a][f];
      const val = c.n ? (campo === "ticket" ? c.soma / c.n : c.soma) : null;
      return `<td>${fmtCampo(campo, val)}</td>`;
    }).join("")}</tr>
  `).join("");
}

// ---------- Filtros / interação ----------
function montarPilulasPeriodo(container, estadoAtual, aoClicar) {
  container.innerHTML = PERIODOS.map((p) => `
    <button class="pilula-btn ${p.codigo === estadoAtual ? "ativo" : ""}" data-periodo="${p.codigo}">${p.rotulo}</button>
  `).join("");
  container.querySelectorAll(".pilula-btn").forEach((btn) => {
    btn.addEventListener("click", () => aoClicar(btn.dataset.periodo, container));
  });
}

function ligarFiltros() {
  document.querySelectorAll("[data-metrica-part]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.metricaPart === participMetrica) return;
      document.querySelectorAll("[data-metrica-part]").forEach((b) => b.classList.remove("ativo"));
      btn.classList.add("ativo");
      participMetrica = btn.dataset.metricaPart;
      renderGraficoParticipacao();
    });
  });

  document.querySelectorAll("[data-metrica-evo]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.metricaEvo === evoMetrica) return;
      document.querySelectorAll("[data-metrica-evo]").forEach((b) => b.classList.remove("ativo"));
      btn.classList.add("ativo");
      evoMetrica = btn.dataset.metricaEvo;
      renderGraficoEvolucao();
    });
  });

  const contPart = document.getElementById("periodo-participacao");
  montarPilulasPeriodo(contPart, participPeriodo, (codigo, cont) => {
    participPeriodo = codigo;
    cont.querySelectorAll(".pilula-btn").forEach((b) => b.classList.toggle("ativo", b.dataset.periodo === codigo));
    renderGraficoParticipacao();
  });

  const contEvo = document.getElementById("periodo-evolucao");
  montarPilulasPeriodo(contEvo, evoPeriodo, (codigo, cont) => {
    evoPeriodo = codigo;
    cont.querySelectorAll(".pilula-btn").forEach((b) => b.classList.toggle("ativo", b.dataset.periodo === codigo));
    renderGraficoEvolucao();
  });
}

async function iniciar() {
  try {
    const resp = await fetch(ARQUIVO_DADOS);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    dados = await resp.json();
  } catch (erro) {
    document.getElementById("txt-abertura").textContent =
      "Não foi possível carregar os dados. Rode o pipeline (python run_pipeline.py) para gerar "
      + `${ARQUIVO_DADOS}.`;
    console.error(erro);
    return;
  }

  prepararSeriesTicket();
  renderCabecalho();
  renderNarrativaAbertura();
  ligarFiltros();
  renderGraficoParticipacao();
  renderGraficoEvolucao();
}

iniciar();
