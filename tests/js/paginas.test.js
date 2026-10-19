// Testes das páginas sem navegador: node --test tests/js
// Carrega docs/js/*.js num contexto `vm` com um DOM falso e os JSON reais de docs/dados.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const DOCS = path.resolve(__dirname, "..", "..", "docs");
const lerJson = (rel) => JSON.parse(fs.readFileSync(path.join(DOCS, rel), "utf8"));
const lerTexto = (rel) => fs.readFileSync(path.join(DOCS, rel), "utf8");

// ---------- DOM falso ----------
function elemento() {
  const el = {
    hidden: false, innerHTML: "", textContent: "", value: "", dataset: {}, children: [], style: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    addEventListener() {}, setAttribute() {}, getAttribute: () => null,
    querySelector: () => elemento(), querySelectorAll: () => [],
    closest: () => null,
  };
  return el;
}
function idsOcultosNoHtml(pagina) {
  const ocultos = new Set();
  for (const tag of lerTexto(pagina).match(/<[^>]+>/g) || []) {
    const id = /\bid="([^"]+)"/.exec(tag);
    if (id && /\shidden(\s|>|=|\/)/.test(tag)) ocultos.add(id[1]);
  }
  return ocultos;
}
function documentoFalso(slug, ocultos = new Set()) {
  const porId = new Map();
  return {
    porId,
    body: { dataset: { slug } },
    documentElement: elemento(),
    getElementById(id) {
      if (!porId.has(id)) { const e = elemento(); e.hidden = ocultos.has(id); porId.set(id, e); }
      return porId.get(id);
    },
    querySelector: () => elemento(),
    querySelectorAll: () => [],
  };
}
const esperar = () => new Promise((r) => setTimeout(r, 20));

// ---------- app-v2.js (painel) ----------
function carregarPainel(largura = 1200) {
  let fonte = lerTexto("js/app-v2.js");
  const semInicio = fonte.replace(/\r?\niniciar\(\);\s*$/, "\n");
  assert.notEqual(semInicio, fonte, "app-v2.js deixou de terminar com iniciar(); ajuste o teste");
  const document = documentoFalso("");
  const ctx = vm.createContext({
    window: { innerWidth: largura, matchMedia: () => ({ matches: false, addEventListener() {} }) },
    document, Chart: { register() {} }, console, Intl, Date, Math, Number, String, Array, Object, JSON,
    getComputedStyle: () => ({ getPropertyValue: () => "#123456" }),
  });
  vm.runInContext(semInicio, ctx, { filename: "app-v2.js" });
  const publicado = lerJson("dados/meios_pagamento_mensal.json");
  ctx.__dados = publicado;
  ctx.__eventos = lerJson("dados/eventos_meios_pagamento.json");
  vm.runInContext("dados = __dados; eventos = __eventos; prepararSeriesTicket();", ctx);
  return { ctx, document, publicado, rodar: (codigo) => JSON.parse(JSON.stringify(vm.runInContext(codigo, ctx) ?? null)) };
}

test("formatação de valores, quantidades e meses", () => {
  const { rodar } = carregarPainel();
  assert.equal(rodar("fmtMesAno('2020-11')"), "nov/2020");
  assert.equal(rodar("fmtMesAno('2002-04')"), "abr/2002");
  assert.equal(rodar("fmtValor(null)"), "—");
  assert.match(rodar("fmtValor(3733392.32)"), /^R\$ 3,73 tri$/);
  assert.match(rodar("fmtValor(29333.21)"), /^R\$ 29,3 bi$/);
  assert.match(rodar("fmtValor(500)"), /^R\$ 500 mi$/);
  assert.match(rodar("fmtQtd(8110186.61)"), /^8,11 bi$/);
  assert.match(rodar("fmtQtd(6264.23)"), /^6,3 mi$/);
  assert.match(rodar("fmtQtd(12)"), /^12 mil$/);
  assert.equal(rodar("fmtPct(null)"), "—");
  assert.equal(rodar("fmtPct(95.04)"), "95,0%");
  assert.equal(rodar("fmtCompacto('quantidade', 43912345)"), "44 bi");
  assert.equal(rodar("fmtCompacto('quantidade', 4612345)"), "4,6 bi");
  assert.equal(rodar("fmtCompacto('quantidade', 850000)"), "850 mi");
  assert.equal(rodar("fmtCompacto('quantidade', 999600)"), "1,0 bi");
  assert.equal(rodar("fmtCompacto('quantidade', 12)"), "12 mil");
  assert.equal(rodar("fmtCompacto('valor', 3733392)"), "3,7 tri");
  assert.equal(rodar("fmtCompacto('valor', 29333)"), "29 bi");
  assert.equal(rodar("fmtCompacto('valor', 0)"), "");
  assert.equal(rodar("fmtTicket(null)"), "—");
  assert.match(rodar("fmtTicket(1234.5)"), /^R\$ 1\.234,50$/);
});

test("períodos 10A/5A/1A/tudo viram índices sobre as labels", () => {
  const { rodar, publicado } = carregarPainel();
  const ultimo = publicado.labels.length - 1;
  assert.deepEqual(rodar("periodoParaIndices('tudo')"), [0, ultimo]);
  assert.deepEqual(rodar("periodoParaIndices('10a')"), [ultimo - 119, ultimo]);
  assert.deepEqual(rodar("periodoParaIndices('5a')"), [ultimo - 59, ultimo]);
  assert.deepEqual(rodar("periodoParaIndices('1a')"), [ultimo - 11, ultimo]);
  const [ini, fim] = rodar("periodoParaIndices('ytd')");
  assert.equal(publicado.labels[ini].slice(0, 4), publicado.labels[fim].slice(0, 4));
});

test("granularidade do gráfico de participação respeita o limite de colunas", () => {
  const { rodar } = carregarPainel();
  assert.equal(rodar("escolherGranularidade(12, 25).codigo"), "mensal");
  assert.equal(rodar("escolherGranularidade(60, 25).codigo"), "trimestral");
  assert.equal(rodar("escolherGranularidade(120, 25).codigo"), "semestral");
  assert.equal(rodar("escolherGranularidade(293, 25).codigo"), "anual");
  const g = rodar("escolherGranularidade(293, 10)");           // tela pequena, série longa
  assert.equal(g.codigo, "multianual");
  assert.ok(Math.ceil(Math.ceil(293 / 12) / g.anosPorBloco) <= 10);
  for (const meses of [1, 7, 12, 36, 60, 120, 293, 400]) {
    for (const max of [10, 25]) {
      const o = rodar(`escolherGranularidade(${meses}, ${max})`);
      const passo = { mensal: 1, trimestral: 3, semestral: 6, anual: 12 }[o.codigo];
      const colunas = passo ? Math.ceil(meses / passo) : Math.ceil(Math.ceil(meses / 12) / o.anosPorBloco);
      assert.ok(colunas <= max, `${meses} meses / máx ${max} -> ${colunas} colunas (${o.codigo})`);
    }
  }
});

test("a participação agregada soma 100% em cada período, em todas as granularidades e métricas", () => {
  const { rodar, publicado } = carregarPainel();
  const ultimo = publicado.labels.length - 1;
  for (const gran of ["{codigo:'mensal'}", "{codigo:'trimestral'}", "{codigo:'semestral'}", "{codigo:'anual'}",
                      "{codigo:'multianual',anosPorBloco:5}"]) {
    for (const campo of ["quantidade", "valor"]) {
      const r = rodar(`agregarParticipacaoPorPeriodo(${ultimo - 59}, ${ultimo}, '${campo}', ${gran})`);
      assert.ok(r.periodos.length >= 1);
      r.periodos.forEach((_, i) => {
        const soma = publicado.formas.reduce((s, f) => s + (r.share[f][i] ?? 0), 0);
        assert.ok(Math.abs(soma - 100) < 1e-6, `${gran} ${campo} período ${i}: ${soma}`);
      });
    }
  }
  const trimestral = rodar(`agregarParticipacaoPorPeriodo(${ultimo - 59}, ${ultimo}, 'valor', {codigo:'trimestral'})`);
  assert.ok([20, 21].includes(trimestral.periodos.length), `${trimestral.periodos.length} trimestres`);   // 60 meses = 20 ou 21 trimestres
});

test("o total agregado (modo Total) soma a série mensal e é coerente com a fatia", () => {
  const { rodar, publicado } = carregarPainel();
  const ultimo = publicado.labels.length - 1;
  const i0 = ultimo - 59;
  for (const gran of ["{codigo:'mensal'}", "{codigo:'trimestral'}", "{codigo:'anual'}", "{codigo:'multianual',anosPorBloco:5}"]) {
    for (const campo of ["quantidade", "valor"]) {
      const r = rodar(`agregarParticipacaoPorPeriodo(${i0}, ${ultimo}, '${campo}', ${gran})`);
      publicado.formas.forEach((f) => {
        const somaAgregada = r.total[f].reduce((s, v) => s + v, 0);
        const somaMensal = publicado.series[f][campo].slice(i0, ultimo + 1).reduce((s, v) => s + (v ?? 0), 0);
        assert.ok(Math.abs(somaAgregada - somaMensal) < 1e-6 * Math.max(1, somaMensal), `${gran} ${campo} ${f}`);
      });
      assert.equal(r.incompleto.length, r.periodos.length);
      if (gran === "{codigo:'mensal'}") assert.ok(r.incompleto.every((x) => !x), "mês nunca é incompleto");
      r.periodos.forEach((_, i) => {
        const totPeriodo = publicado.formas.reduce((s, f) => s + r.total[f][i], 0);
        publicado.formas.forEach((f) => {
          if (!totPeriodo) return;
          assert.ok(Math.abs(r.share[f][i] - (r.total[f][i] / totPeriodo) * 100) < 1e-9, `${gran} ${campo} ${f} período ${i}`);
        });
      });
    }
  }
});

test("CAGR do JS bate com o cagr_valor_aa_pct publicado pelo Python", () => {
  const { rodar, publicado } = carregarPainel();
  const ultimo = publicado.labels.length - 1;
  for (const p of publicado.kpis.por_forma) {
    const js = rodar(`cagrAA(dados.series['${p.forma}'].valor, 0, ${ultimo})`);
    if (p.cagr_valor_aa_pct == null) assert.equal(js, null, p.forma);
    else assert.ok(Math.abs(js - p.cagr_valor_aa_pct) < 1e-6, `${p.forma}: js ${js} vs py ${p.cagr_valor_aa_pct}`);
  }
  assert.equal(rodar("cagrAA([0, 0, 5, null], 0, 3)"), null);   // um único valor positivo
});

test("ticket médio do JS bate com o ticket publicado pelo Python", () => {
  const { rodar, publicado } = carregarPainel();
  const ultimo = publicado.labels.length - 1;
  for (const p of publicado.kpis.por_forma) {
    const js = rodar(`dados.series['${p.forma}'].ticket[${ultimo}]`);
    if (p.ticket_medio_ultimo_rs == null) assert.equal(js, null, p.forma);
    else assert.ok(Math.abs(js - p.ticket_medio_ultimo_rs) < 1e-6, p.forma);
  }
});

test("frase de abertura cita a forma líder do último mês", () => {
  const { rodar, document, publicado } = carregarPainel();
  rodar("renderNarrativaAbertura()");
  const html = document.getElementById("txt-abertura").innerHTML;
  const lider = rodar("liderPorQuantidade()");
  assert.equal(lider.forma, "Pix");
  assert.ok(lider.part_qtd_pct > 50 && lider.part_qtd_pct <= 100);
  assert.match(html, /<strong>Pix<\/strong>/);
  assert.ok(html.includes(`Desde ${publicado.meta.periodo.inicio.slice(0, 4)}`));
});

test("rodapé e eventos da linha do tempo renderizam com os dados publicados", () => {
  const { rodar, document, publicado } = carregarPainel();
  rodar("renderCabecalho()");
  assert.ok(document.getElementById("rodape-fonte-v2").textContent.includes(publicado.meta.fonte));
  const todos = JSON.stringify(publicado.labels);
  rodar(`focoForma = 'Pix'; renderNarrativaEventos(${todos})`);
  const html = document.getElementById("eventos-linha-tempo").innerHTML;
  assert.match(html, /class="evento-item"/);
  assert.match(html, /Fonte ↗/);
  rodar("focoForma = 'Pix'; renderNarrativaEventos([])");
  assert.match(document.getElementById("eventos-linha-tempo").innerHTML, /Nenhum evento catalogado/);
});

test("narrativa de fechamento calcula a taxa de crescimento do foco", () => {
  const { rodar, document, publicado } = carregarPainel();
  const ultimo = publicado.labels.length - 1;
  rodar(`focoForma = 'Pix'; evoMetrica = 'valor'; renderNarrativaFechamento(${ultimo - 59}, ${ultimo})`);
  assert.match(document.getElementById("txt-fechamento").innerHTML, /<strong>Pix<\/strong> (cresceu|recuou)/);
});

// ---------- explorar.js (exploração) ----------
async function rodarExploracao({ semPerfil = false, semNotas = false } = {}) {
  const document = documentoFalso("meios_pagamento_mensal", idsOcultosNoHtml("explorar.html"));
  const pedidos = [];
  const fetch = async (url) => {
    pedidos.push(url);
    const ausente = (semPerfil && url.includes("perfil_")) || (semNotas && url.includes("notas_"));
    if (ausente || !fs.existsSync(path.join(DOCS, url))) return { ok: false, status: 404, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => lerJson(url) };
  };
  const ctx = vm.createContext({ document, fetch, console, Intl, Number, String, Object, Array, JSON, Set });
  vm.runInContext(lerTexto("js/explorar.js"), ctx, { filename: "explorar.js" });
  for (let i = 0; i < 5; i++) await esperar();
  return { document, pedidos, el: (id) => document.getElementById(id) };
}

test("exploração renderiza perfil e notas reais", async () => {
  const { el, pedidos } = await rodarExploracao();
  const perfil = lerJson("dados/perfil_meios_pagamento_mensal.json");
  const notas = lerJson("dados/notas_meios_pagamento_mensal.json");
  assert.deepEqual(pedidos, [
    "dados/perfil_meios_pagamento_mensal.json", "dados/notas_meios_pagamento_mensal.json"]);
  assert.match(el("resumo").innerHTML, /Tabelas perfiladas/);
  assert.match(el("resumo").innerHTML, new RegExp(`${perfil.cobertura_temporal.inicio} → ${perfil.cobertura_temporal.fim}`));
  assert.equal(el("erro").hidden, true, "o aviso de erro não deve aparecer quando o perfil carrega");
  for (const sec of ["sec-mapa", "sec-cobertura", "sec-armadilhas", "sec-comparativos", "sec-contexto",
                     "sec-cruzamentos", "sec-pauta", "sec-perguntas"]) {
    assert.equal(el(sec).hidden, false, `${sec} deveria ter sido exibida`);
  }
  assert.equal((el("tabelas").innerHTML.match(/<details class="bloco-tabela"/g) || []).length, perfil.tabelas.length);
  assert.equal((el("armadilhas").innerHTML.match(/class="mini-cartao"/g) || []).length, notas.armadilhas.length);
  assert.equal((el("pauta-justificativas").innerHTML.match(/<details class="bloco-tabela"/g) || []).length, notas.pauta.length);
  assert.equal((el("perguntas").innerHTML.match(/<li>/g) || []).length, notas.perguntas_abertas.length);
  assert.match(el("meta-info").textContent, /perfil gerado em/);
  assert.match(el("rodape-perfil").textContent, /perfil_meios_pagamento_mensal\.json/);
});

test("exploração sem perfil mostra o aviso de erro", async () => {
  const { el } = await rodarExploracao({ semPerfil: true });
  assert.equal(el("erro").hidden, false);
  assert.match(el("erro").innerHTML, /Perfil não encontrado/);
  assert.match(el("meta-info").textContent, /Falha ao carregar/);
});

test("exploração sem notas funciona só com a metade medida", async () => {
  const { el } = await rodarExploracao({ semNotas: true });
  assert.match(el("resumo").innerHTML, /sem notas curadas/);
  assert.equal(el("sec-mapa").hidden, false);
  assert.equal(el("sec-pauta").hidden, true, "sem notas, a pauta continua oculta");
  assert.equal(el("sec-armadilhas").hidden, true);
});
