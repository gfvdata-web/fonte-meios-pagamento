"""Contrato entre os arquivos publicados em docs/dados/ e os campos que o JS das páginas lê.

Os campos esperados foram extraídos de docs/js/app-v2.js (painel) e docs/js/explorar.js
(exploração). Cada teste de campo confere também que o JS ainda menciona o campo: se o JS
passar a ler outra coisa, o teste avisa que o contrato mudou.
"""
from __future__ import annotations

import csv
import re
import unittest
from datetime import datetime

from src import config

from tests import helpers
from tests.helpers import DADOS_PUB, DOCS, SLUG, ler_json

JS_PAINEL = (DOCS / "js" / "app-v2.js").read_text(encoding="utf-8")
JS_EXPLORAR = (DOCS / "js" / "explorar.js").read_text(encoding="utf-8")
RE_ANO_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
FORMAS = list(config.fonte()["formas"])


def _meses_seguidos(a: str, b: str) -> bool:
    (ya, ma), (yb, mb) = map(int, a.split("-")), map(int, b.split("-"))
    return (ya * 12 + ma) + 1 == (yb * 12 + mb)


class TestSerieDoPainel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = ler_json(DADOS_PUB / f"{SLUG}.json")

    def test_o_js_le_estes_campos(self):
        for trecho in ("dados.meta", "meta.fonte", "meta.gerado_em", "meta.periodo.inicio",
                       "dados.kpis.totais.mes_ref", "dados.labels", "dados.formas", "dados.series"):
            self.assertIn(trecho, JS_PAINEL, f"o app-v2.js deixou de ler {trecho}; revise o contrato")

    def test_meta(self):
        meta = self.d["meta"]
        for campo in ("fonte", "descricao", "url", "unidades", "periodicidade", "licenca", "gerado_em", "periodo"):
            self.assertIn(campo, meta)
        datetime.fromisoformat(meta["gerado_em"])      # o JS faz new Date(gerado_em)
        self.assertEqual(set(meta["unidades"]), {"quantidade", "valor"})
        self.assertEqual(meta["url"], config.fonte()["url"])

    def test_labels_mensais_sem_buraco(self):
        labels = self.d["labels"]
        self.assertGreater(len(labels), 12)             # o painel usa janelas de 1/5/10 anos
        for l in labels:
            self.assertRegex(l, RE_ANO_MES)
        for a, b in zip(labels, labels[1:]):
            self.assertTrue(_meses_seguidos(a, b), f"buraco/ordem entre {a} e {b}")
        self.assertEqual(self.d["meta"]["periodo"], {"inicio": labels[0], "fim": labels[-1]})
        self.assertEqual(self.d["kpis"]["totais"]["mes_ref"], labels[-1])
        self.assertEqual(self.d["kpis"]["totais"]["meses_cobertos"], len(labels))

    def test_formas_e_series_alinhadas(self):
        self.assertEqual(self.d["formas"], FORMAS)
        n = len(self.d["labels"])
        self.assertEqual(set(self.d["series"]), set(FORMAS))
        for forma, s in self.d["series"].items():
            for campo in ("quantidade", "valor"):
                self.assertEqual(len(s[campo]), n, f"{forma}.{campo}")
                for v in s[campo]:
                    self.assertTrue(v is None or (isinstance(v, (int, float)) and v >= 0), (forma, campo, v))

    def test_o_ultimo_mes_tem_movimento_nas_formas_ativas(self):
        # A frase de abertura do painel divide pelo total do último mês.
        ult = {f: self.d["series"][f]["quantidade"][-1] for f in FORMAS}
        self.assertGreater(sum(v or 0 for v in ult.values()), 0)
        self.assertGreater(ult["Pix"], 0)

    def test_kpis_por_forma(self):
        campos = {"forma", "valor_total", "qtd_total", "part_valor_pct", "part_qtd_pct", "valor_ultimo",
                  "qtd_ultimo", "ticket_medio_ultimo_rs", "yoy_valor_pct", "cagr_valor_aa_pct"}
        por_forma = self.d["kpis"]["por_forma"]
        self.assertEqual({p["forma"] for p in por_forma}, set(FORMAS))
        for p in por_forma:
            self.assertEqual(set(p), campos)

    def test_estatisticas_por_forma(self):
        self.assertEqual(set(self.d["estatisticas"]), set(FORMAS))
        for forma in FORMAS:
            for campo in ("valor", "quantidade"):
                self.assertEqual(
                    set(self.d["estatisticas"][forma][campo]),
                    {"media", "mediana", "desvio_padrao", "coef_variacao_pct", "minimo", "maximo"})

    def test_formas_do_js_tem_cor_no_css(self):
        mapa = dict(re.findall(r'(\w+):\s*"(--c-\w+)"', JS_PAINEL.split("const FORMA_VAR")[1].split("};")[0]))
        self.assertEqual(set(mapa), set(FORMAS), "FORMA_VAR do JS diverge das formas publicadas")
        css = (DOCS / "css" / "estilo-v2.css").read_text(encoding="utf-8")
        for forma, var in mapa.items():
            self.assertIn(f"{var}:", css, f"variável {var} ({forma}) não definida no estilo-v2.css")


class TestCsvPublico(unittest.TestCase):
    def test_colunas_tipos_e_chave(self):
        with (DADOS_PUB / f"{SLUG}.csv").open(encoding="utf-8", newline="") as f:
            leitor = csv.DictReader(f)
            self.assertEqual(leitor.fieldnames, ["ano_mes", "forma_pagamento", "quantidade", "valor"])
            linhas = list(leitor)
        chaves = [(l["ano_mes"], l["forma_pagamento"]) for l in linhas]
        self.assertEqual(len(chaves), len(set(chaves)), "chave ano_mes+forma duplicada")
        self.assertEqual({l["forma_pagamento"] for l in linhas}, set(FORMAS))
        for l in linhas:
            self.assertRegex(l["ano_mes"], RE_ANO_MES)
            float(l["quantidade"]), float(l["valor"])
        self.assertEqual(len(linhas), len(ler_json(DADOS_PUB / f"{SLUG}.json")["labels"]) * len(FORMAS))

    def test_json_e_csv_dizem_a_mesma_coisa(self):
        d = ler_json(DADOS_PUB / f"{SLUG}.json")
        with (DADOS_PUB / f"{SLUG}.csv").open(encoding="utf-8", newline="") as f:
            tidy = {(l["ano_mes"], l["forma_pagamento"]): l for l in csv.DictReader(f)}
        for forma in FORMAS:
            for i, mes in enumerate(d["labels"]):
                lin = tidy[(mes, forma)]
                self.assertAlmostEqual(float(lin["quantidade"]), d["series"][forma]["quantidade"][i], places=6)
                self.assertAlmostEqual(float(lin["valor"]), d["series"][forma]["valor"][i], places=6)


class TestEventos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eventos = ler_json(DADOS_PUB / "eventos_meios_pagamento.json")

    def test_o_js_le_estes_campos(self):
        for trecho in ("e.formas", "e.data", "e.titulo", "e.descricao", "e.fonte"):
            self.assertIn(trecho, JS_PAINEL)

    def test_campos_e_tipos(self):
        self.assertGreater(len(self.eventos), 5)
        for e in self.eventos:
            self.assertEqual(set(e), {"data", "titulo", "descricao", "formas", "fonte"}, e.get("titulo"))
            self.assertRegex(e["data"], RE_ANO_MES)
            self.assertTrue(e["titulo"].strip() and e["descricao"].strip())
            self.assertTrue(e["formas"], e["titulo"])
            self.assertLessEqual(set(e["formas"]), set(FORMAS), e["titulo"])
            self.assertRegex(e["fonte"], r"^https?://\S+$", e["titulo"])

    def test_sem_evento_duplicado(self):
        chaves = [(e["data"], e["titulo"]) for e in self.eventos]
        self.assertEqual(len(chaves), len(set(chaves)))

    def test_cada_forma_com_evento_na_janela_da_serie(self):
        # O painel mostra "Nenhum evento catalogado" quando não há; ao menos o Pix deve ter.
        labels = set(ler_json(DADOS_PUB / f"{SLUG}.json")["labels"])
        pix = [e for e in self.eventos if "Pix" in e["formas"] and e["data"] in labels]
        self.assertTrue(pix, "nenhum evento do Pix cai dentro da série")


class TestPerfilLidoPelaExploracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = ler_json(DADOS_PUB / f"perfil_{SLUG}.json")

    def test_o_js_le_estes_campos(self):
        for trecho in ("perfil.tabelas", "perfil.relacionamentos", "perfil.cobertura_temporal",
                       "perfil.meta.fonte", "perfil.meta.gerado_em", "t.chave_primaria_valida",
                       "t.amostra", "c.pct_nulos", "r.cobertura_pct", "r.orfaos"):
            self.assertIn(trecho, JS_EXPLORAR)

    def test_meta(self):
        self.assertEqual(self.p["meta"]["slug"], SLUG)
        self.assertTrue(self.p["meta"]["fonte"])
        datetime.fromisoformat(self.p["meta"]["gerado_em"])

    def test_tabelas(self):
        tabelas = self.p["tabelas"]
        self.assertEqual([t["camada"] for t in tabelas].count("tidy"), 1)   # o resumo procura a camada tidy
        campos = {"id", "camada", "nome", "arquivo", "formato", "origem", "n_linhas", "n_colunas",
                  "granularidade", "chave_primaria", "chave_primaria_valida", "duplicatas",
                  "colunas", "amostra", "alertas"}
        for t in tabelas:
            self.assertEqual(set(t), campos, t["id"])
            self.assertEqual(len(t["colunas"]), t["n_colunas"], t["id"])
            a = t["amostra"]
            self.assertEqual(set(a), {"cabecalho", "inicio", "fim", "omitidas"})
            self.assertEqual(a["cabecalho"], [c["nome"] for c in t["colunas"]])
            for linha in a["inicio"] + a["fim"]:
                self.assertEqual(len(linha), len(a["cabecalho"]))
            for c in t["colunas"]:
                for campo in ("nome", "papel", "tipo", "unidade", "pct_nulos", "distintos"):
                    self.assertIn(campo, c, f"{t['id']}.{c['nome']}")

    def test_papeis_tem_estilo_de_selo(self):
        # O JS monta class="selo selo-<papel>"; sem a regra no CSS o selo fica sem cor.
        css = (DOCS / "css" / "estilo.css").read_text(encoding="utf-8")
        usados = {c["papel"] for t in self.p["tabelas"] for c in t["colunas"]}
        for papel in usados:
            self.assertIn(f".selo-{papel}", css, f"falta .selo-{papel} em estilo.css")

    def test_relacionamentos_e_cobertura(self):
        ids = {t["id"] for t in self.p["tabelas"]}
        for r in self.p["relacionamentos"]:
            self.assertEqual(set(r), {"de", "para", "tabela_de", "tabela_para", "cardinalidade",
                                      "cobertura_pct", "orfaos", "uso"})
            self.assertLessEqual({r["tabela_de"], r["tabela_para"]}, ids)
        cob = self.p["cobertura_temporal"]
        self.assertEqual(set(cob), {"inicio", "fim", "meses_esperados", "meses_presentes", "lacunas"})
        self.assertIsInstance(cob["lacunas"], list)
        labels = ler_json(DADOS_PUB / f"{SLUG}.json")["labels"]
        self.assertEqual((cob["inicio"], cob["fim"]), (labels[0], labels[-1]),
                         "perfil e série publicada cobrem períodos diferentes")

    def test_perfil_cabe_no_teto_da_etapa_e(self):
        self.assertLess((DADOS_PUB / f"perfil_{SLUG}.json").stat().st_size / 1024, 300)


class TestNotasLidasPelaExploracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = ler_json(DADOS_PUB / f"notas_{SLUG}.json")
        cls.p = ler_json(DADOS_PUB / f"perfil_{SLUG}.json")
        cls.css = (DOCS / "css" / "estilo.css").read_text(encoding="utf-8")

    def test_secoes_e_campos(self):
        n = self.n
        self.assertTrue(n["meta"]["atualizado_em"])
        for sec, campos in {
            "leitura": {"tabela_id", "texto"},
            "armadilhas": {"titulo", "texto", "impacto"},
            "comparativos": {"id", "titulo", "pergunta", "colunas", "o_que_esperar"},
            "contexto_externo": {"titulo", "resumo", "fonte", "url", "consultado_em", "por_que_importa"},
            "cruzamentos": {"com_fonte", "chave", "pergunta", "cuidado"},
            "pauta": {"id", "titulo", "pergunta", "tabela", "colunas", "tipo_grafico", "por_que_esse_tipo",
                      "status", "prioridade", "esforco"},
        }.items():
            self.assertTrue(n[sec], f"seção {sec} vazia")
            for item in n[sec]:
                self.assertLessEqual(campos, set(item), f"{sec}: {item.get('titulo') or item.get('id')}")
        self.assertTrue(all(isinstance(p, str) and p for p in n["perguntas_abertas"]))

    def test_leitura_aponta_para_tabelas_do_perfil(self):
        ids = {t["id"] for t in self.p["tabelas"]}
        self.assertLessEqual({l["tabela_id"] for l in self.n["leitura"]}, ids)

    def test_colunas_citadas_existem_na_tabela(self):
        cols = {t["id"]: {c["nome"] for c in t["colunas"]} for t in self.p["tabelas"]}
        for item in self.n["pauta"]:
            self.assertIn(item["tabela"], cols, item["id"])
            self.assertLessEqual(set(item["colunas"]), cols[item["tabela"]], item["id"])
        todas = set().union(*cols.values())
        for item in self.n["comparativos"]:
            self.assertLessEqual(set(item["colunas"]), todas, item["id"])

    def test_vocabulario_que_o_js_ordena_e_filtra(self):
        for a in self.n["armadilhas"]:
            self.assertIn(a["impacto"], {"alto", "medio", "baixo"})   # ordem = {alto, medio, baixo}
        html = (DOCS / "explorar.html").read_text(encoding="utf-8")
        filtros = set(re.findall(r'class="alt-btn[^"]*" data-status="(\w+)"', html))
        ids = [p["id"] for p in self.n["pauta"]]
        self.assertEqual(len(ids), len(set(ids)), "ids de pauta repetidos")
        for p in self.n["pauta"]:
            self.assertIn(p["status"], filtros, f"{p['id']}: status sem botão de filtro")
            self.assertIn(f".selo-{p['esforco']}", self.css, f"{p['id']}: esforço sem estilo de selo")
            self.assertIn(f".selo-{p['status']}", self.css, f"{p['id']}: status sem estilo de selo")
            self.assertIn(f".selo-{p['prioridade']}", self.css, f"{p['id']}: prioridade sem estilo de selo")

    def test_urls_externas_bem_formadas(self):
        for c in self.n["contexto_externo"]:
            self.assertRegex(c["url"], r"^https?://\S+$", c["titulo"])
            self.assertRegex(c["consultado_em"], r"^\d{4}-\d{2}-\d{2}$", c["titulo"])

    def test_cruzamentos_viram_url_de_outra_fonte(self):
        # explorar.js: DOMINIOS[slug] ou https://gfvdata-web.github.io/fonte-<slug com hífen, sem -mensal>/
        for c in self.n["cruzamentos"]:
            self.assertRegex(c["com_fonte"], r"^[a-z0-9_]+$")


if __name__ == "__main__":
    unittest.main()
