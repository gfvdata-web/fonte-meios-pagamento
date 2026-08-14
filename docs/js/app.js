/* ===== Painel Meios de Pagamento — Etapa 6 =====
   Consome docs/dados/meios_pagamento_mensal.json (gerado pela Etapa 5). */

const ARQUIVO_DADOS = "dados/meios_pagamento_mensal.json";
const CORES = {
  Pix: "#0ea5a4", TED: "#2563eb", Boleto: "#f59e0b",
  Cheque: "#8b5cf6", TEC: "#ec4899", DOC: "#94a3b8",
};
const OCULTAR_INICIAL = ["DOC", "TEC"]; // legados ~zerados: começam desligados no gráfico

let dados = null;
let metrica = "valor"; // "valor" | "quantidade" | "ticket"
let graficoEvolucao = null;
let graficoParticipacao = null;

// Índices (em dados.labels) dos filtros de período de cada cartão.
let rankInicio = 0, rankFim = 0;
let estInicio = 0, estFim = 0;

// ---------- Formatação ----------
const nf = (casas = 1) => new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: casas, maximumFractionDigits: casas,
});

/** valor em R$ milhões -> texto compacto. */
function fmtValor(x) {
  if (x == null) return "—";
  const abs = Math.abs(x);
  if (abs >= 1e6) return `R$ ${nf(2).format(x / 1e6)} tri`;
  if (abs >= 1e3) return `R$ ${nf(1).format(x / 1e3)} bi`;
  return `R$ ${nf(0).format(x)} mi`;
}

/** quantidade em milhares -> texto compacto. */
function fmtQtd(x) {
  if (x == null) return "—";
  const abs = Math.abs(x);
  if (abs >= 1e6) return `${nf(2).format(x / 1e6)} bi`;
  if (abs >= 1e3) return `${nf(1).format(x / 1e3)} mi`;
  return `${nf(0).format(x)} mil`;
}

/** valor em R$ milhões -> texto exato para números pequenos (não some em "0 mi"). */
function fmtValorPreciso(x) {
  if (x == null) return "—";
  const abs = Math.abs(x);
  if (abs >= 1e6) return `R$ ${nf(2).format(x / 1e6)} tri`;
  if (abs >= 1e3) return `R$ ${nf(1).format(x / 1e3)} bi`;
  if (abs >= 1) return `R$ ${nf(0).format(x)} mi`;
  if (abs < 0.005) return "R$ 0 mi";            // próximo de zero -> 0
  return `R$ ${nf(2).format(x)} mi`;            // ex.: 0,06 -> "R$ 0,06 mi"
}

/** quantidade em milhares -> texto exato para números pequenos. */
function fmtQtdPreciso(x) {
  if (x == null) return "—";
  const abs = Math.abs(x);
  if (abs >= 1e6) return `${nf(2).format(x / 1e6)} bi`;
  if (abs >= 1e3) return `${nf(1).format(x / 1e3)} mi`;
  if (abs >= 1) return `${nf(0).format(x)} mil`;
  if (abs < 0.005) return "0 mil";
  return `${nf(2).format(x)} mil`;
}

/** ticket médio em R$ -> texto (valor "cheio", já que é por transação, não em milhões/milhares). */
function fmtTicket(x) {
  if (x == null) return "—";
  return `R$ ${nf(2).format(x)}`;
}

const fmtMetrica = (x) => {
  if (metrica === "quantidade") return fmtQtd(x);
  if (metrica === "ticket") return fmtTicket(x);
  return fmtValor(x);
};

function fmtPct(x, comSinal = false) {
  if (x == null) return "—";
  const s = comSinal && x > 0 ? "+" : "";
  return `${s}${nf(1).format(x)}%`;
}

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** "2026-05" -> "mai/2026" */
function fmtMesAno(anoMes) {
  const [a, m] = anoMes.split("-");
  return `${MESES[Number(m) - 1]}/${a}`;
}

/** "2026-05" -> "mai/26" (formato mmm/aa, usado nos filtros). */
function fmtMesAnoCurto(anoMes) {
  const [a, m] = anoMes.split("-");
  return `${MESES[Number(m) - 1]}/${a.slice(2)}`;
}

/** "2026-05" -> "2025-05" (mesmo mês do ano anterior). */
function mesAnoAnterior(anoMes) {
  const [a, m] = anoMes.split("-");
  return `${Number(a) - 1}-${m}`;
}

const cssVar = (nome) => getComputedStyle(document.body).getPropertyValue(nome).trim();

// ---------- Cálculos por período (recalculados no cliente conforme os filtros) ----------
const num = (x) => (x == null ? 0 : x);

/** Calcula e guarda em dados.series[forma].ticket a série de ticket médio (R$/transação). */
function prepararSeriesTicket() {
  dados.formas.forEach((f) => {
    const v = dados.series[f].valor, q = dados.series[f].quantidade;
    dados.series[f].ticket = v.map((valor, i) => {
      const qtd = q[i];
      if (valor == null || qtd == null || qtd === 0) return null;
      return (valor * 1000) / qtd; // valor em R$ mi, qtd em mil transações -> R$/transação
    });
  });
}

/** YoY (%) do índice i vs. 12 meses antes, na série completa. */
function yoyValor(serie, i) {
  if (i < 12) return null;
  const atual = serie[i], anterior = serie[i - 12];
  if (atual == null || anterior == null || anterior === 0) return null;
  return (atual / anterior - 1) * 100;
}

/** CAGR anual (%) entre o 1º e o último valor positivo dentro do intervalo [i0, i1]. */
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

/** Ranking por forma no intervalo [i0, i1]. Mês de referência = i1. */
function calcularRanking(i0, i1) {
  let valorGeral = 0, qtdGeral = 0;
  dados.formas.forEach((f) => {
    const v = dados.series[f].valor, q = dados.series[f].quantidade;
    for (let k = i0; k <= i1; k++) { valorGeral += num(v[k]); qtdGeral += num(q[k]); }
  });

  const linhas = dados.formas.map((f) => {
    const v = dados.series[f].valor, q = dados.series[f].quantidade;
    let valorTotal = 0, qtdTotal = 0;
    for (let k = i0; k <= i1; k++) { valorTotal += num(v[k]); qtdTotal += num(q[k]); }
    const valUlt = num(v[i1]), qtdUlt = num(q[i1]);
    return {
      forma: f,
      valor_total: valorTotal,
      part_valor_pct: valorGeral ? valorTotal / valorGeral * 100 : null,
      part_qtd_pct: qtdGeral ? qtdTotal / qtdGeral * 100 : null,
      valor_ultimo: valUlt,
      yoy_valor_pct: yoyValor(v, i1),
      cagr_valor_aa_pct: cagrAA(v, i0, i1),
      ticket_medio_ultimo_rs: qtdUlt ? (valUlt * 1000) / qtdUlt : null,
    };
  });
  linhas.sort((a, b) => b.valor_total - a.valor_total);
  return linhas;
}

/** Estatística descritiva da série `metricaLocal` da `forma` no intervalo [i0, i1]. */
function calcularEstatistica(forma, metricaLocal, i0, i1) {
  const serie = dados.series[forma][metricaLocal];
  const arr = [];
  for (let k = i0; k <= i1; k++) { if (serie[k] != null) arr.push(serie[k]); }
  const n = arr.length;
  const vazio = { media: null, mediana: null, desvio_padrao: null, coef_variacao_pct: null, minimo: null, maximo: null };
  if (!n) return vazio;

  const media = arr.reduce((s, x) => s + x, 0) / n;
  const ord = [...arr].sort((a, b) => a - b);
  const mediana = n % 2 ? ord[(n - 1) / 2] : (ord[n / 2 - 1] + ord[n / 2]) / 2;
  let desvio = null;
  if (n > 1) {
    const soma2 = arr.reduce((s, x) => s + (x - media) ** 2, 0);
    desvio = Math.sqrt(soma2 / (n - 1)); // amostral (ddof=1), igual ao pandas
  }
  return {
    media,
    mediana,
    desvio_padrao: desvio,
    coef_variacao_pct: (media && desvio) ? desvio / media * 100 : null,
    minimo: Math.min(...arr),
    maximo: Math.max(...arr),
  };
}

// ---------- Renderização ----------
function renderCabecalho() {
  const meta = dados.meta;
  document.getElementById("descricao-fonte").textContent = meta.descricao;
  document.getElementById("meta-info").textContent =
    `Período: ${fmtMesAno(meta.periodo.inicio)} – ${fmtMesAno(meta.periodo.fim)} · `
    + `${dados.kpis.totais.meses_cobertos} meses · Atualizado em `
    + `${new Date(meta.gerado_em).toLocaleDateString("pt-BR")}`;
  document.getElementById("rodape-fonte").textContent = `Fonte: ${meta.fonte}.`;
}

function renderKpis() {
  const t = dados.kpis.totais;
  const lider = dados.kpis.por_forma[0];
  const p = dados.meta.periodo;
  const mesRef = fmtMesAno(t.mes_ref);
  const periodoTxt = `${fmtMesAno(p.inicio)} – ${fmtMesAno(p.fim)}`;
  const alvo = document.getElementById("kpis");
  const cartoes = [
    {
      rotulo: `Valor movimentado — ${mesRef}`,
      valor: fmtValor(t.valor_ultimo_mes),
      apoio: `Soma de todas as formas no mês de referência (${mesRef})`,
    },
    {
      rotulo: `Transações — ${mesRef}`,
      valor: fmtQtd(t.qtd_ultimo_mes),
      apoio: `Total de transações no mês de referência (${mesRef})`,
    },
    {
      rotulo: "Forma líder por valor",
      valor: lider.forma,
      apoio: `${fmtPct(lider.part_valor_pct)} do valor acumulado no período ${periodoTxt}`,
    },
    {
      rotulo: "Crescimento YoY do líder",
      valor: fmtPct(lider.yoy_valor_pct, true),
      apoio: `${lider.forma} · ${mesRef} vs. ${fmtMesAno(mesAnoAnterior(t.mes_ref))}`,
      classe: lider.yoy_valor_pct == null ? "" : (lider.yoy_valor_pct >= 0 ? "pos" : "neg"),
    },
  ];
  alvo.innerHTML = cartoes.map((c) => `
    <div class="kpi">
      <p class="rotulo">${c.rotulo}</p>
      <p class="valor">${c.valor}</p>
      <p class="apoio ${c.classe || ""}">${c.apoio}</p>
    </div>`).join("");
}

function renderEvolucao() {
  const ctx = document.getElementById("gEvolucao");
  const datasets = dados.formas.map((forma) => ({
    label: forma,
    data: dados.series[forma][metrica],
    borderColor: CORES[forma],
    backgroundColor: CORES[forma],
    borderWidth: 2,
    pointRadius: 0,
    pointHoverRadius: 4,
    tension: 0.3,
    hidden: OCULTAR_INICIAL.includes(forma),
  }));

  document.getElementById("titulo-evolucao").textContent =
    metrica === "valor"
      ? "Valor movimentado por forma (R$), por mês."
      : metrica === "ticket"
      ? "Ticket médio por transação, por forma, por mês."
      : "Quantidade de transações por forma, por mês.";

  if (graficoEvolucao) graficoEvolucao.destroy();
  graficoEvolucao = new Chart(ctx, {
    type: "line",
    data: { labels: dados.labels.map(fmtMesAno), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: cssVar("--texto"), usePointStyle: true, boxWidth: 8 } },
        tooltip: {
          callbacks: { label: (i) => `${i.dataset.label}: ${fmtMetrica(i.parsed.y)}` },
        },
      },
      scales: {
        x: {
          ticks: { color: cssVar("--texto-suave"), maxTicksLimit: 12, autoSkip: true },
          grid: { display: false },
        },
        y: {
          ticks: { color: cssVar("--texto-suave"), callback: (v) => fmtMetrica(v) },
          grid: { color: cssVar("--borda") },
        },
      },
    },
  });
}

function renderParticipacao() {
  const ctx = document.getElementById("gParticipacao");
  // Ticket médio não é uma grandeza somável (não há "fatia" de ticket médio);
  // nesse caso o gráfico mostra a participação por valor como referência.
  const campoMetrica = metrica === "ticket" ? "valor" : metrica;
  const campo = campoMetrica === "valor" ? "valor_total" : "qtd_total";
  const itens = [...dados.kpis.por_forma].sort((a, b) => b[campo] - a[campo]);
  const total = itens.reduce((s, x) => s + x[campo], 0);

  document.getElementById("titulo-participacao").textContent =
    metrica === "valor"
      ? "Fatia de cada forma no valor acumulado."
      : metrica === "ticket"
      ? "Ticket médio não é somável — exibindo fatia por valor acumulado como referência."
      : "Fatia de cada forma na quantidade acumulada.";

  if (graficoParticipacao) graficoParticipacao.destroy();
  graficoParticipacao = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: itens.map((x) => x.forma),
      datasets: [{
        data: itens.map((x) => x[campo]),
        backgroundColor: itens.map((x) => CORES[x.forma]),
        borderColor: cssVar("--superficie"),
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "58%",
      plugins: {
        legend: { position: "bottom", labels: { color: cssVar("--texto"), usePointStyle: true, boxWidth: 8 } },
        tooltip: {
          callbacks: {
            label: (i) => {
              const pct = total ? (i.parsed / total) * 100 : 0;
              const bruto = campoMetrica === "valor" ? fmtValor(i.parsed) : fmtQtd(i.parsed);
              return `${i.label}: ${bruto} (${fmtPct(pct)})`;
            },
          },
        },
      },
    },
  });
}

function pilulaForma(forma) {
  return `<span class="pilula"><span class="ponto" style="background:${CORES[forma]}"></span>${forma}</span>`;
}

function cls(x) { return x == null ? "nulo" : x >= 0 ? "pos" : "neg"; }

function renderTabelaRanking() {
  const corpo = document.querySelector("#tabela-ranking tbody");
  const mesRefTxt = fmtMesAnoCurto(dados.labels[rankFim]);
  document.getElementById("desc-ranking").textContent =
    `Período ${fmtMesAnoCurto(dados.labels[rankInicio])}–${fmtMesAnoCurto(dados.labels[rankFim])}. `
    + `Participação e CAGR no período; YoY, valor e ticket médio referem-se ao mês final (${mesRefTxt}).`;

  const linhas = calcularRanking(rankInicio, rankFim);
  corpo.innerHTML = linhas.map((f) => `
    <tr>
      <td>${pilulaForma(f.forma)}</td>
      <td class="num">${fmtPct(f.part_valor_pct)}</td>
      <td class="num">${fmtPct(f.part_qtd_pct)}</td>
      <td class="num">${fmtValor(f.valor_ultimo)}</td>
      <td class="num ${cls(f.yoy_valor_pct)}">${fmtPct(f.yoy_valor_pct, true)}</td>
      <td class="num ${cls(f.cagr_valor_aa_pct)}">${fmtPct(f.cagr_valor_aa_pct, true)}</td>
      <td class="num">${f.ticket_medio_ultimo_rs == null ? "—" : "R$ " + nf(2).format(f.ticket_medio_ultimo_rs)}</td>
    </tr>`).join("");
}

function renderTabelaEstatistica() {
  const corpo = document.querySelector("#tabela-estatistica tbody");
  const fmt = metrica === "quantidade" ? fmtQtd : metrica === "ticket" ? fmtTicket : fmtValor;
  const fmtExato = metrica === "quantidade" ? fmtQtdPreciso : metrica === "ticket" ? fmtTicket : fmtValorPreciso;
  const rotuloMetrica = metrica === "quantidade" ? "quantidade" : metrica === "ticket" ? "ticket médio (R$)" : "valor (R$)";
  document.getElementById("titulo-estatistica").textContent =
    `Série mensal no período ${fmtMesAnoCurto(dados.labels[estInicio])}–${fmtMesAnoCurto(dados.labels[estFim])} `
    + `— métrica: ${rotuloMetrica}.`;

  corpo.innerHTML = dados.formas.map((forma) => {
    const e = calcularEstatistica(forma, metrica, estInicio, estFim);
    return `
      <tr>
        <td>${pilulaForma(forma)}</td>
        <td class="num">${fmt(e.media)}</td>
        <td class="num">${fmt(e.mediana)}</td>
        <td class="num">${fmt(e.desvio_padrao)}</td>
        <td class="num">${fmtPct(e.coef_variacao_pct)}</td>
        <td class="num">${fmtExato(e.minimo)}</td>
        <td class="num">${fmtExato(e.maximo)}</td>
      </tr>`;
  }).join("");
}

function renderMetricaDependente() {
  renderEvolucao();
  renderParticipacao();
  renderTabelaEstatistica();
}

function ligarAlternador() {
  document.querySelectorAll(".alt-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.metrica === metrica) return;
      document.querySelectorAll(".alt-btn").forEach((b) => b.classList.remove("ativo"));
      btn.classList.add("ativo");
      metrica = btn.dataset.metrica;
      renderMetricaDependente();
    });
  });
}

/** Preenche um <select> com todos os meses (mmm/aa) e marca o índice atual. */
function preencherSelectMeses(sel, idxSelecionado) {
  sel.innerHTML = dados.labels
    .map((l, i) => `<option value="${i}">${fmtMesAnoCurto(l)}</option>`)
    .join("");
  sel.value = String(idxSelecionado);
}

function ligarFiltroRanking() {
  const selI = document.getElementById("ranking-inicio");
  const selF = document.getElementById("ranking-fim");
  preencherSelectMeses(selI, rankInicio);
  preencherSelectMeses(selF, rankFim);
  selI.addEventListener("change", () => {
    rankInicio = Number(selI.value);
    if (rankInicio > rankFim) { rankFim = rankInicio; selF.value = String(rankFim); }
    renderTabelaRanking();
  });
  selF.addEventListener("change", () => {
    rankFim = Number(selF.value);
    if (rankFim < rankInicio) { rankInicio = rankFim; selI.value = String(rankInicio); }
    renderTabelaRanking();
  });
}

function ligarFiltroEstatistica() {
  const selI = document.getElementById("est-inicio");
  const selF = document.getElementById("est-fim");
  preencherSelectMeses(selI, estInicio);
  preencherSelectMeses(selF, estFim);
  selI.addEventListener("change", () => {
    estInicio = Number(selI.value);
    if (estInicio > estFim) { estFim = estInicio; selF.value = String(estFim); }
    renderTabelaEstatistica();
  });
  selF.addEventListener("change", () => {
    estFim = Number(selF.value);
    if (estFim < estInicio) { estInicio = estFim; selI.value = String(estInicio); }
    renderTabelaEstatistica();
  });
}

async function iniciar() {
  try {
    const resp = await fetch(ARQUIVO_DADOS);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    dados = await resp.json();
  } catch (erro) {
    document.getElementById("meta-info").textContent =
      "Não foi possível carregar os dados. Rode o pipeline (python run_pipeline.py) para gerar "
      + `${ARQUIVO_DADOS}.`;
    console.error(erro);
    return;
  }

  prepararSeriesTicket();

  // Filtros começam cobrindo todo o período disponível.
  const ultimo = dados.labels.length - 1;
  rankInicio = 0; rankFim = ultimo;
  estInicio = 0; estFim = ultimo;

  renderCabecalho();
  renderKpis();
  ligarFiltroRanking();
  ligarFiltroEstatistica();
  renderTabelaRanking();
  renderMetricaDependente();
  ligarAlternador();
}

iniciar();
