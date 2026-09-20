/* ===== Meios de Pagamento — v2 (experimental) =====
   Consome o mesmo dados/meios_pagamento_mensal.json da v1, mas com layout,
   narrativa e gráficos próprios. Nada aqui é compartilhado com js/app.js. */

const ARQUIVO_DADOS = "dados/meios_pagamento_mensal.json";
const ARQUIVO_EVENTOS = "dados/eventos_meios_pagamento.json";
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
if (window["chartjs-plugin-annotation"]) Chart.register(window["chartjs-plugin-annotation"]);

let dados = null;
let eventos = [];
let graficoParticipacao = null;
let graficoEvolucao = null;

let participMetrica = "quantidade"; // "quantidade" | "valor"
let participPeriodo = "10a";
let evoMetrica = "quantidade";      // "quantidade" | "valor" | "ticket"
let evoPeriodo = "5a";
let focoForma = "Pix";

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

/** Nº máximo de colunas legíveis na tela atual (mobile: 10, desktop: 25). */
function maxColunasTela() {
  return window.innerWidth < 760 ? 10 : 25;
}

const ROTULO_GRANULARIDADE = {
  mensal: "mês", trimestral: "trimestre", semestral: "semestre",
  anual: "ano", multianual: "período",
};

/** Escolhe a granularidade (mensal/trimestral/semestral/anual/blocos de N anos) mais próxima de
 *  ~20 colunas — o "ponto ideal" de leitura — sem nunca estourar o limite de colunas da tela. */
function escolherGranularidade(qtdMeses, maxColunas) {
  const ALVO_COLUNAS = 20;
  const ESCADA = [
    { codigo: "mensal", meses: 1 },
    { codigo: "trimestral", meses: 3 },
    { codigo: "semestral", meses: 6 },
    { codigo: "anual", meses: 12 },
  ];
  const bucketIdeal = qtdMeses / ALVO_COLUNAS;

  // Degrau mais próximo do ideal (pode ficar acima do limite da tela em janelas curtas na tela pequena).
  let escolha = ESCADA.reduce((melhor, o) =>
    Math.abs(o.meses - bucketIdeal) < Math.abs(melhor.meses - bucketIdeal) ? o : melhor, ESCADA[0]);
  if (Math.ceil(qtdMeses / escolha.meses) <= maxColunas) return escolha;

  // Não coube: sobe na escada até caber.
  const maisGrossa = ESCADA.filter((o) => o.meses > escolha.meses)
    .find((o) => Math.ceil(qtdMeses / o.meses) <= maxColunas);
  if (maisGrossa) return maisGrossa;

  // Nem anual coube (período muito longo numa tela pequena): agrupa em blocos de N anos.
  const anos = Math.ceil(qtdMeses / 12);
  const anosPorBloco = Math.ceil(anos / maxColunas);
  return { codigo: "multianual", anosPorBloco };
}

/** Agrega a série mensal na granularidade escolhida dentro de [i0, i1] e calcula a fatia (%) de cada forma por período. */
function agregarParticipacaoPorPeriodo(i0, i1, campo, granularidade) {
  const anoAncora = Number(dados.labels[i0].slice(0, 4));
  const periodos = [];
  const rotulos = {};
  const somaPorPeriodo = {};
  for (let k = i0; k <= i1; k++) {
    const label = dados.labels[k];
    const ano = Number(label.slice(0, 4));
    const mes = Number(label.slice(5, 7));
    let chave, rotulo;
    if (granularidade.codigo === "mensal") {
      chave = `${ano}-${mes}`; rotulo = fmtMesAno(label);
    } else if (granularidade.codigo === "trimestral") {
      const t = Math.floor((mes - 1) / 3) + 1;
      chave = `${ano}-T${t}`; rotulo = `${t}º/${String(ano).slice(2)}`;
    } else if (granularidade.codigo === "semestral") {
      const s = Math.floor((mes - 1) / 6) + 1;
      chave = `${ano}-S${s}`; rotulo = `S${s}/${String(ano).slice(2)}`;
    } else if (granularidade.codigo === "anual") {
      chave = `${ano}`; rotulo = `${ano}`;
    } else {
      const bloco = Math.floor((ano - anoAncora) / granularidade.anosPorBloco);
      const anoIni = anoAncora + bloco * granularidade.anosPorBloco;
      const anoFim = anoIni + granularidade.anosPorBloco - 1;
      chave = `B${bloco}`; rotulo = granularidade.anosPorBloco > 1 ? `${anoIni}–${anoFim}` : `${anoIni}`;
    }
    if (!somaPorPeriodo[chave]) { somaPorPeriodo[chave] = {}; periodos.push(chave); rotulos[chave] = rotulo; }
    dados.formas.forEach((f) => {
      const v = num(dados.series[f][campo][k]);
      somaPorPeriodo[chave][f] = (somaPorPeriodo[chave][f] || 0) + v;
    });
  }
  const rotulosOrdenados = periodos.map((p) => rotulos[p]);
  const share = {}; // forma -> [% por período, na mesma ordem de `periodos`]
  dados.formas.forEach((f) => { share[f] = []; });
  periodos.forEach((p) => {
    const total = dados.formas.reduce((s, f) => s + somaPorPeriodo[p][f], 0);
    dados.formas.forEach((f) => {
      share[f].push(total ? (somaPorPeriodo[p][f] / total) * 100 : null);
    });
  });
  return { periodos: rotulosOrdenados, share };
}

// ---------- Renderização: cabeçalho ----------
function renderCabecalho() {
  const meta = dados.meta;
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
    + `apesar de representar apenas <strong>${fmtPct(lider.part_valor_pct)}</strong> do valor total transacionado.`;
}

function renderNarrativaMeio(periodos, share, granularidade) {
  const alvo = document.getElementById("txt-meio");
  if (periodos.length < 2) {
    const ultimos = dados.formas
      .map((f) => ({ forma: f, pct: share[f][share[f].length - 1] }))
      .filter((x) => x.pct != null)
      .sort((a, b) => b.pct - a.pct);
    const [top1, top2] = ultimos;
    alvo.innerHTML = top1
      ? `No(a) ${ROTULO_GRANULARIDADE[granularidade.codigo]} ${periodos[0] || "—"}, considerando ${rotuloMetrica(participMetrica)}, o <strong>${top1.forma}</strong> `
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
  const foco = ranking.find((x) => x.forma === focoForma) || ranking[0];
  if (!foco || foco.cagr == null) {
    alvo.textContent = `Não há variação suficiente no período selecionado para calcular a taxa de crescimento do ${focoForma}.`;
    return;
  }
  const contraste = ranking.find((x) => x.forma !== foco.forma && x.cagr != null);
  alvo.innerHTML =
    `No período de ${fmtMesAno(dados.labels[i0])} a ${fmtMesAno(dados.labels[i1])}, o <strong>${foco.forma}</strong> `
    + `${foco.cagr >= 0 ? "cresceu" : "recuou"} a uma taxa média de ${fmtPct(Math.abs(foco.cagr), 1)} ao ano em ${rotuloMetrica(evoMetrica)}`
    + (contraste
      ? `, enquanto o <strong>${contraste.forma}</strong> ${contraste.cagr >= 0 ? "avançou" : "recuou"} `
        + `${fmtPct(Math.abs(contraste.cagr), 1)} ao ano no mesmo período.`
      : ".");
}

/** Lista, abaixo do gráfico, os eventos catalogados que tocam a forma em foco e caem dentro do período visível. */
function renderNarrativaEventos(i0, i1) {
  const labelsPeriodoRaw = dados.labels.slice(i0, i1 + 1);
  const relevantes = eventos
    .filter((e) => e.formas.includes(focoForma) && labelsPeriodoRaw.includes(e.data))
    .sort((a, b) => a.data.localeCompare(b.data));
  const alvo = document.getElementById("eventos-linha-tempo");
  const titulo = `<p class="eventos-titulo">O que pode explicar a trajetória do ${focoForma}</p>`;
  if (!relevantes.length) {
    alvo.innerHTML = titulo
      + `<p class="eventos-vazio">Nenhum evento catalogado nesta janela de tempo para o ${focoForma} — amplie o período para ver o contexto.</p>`;
    return;
  }
  alvo.innerHTML = titulo + relevantes.map((e) => `
    <div class="evento-item">
      <div class="evento-data">${fmtMesAno(e.data)}</div>
      <div class="evento-corpo">
        <h4>${e.titulo}</h4>
        <p>${e.descricao} <a href="${e.fonte}" target="_blank" rel="noopener">Fonte ↗</a></p>
      </div>
    </div>`).join("");
}

// ---------- Gráfico 1: participação por trimestre (colunas empilhadas) ----------
function renderGraficoParticipacao() {
  const [i0, i1] = periodoParaIndices(participPeriodo);
  const granularidade = escolherGranularidade(i1 - i0 + 1, maxColunasTela());
  const { periodos, share } = agregarParticipacaoPorPeriodo(i0, i1, participMetrica, granularidade);

  document.getElementById("desc-participacao").textContent =
    `Fatia de cada forma de pagamento no total de ${rotuloMetrica(participMetrica)} `
    + `por ${ROTULO_GRANULARIDADE[granularidade.codigo]} `
    + `(${periodos[0] || "—"} a ${periodos[periodos.length - 1] || "—"}).`;

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
  renderNarrativaMeio(periodos, share, granularidade);
}

function renderTabelaParticipacao(periodos, share) {
  const thead = document.querySelector("#tabela-participacao thead");
  const tbody = document.querySelector("#tabela-participacao tbody");
  thead.innerHTML = `<tr><th>Forma</th>${periodos.map((p) => `<th>${p}</th>`).join("")}</tr>`;
  tbody.innerHTML = dados.formas.map((f) => `
    <tr><td>${pilulaForma(f)}</td>${share[f].map((v) => `<td>${fmtPct(v)}</td>`).join("")}</tr>
  `).join("");
}

/** #rrggbb -> "rgba(r,g,b,alpha)", para esmaecer as formas que não estão em foco. */
function comAlpha(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/** Linhas verticais tracejadas nos meses em que há evento catalogado para a forma em foco. */
function construirAnotacoesEventos(labelsPeriodoRaw) {
  const anotacoes = {};
  eventos
    .filter((e) => e.formas.includes(focoForma) && labelsPeriodoRaw.includes(e.data))
    .forEach((e, idx) => {
      const posicao = labelsPeriodoRaw.indexOf(e.data);
      anotacoes[`evento${idx}`] = {
        type: "line", xMin: posicao, xMax: posicao,
        borderColor: "rgba(20,24,26,.4)", borderWidth: 1, borderDash: [4, 4],
        label: {
          display: true, content: e.titulo, position: "start", rotation: -90,
          backgroundColor: "rgba(20,24,26,.85)", color: "#fff",
          font: { size: 9, family: "IBM Plex Sans" }, padding: 4,
        },
      };
    });
  return anotacoes;
}

// ---------- Gráfico 2: linha do tempo ----------
function renderGraficoEvolucao() {
  const [i0, i1] = periodoParaIndices(evoPeriodo);
  const campo = evoMetrica === "ticket" ? "ticket" : evoMetrica;
  const labelsPeriodoRaw = dados.labels.slice(i0, i1 + 1);

  document.getElementById("desc-evolucao").textContent =
    `Série mensal de ${rotuloMetrica(evoMetrica)} por forma de pagamento, `
    + `de ${fmtMesAno(dados.labels[i0])} a ${fmtMesAno(dados.labels[i1])}. Em foco: ${focoForma}.`;

  const ctx = document.getElementById("gEvolucaoV2");
  // A forma em foco fica cheia e por cima; as demais ficam esmaecidas e ao fundo.
  const ordemDesenho = [...dados.formas.filter((f) => f !== focoForma), focoForma];
  const datasets = ordemDesenho.map((f) => {
    const emFoco = f === focoForma;
    return {
      label: f,
      data: dados.series[f][campo].slice(i0, i1 + 1),
      borderColor: emFoco ? CORES[f] : comAlpha(CORES[f], 0.25),
      backgroundColor: CORES[f],
      borderWidth: emFoco ? 3 : 1.5,
      pointRadius: 0,
      pointHoverRadius: 4,
      tension: 0.25,
      order: emFoco ? 0 : 1,
    };
  });

  if (graficoEvolucao) graficoEvolucao.destroy();
  graficoEvolucao = new Chart(ctx, {
    type: "line",
    data: { labels: labelsPeriodoRaw.map(fmtMesAno), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: cssVar("--texto"), usePointStyle: true, boxWidth: 8, font: { family: "IBM Plex Sans" } } },
        tooltip: { callbacks: { label: (i) => `${i.dataset.label}: ${fmtCampo(campo, i.parsed.y)}` } },
        datalabels: { display: false },
        annotation: { annotations: construirAnotacoesEventos(labelsPeriodoRaw) },
      },
      scales: {
        x: { ticks: { color: cssVar("--texto-suave"), maxTicksLimit: 12, autoSkip: true }, grid: { display: false } },
        y: { ticks: { color: cssVar("--texto-suave"), callback: (v) => fmtCampo(campo, v) }, grid: { color: cssVar("--borda") } },
      },
    },
  });

  renderTabelaEvolucao(i0, i1, campo);
  renderNarrativaFechamento(i0, i1);
  renderNarrativaEventos(i0, i1);
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

/** Pílulas de "contar a história de <forma>" — troca o foco de destaque/eventos da linha do tempo. */
function montarPilulasForma() {
  const cont = document.getElementById("foco-forma");
  cont.innerHTML = dados.formas.map((f) => `
    <button class="pilula-btn pilula-btn-forma ${f === focoForma ? "ativo" : ""}" data-forma="${f}">
      <span class="ponto-v2" style="background:${CORES[f]}"></span>${f}
    </button>
  `).join("");
  cont.querySelectorAll(".pilula-btn-forma").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.forma === focoForma) return;
      focoForma = btn.dataset.forma;
      cont.querySelectorAll(".pilula-btn-forma").forEach((b) => b.classList.toggle("ativo", b.dataset.forma === focoForma));
      renderGraficoEvolucao();
    });
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

  // Recalcula a granularidade do gráfico de participação ao cruzar o breakpoint mobile/desktop.
  let larguraAnterior = maxColunasTela();
  window.addEventListener("resize", () => {
    clearTimeout(window.__resizeParticipacaoTimer);
    window.__resizeParticipacaoTimer = setTimeout(() => {
      const atual = maxColunasTela();
      if (atual !== larguraAnterior) { larguraAnterior = atual; renderGraficoParticipacao(); }
    }, 200);
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

  try {
    const respEventos = await fetch(ARQUIVO_EVENTOS);
    eventos = respEventos.ok ? await respEventos.json() : [];
  } catch (erro) {
    eventos = [];
    console.warn("Eventos não carregados:", erro);
  }

  prepararSeriesTicket();
  renderCabecalho();
  renderNarrativaAbertura();
  ligarFiltros();
  montarPilulasForma();
  renderGraficoParticipacao();
  renderGraficoEvolucao();
}

iniciar();
