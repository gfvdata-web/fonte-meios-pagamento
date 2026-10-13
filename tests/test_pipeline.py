"""Pipeline Etapas 2 -> E -> 5 contra a fixture da API (rede trocada por mock)."""
from __future__ import annotations

import csv
import json
import unittest
import zipfile
from unittest import mock

import pandas as pd

from src import config
from src.analise import meios_pagamento as analise
from src.coleta import meios_pagamento as coleta
from src.perfil import meios_pagamento as perfil
from src.publicacao import meios_pagamento as publicacao
from src.publicacao import skill
from src.tratamento import meios_pagamento as tratamento

from tests import helpers
from tests.helpers import SLUG, ambiente_isolado, api_falsa, sem_saida

FORMAS = list(config.FONTES[SLUG]["formas"])


def _coletar_e_tratar():
    with sem_saida(), api_falsa():
        coleta.coletar()
    with sem_saida():
        return tratamento.tratar()


class TestColeta(unittest.TestCase):
    def test_grava_envelope_com_registros_da_api(self):
        with ambiente_isolado(), api_falsa() as falso, sem_saida():
            registros = coleta.coletar()
            falso.assert_called_once()
            self.assertEqual(falso.call_args.args[0], config.fonte()["url"])
            envelope = helpers.ler_json(config.DIR_BRUTOS / f"{SLUG}.json")
        self.assertEqual(len(registros), len(helpers.resposta_api()["value"]))
        self.assertEqual(envelope["total_registros"], len(registros))
        self.assertEqual(envelope["registros"], registros)
        self.assertEqual(envelope["fonte"], config.fonte()["nome"])
        self.assertTrue(envelope["coletado_em"])

    def test_erro_http_nao_sobrescreve_o_bruto_existente(self):
        with ambiente_isolado(), sem_saida():
            with api_falsa():
                coleta.coletar()
            antes = (config.DIR_BRUTOS / f"{SLUG}.json").read_text(encoding="utf-8")
            with api_falsa(corpo={}, status=503):
                with self.assertRaises(Exception):
                    coleta.coletar()
            depois = (config.DIR_BRUTOS / f"{SLUG}.json").read_text(encoding="utf-8")
        self.assertEqual(antes, depois)

    def test_resposta_sem_value_vira_lista_vazia(self):
        with ambiente_isolado(), api_falsa(corpo={"outra": 1}), sem_saida():
            self.assertEqual(coleta.coletar(), [])

    def test_slug_desconhecido_da_erro_claro(self):
        with self.assertRaises(KeyError):
            config.fonte("nao_existe")


class TestTratamento(unittest.TestCase):
    def test_wide_vira_tidy_com_seis_formas_por_mes(self):
        with ambiente_isolado():
            tidy = _coletar_e_tratar()
            meses = len(helpers.resposta_api()["value"])
            self.assertEqual(len(tidy), meses * len(FORMAS))
            self.assertEqual(list(tidy.columns), ["ano_mes", "forma_pagamento", "quantidade", "valor"])
            self.assertEqual(sorted(tidy["forma_pagamento"].unique()), sorted(FORMAS))
            csv_gravado = pd.read_csv(config.DIR_PROCESSADOS / f"{SLUG}.csv", dtype={"ano_mes": str})
        self.assertEqual(len(csv_gravado), len(tidy))

    def test_ano_mes_normalizado_e_ordenado(self):
        with ambiente_isolado():
            tidy = _coletar_e_tratar()
        self.assertTrue(tidy["ano_mes"].str.fullmatch(r"\d{4}-\d{2}").all())
        self.assertEqual(tidy["ano_mes"].iloc[0], "2020-01")
        self.assertEqual(tidy["ano_mes"].iloc[-1], "2024-04")
        ordem = list(zip(tidy["ano_mes"], tidy["forma_pagamento"]))
        self.assertEqual(ordem, sorted(ordem))

    def test_valores_preservados_sem_conversao_de_unidade(self):
        reg = next(r for r in helpers.resposta_api()["value"] if r["AnoMes"] == "202112")
        with ambiente_isolado():
            tidy = _coletar_e_tratar()
        linha = tidy[(tidy.ano_mes == "2021-12") & (tidy.forma_pagamento == "Pix")].iloc[0]
        self.assertAlmostEqual(linha["quantidade"], reg["quantidadePix"])
        self.assertAlmostEqual(linha["valor"], reg["valorPix"])

    def test_zeros_de_forma_inexistente_sao_mantidos(self):
        # Pix antes de nov/2020 e DOC/TEC depois de fev/2024 vêm como 0, não como vazio.
        with ambiente_isolado():
            tidy = _coletar_e_tratar()
        pix_antes = tidy[(tidy.forma_pagamento == "Pix") & (tidy.ano_mes < "2020-11")]
        self.assertGreater(len(pix_antes), 0)
        self.assertTrue((pix_antes["quantidade"] == 0).all())
        doc_depois = tidy[(tidy.forma_pagamento == "DOC") & (tidy.ano_mes > "2024-02")]
        self.assertTrue((doc_depois["quantidade"] == 0).all())

    def test_forma_sem_colunas_no_bruto_e_ignorada(self):
        corpo = helpers.resposta_api()
        for reg in corpo["value"]:
            reg.pop("quantidadeDOC"), reg.pop("valorDOC")
        with ambiente_isolado(), sem_saida():
            with api_falsa(corpo=corpo):
                coleta.coletar()
            tidy = tratamento.tratar()
        self.assertNotIn("DOC", set(tidy["forma_pagamento"]))
        self.assertEqual(len(set(tidy["forma_pagamento"])), len(FORMAS) - 1)

    def test_numero_como_texto_e_nulo_viram_numerico_ou_nan(self):
        corpo = helpers.resposta_api()
        corpo["value"][0]["quantidadePix"] = "123.5"
        corpo["value"][0]["valorPix"] = None
        mes = corpo["value"][0]["AnoMes"]
        mes_fmt = f"{mes[:4]}-{mes[4:]}"
        with ambiente_isolado(), sem_saida():
            with api_falsa(corpo=corpo):
                coleta.coletar()
            tidy = tratamento.tratar()
        linha = tidy[(tidy.ano_mes == mes_fmt) & (tidy.forma_pagamento == "Pix")].iloc[0]
        self.assertEqual(linha["quantidade"], 123.5)
        self.assertTrue(pd.isna(linha["valor"]))

    def test_sem_bruto_pede_para_rodar_a_coleta(self):
        with ambiente_isolado():
            with self.assertRaises(FileNotFoundError) as ctx:
                tratamento.tratar()
        self.assertIn("coleta", str(ctx.exception))


class TestAnalise(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ambiente_isolado():
            cls.tidy = _coletar_e_tratar()
            cls.res = analise.analisar()

    def test_labels_ordenadas_e_series_alinhadas(self):
        labels = self.res["labels"]
        self.assertEqual(labels, sorted(labels))
        self.assertEqual(len(labels), 52)
        self.assertEqual(self.res["formas"], FORMAS)
        for forma in FORMAS:
            for campo in ("quantidade", "valor"):
                self.assertEqual(len(self.res["series"][forma][campo]), len(labels))

    def test_totais_do_ultimo_mes(self):
        ult = self.tidy[self.tidy.ano_mes == "2024-04"]
        t = self.res["kpis"]["totais"]
        self.assertEqual(t["mes_ref"], "2024-04")
        self.assertEqual(t["meses_cobertos"], 52)
        self.assertAlmostEqual(t["valor_ultimo_mes"], ult["valor"].sum())
        self.assertAlmostEqual(t["qtd_ultimo_mes"], ult["quantidade"].sum())

    def test_ranking_por_valor_total_decrescente(self):
        por_forma = self.res["kpis"]["por_forma"]
        totais = [p["valor_total"] for p in por_forma]
        self.assertEqual(totais, sorted(totais, reverse=True))
        self.assertAlmostEqual(sum(p["part_valor_pct"] for p in por_forma), 100.0)
        self.assertAlmostEqual(sum(p["part_qtd_pct"] for p in por_forma), 100.0)

    def test_ticket_medio_em_reais(self):
        # valor em R$ milhões / quantidade em milhares  =>  x1000 = R$ por transação.
        pix = next(p for p in self.res["kpis"]["por_forma"] if p["forma"] == "Pix")
        self.assertAlmostEqual(pix["ticket_medio_ultimo_rs"], pix["valor_ultimo"] * 1000 / pix["qtd_ultimo"])
        doc = next(p for p in self.res["kpis"]["por_forma"] if p["forma"] == "DOC")
        self.assertEqual(doc["qtd_ultimo"], 0)
        self.assertIsNone(doc["ticket_medio_ultimo_rs"])

    def test_yoy_contra_mesmo_mes_do_ano_anterior(self):
        pix = next(p for p in self.res["kpis"]["por_forma"] if p["forma"] == "Pix")
        s = self.res["series"]["Pix"]["valor"]
        self.assertAlmostEqual(pix["yoy_valor_pct"], (s[-1] / s[-13] - 1) * 100)

    def test_estatistica_descritiva_por_forma(self):
        for forma in FORMAS:
            for campo in ("valor", "quantidade"):
                d = self.res["estatisticas"][forma][campo]
                self.assertLessEqual(d["minimo"], d["mediana"])
                self.assertLessEqual(d["mediana"], d["maximo"])

    def test_resultado_serializa_em_json(self):
        json.dumps(self.res, allow_nan=False)

    def test_funcoes_puras(self):
        self.assertAlmostEqual(analise._cagr_aa(pd.Series([100.0] + [0.0] * 11 + [200.0])), 1.0)
        self.assertIsNone(analise._cagr_aa(pd.Series([0.0, 0.0, 5.0])))   # só um positivo
        self.assertIsNone(analise._cagr_aa(pd.Series([0.0, 0.0])))
        self.assertIsNone(analise._yoy_pct(pd.Series(range(1, 13))))       # menos de 13 meses
        self.assertIsNone(analise._yoy_pct(pd.Series([0.0] + [1.0] * 12)))  # base zero
        self.assertAlmostEqual(analise._yoy_pct(pd.Series([100.0] + [0.0] * 11 + [150.0])), 50.0)
        vazio = analise._desc(pd.Series([], dtype=float))
        self.assertIsNone(vazio["media"])
        um = analise._desc(pd.Series([3.0]))
        self.assertEqual((um["media"], um["desvio_padrao"]), (3.0, None))

    def test_sem_processado_pede_o_tratamento(self):
        with ambiente_isolado():
            with self.assertRaises(FileNotFoundError):
                analise.analisar()


class TestPublicacao(unittest.TestCase):
    def test_pacote_json_e_csv_publicos(self):
        with ambiente_isolado():
            _coletar_e_tratar()
            with sem_saida():
                pacote = publicacao.publicar()
            json_pub = helpers.ler_json(config.DIR_PUBLICADOS / f"{SLUG}.json")
            csv_pub = config.DIR_PUBLICADOS / f"{SLUG}.csv"
            igual = csv_pub.read_bytes() == (config.DIR_PROCESSADOS / f"{SLUG}.csv").read_bytes()
        self.assertTrue(igual, "o CSV público deve ser cópia do tidy")
        self.assertEqual(json_pub["labels"], pacote["labels"])
        meta = json_pub["meta"]
        self.assertEqual(meta["periodo"], {"inicio": "2020-01", "fim": "2024-04"})
        self.assertEqual(meta["unidades"], config.fonte()["unidades"])
        self.assertEqual(meta["url"], config.fonte()["url"])
        self.assertIn("kpis", json_pub)
        self.assertIn("estatisticas", json_pub)


class TestPerfil(unittest.TestCase):
    def test_perfil_das_tres_camadas(self):
        with ambiente_isolado():
            _coletar_e_tratar()
            with sem_saida():
                p = perfil.perfilar()
            gravado = helpers.ler_json(config.DIR_PUBLICADOS / f"perfil_{SLUG}.json")
        self.assertEqual(gravado["meta"]["slug"], SLUG)
        self.assertEqual([t["id"] for t in p["tabelas"]], ["bruto", "tidy", "aux_formas"])
        bruto, tidy, aux = p["tabelas"]
        self.assertEqual((bruto["n_linhas"], tidy["n_linhas"], aux["n_linhas"]), (52, 52 * 6, 6))
        for t in p["tabelas"]:
            self.assertTrue(t["chave_primaria_valida"], t["id"])
            self.assertEqual(t["duplicatas"], 0)
        cob = p["cobertura_temporal"]
        self.assertEqual((cob["inicio"], cob["fim"], cob["lacunas"]), ("2020-01", "2024-04", []))
        for rel in p["relacionamentos"]:
            self.assertEqual(rel["orfaos"], 0, rel)
            self.assertEqual(rel["cobertura_pct"], 100.0)

    def test_situacao_das_formas_na_tabela_auxiliar(self):
        with ambiente_isolado():
            _coletar_e_tratar()
            tidy = pd.read_csv(config.DIR_PROCESSADOS / f"{SLUG}.csv", dtype={"ano_mes": str})
        aux = perfil._montar_auxiliar(tidy, config.fonte()).set_index("forma_pagamento")
        self.assertEqual(aux.loc["Pix", "situacao"], "ativa")
        self.assertEqual(aux.loc["Pix", "primeiro_mes"], "2020-11")
        self.assertEqual(aux.loc["DOC", "situacao"], "sem movimento desde 2024-02")
        self.assertEqual(aux.loc["TEC", "ultimo_mes"], "2024-02")

    def test_forma_sem_nenhum_movimento(self):
        tidy = pd.DataFrame({"ano_mes": ["2024-01", "2024-02"], "forma_pagamento": ["DOC", "DOC"],
                             "quantidade": [0.0, 0.0], "valor": [0.0, 0.0]})
        aux = perfil._montar_auxiliar(tidy, {"formas": {"DOC": "DOC"}})
        self.assertEqual(aux.iloc[0]["situacao"], "sem movimento em toda a serie")
        self.assertEqual(aux.iloc[0]["meses_com_movimento"], 0)

    def test_sem_bruto_pede_a_coleta(self):
        with ambiente_isolado():
            with self.assertRaises(FileNotFoundError):
                perfil.perfilar()

    def test_cobertura_temporal_detecta_lacuna(self):
        from src.perfil import nucleo
        df = pd.DataFrame({"ano_mes": ["2024-01", "2024-03"]})
        cob = nucleo.cobertura_temporal(df)
        self.assertEqual(cob["lacunas"], ["2024-02"])
        self.assertEqual((cob["meses_esperados"], cob["meses_presentes"]), (3, 2))
        vazio = nucleo.cobertura_temporal(pd.DataFrame({"ano_mes": []}))
        self.assertIsNone(vazio["inicio"])


class TestSkillEmpacotada(unittest.TestCase):
    def test_eventos_md_gerado_do_catalogo_de_eventos(self):
        eventos = helpers.ler_json(helpers.DADOS_PUB / "eventos_meios_pagamento.json")
        with ambiente_isolado(), sem_saida():
            skill.gerar_eventos_md()
            md = helpers.ler_texto(skill.DIR_SKILL / "references" / "eventos.md")
        self.assertEqual(md.count("\n## "), len(eventos))
        for ev in eventos:
            self.assertIn(ev["titulo"], md)

    def test_mes_extenso(self):
        self.assertEqual(skill._mes_extenso("2020-11"), "nov/2020")
        self.assertEqual(skill._mes_extenso("2002-04"), "abr/2002")

    def test_zip_tem_a_pasta_da_skill_na_raiz(self):
        with ambiente_isolado(), sem_saida():
            skill.empacotar()
            with zipfile.ZipFile(skill.DESTINO_ZIP) as zf:
                nomes = zf.namelist()
        self.assertIn(f"{skill.NOME_SKILL}/SKILL.md", nomes)
        self.assertIn(f"{skill.NOME_SKILL}/scripts/carregar_dados.py", nomes)
        self.assertTrue(all(n.startswith(f"{skill.NOME_SKILL}/") for n in nomes))
        self.assertFalse([n for n in nomes if "__pycache__" in n])


class TestPipelineCompleto(unittest.TestCase):
    def test_run_pipeline_de_ponta_a_ponta(self):
        import run_pipeline
        with ambiente_isolado() as raiz, api_falsa(), sem_saida():
            run_pipeline.rodar()
            esperados = [
                config.DIR_BRUTOS / f"{SLUG}.json",
                config.DIR_PROCESSADOS / f"{SLUG}.csv",
                config.DIR_PUBLICADOS / f"{SLUG}.json",
                config.DIR_PUBLICADOS / f"{SLUG}.csv",
                config.DIR_PUBLICADOS / f"perfil_{SLUG}.json",
                skill.DESTINO_ZIP,
            ]
            faltando = [str(p.relative_to(raiz)) for p in esperados if not p.exists()]
            notas_criadas = (config.DIR_PUBLICADOS / f"notas_{SLUG}.json").exists()
        self.assertEqual(faltando, [])
        self.assertFalse(notas_criadas, "o pipeline não pode gerar/tocar o notas_*.json (escrito à mão)")

    def test_flags_pulam_coleta_e_perfil(self):
        import run_pipeline
        with ambiente_isolado(), sem_saida():
            with api_falsa():
                coleta.coletar()                       # deixa um bruto para o --sem-coleta
            with mock.patch("requests.get", side_effect=AssertionError("rede!")):
                run_pipeline.rodar(sem_coleta=True, sem_perfil=True)
            self.assertFalse((config.DIR_PUBLICADOS / f"perfil_{SLUG}.json").exists())
            self.assertTrue((config.DIR_PUBLICADOS / f"{SLUG}.json").exists())

    def test_argumentos_da_linha_de_comando(self):
        import run_pipeline
        with mock.patch.object(run_pipeline, "rodar") as rodar, \
             mock.patch("sys.argv", ["run_pipeline.py", "--sem-coleta", "--sem-perfil"]):
            run_pipeline.main()
        rodar.assert_called_once_with(sem_coleta=True, sem_perfil=True)

    def test_publicado_no_repo_bate_com_o_tidy_versionado(self):
        # Reaplica a Etapa 4 sobre o CSV versionado: o JSON publicado precisa ser o mesmo.
        pub = helpers.ler_json(helpers.DADOS_PUB / f"{SLUG}.json")
        with mock.patch.object(config, "DIR_PROCESSADOS", helpers.RAIZ / "dados" / "processados"):
            res = analise.analisar()
        self.assertEqual(pub["labels"], res["labels"])
        self.assertEqual(pub["series"], res["series"])
        self.assertEqual(pub["kpis"], res["kpis"])

    def test_csv_publico_igual_ao_processado(self):
        a = helpers.ler_texto(helpers.DADOS_PUB / f"{SLUG}.csv")
        b = helpers.ler_texto(helpers.RAIZ / "dados" / "processados" / f"{SLUG}.csv")
        self.assertEqual(a, b)
        with (helpers.DADOS_PUB / f"{SLUG}.csv").open(encoding="utf-8", newline="") as f:
            self.assertEqual(next(csv.reader(f)), ["ano_mes", "forma_pagamento", "quantidade", "valor"])


if __name__ == "__main__":
    unittest.main()
