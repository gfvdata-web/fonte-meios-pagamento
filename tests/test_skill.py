"""Skill do Claude (skill/meios-pagamento-bcb): estrutura, script de carga offline e zip publicado."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from src import config
from src.publicacao import skill as empacotador

from tests import helpers
from tests.helpers import DADOS_PUB, RAIZ, SLUG, ler_json

DIR_SKILL = RAIZ / "skill" / "meios-pagamento-bcb"
ZIP_PUBLICO = RAIZ / "docs" / "skill" / "meios-pagamento-bcb.zip"

_spec = importlib.util.spec_from_file_location("carregar_dados", DIR_SKILL / "scripts" / "carregar_dados.py")
cd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cd)


def _linhas_do_csv_publico() -> str:
    return (DADOS_PUB / f"{SLUG}.csv").read_text(encoding="utf-8")


class TestEstruturaDaSkill(unittest.TestCase):
    def test_frontmatter(self):
        texto = helpers.ler_texto(DIR_SKILL / "SKILL.md")
        m = re.match(r"---\nname: (.+)\ndescription: (.+)\n---\n", texto)
        self.assertIsNotNone(m, "SKILL.md sem frontmatter name/description")
        self.assertEqual(m.group(1).strip(), DIR_SKILL.name)
        self.assertGreater(len(m.group(2)), 80)
        self.assertLessEqual(len(m.group(2)), 1024)

    def test_referencias_citadas_no_skill_md_existem(self):
        texto = (DIR_SKILL / "SKILL.md").read_text(encoding="utf-8")
        citadas = set(re.findall(r"`?((?:references|scripts)/[\w.-]+)`?", texto))
        self.assertTrue(citadas)
        for ref in citadas:
            self.assertTrue((DIR_SKILL / ref).is_file(), f"SKILL.md cita {ref}, que não existe")

    def test_urls_do_script_batem_com_o_projeto(self):
        self.assertEqual(cd.URL_BCB, config.fonte()["url"])
        self.assertEqual(cd.FORMAS, list(config.fonte()["formas"]))
        self.assertTrue(cd.URL_SITE.startswith("https://meiospagamento.gfvdata.com/"))
        self.assertTrue(cd.URL_SITE.endswith(f"/dados/{SLUG}.csv"))
        self.assertTrue((DADOS_PUB / f"{SLUG}.csv").is_file())
        self.assertIn(cd.URL_SITE, (DIR_SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_script_compila_e_so_usa_biblioteca_padrao(self):
        fonte = (DIR_SKILL / "scripts" / "carregar_dados.py").read_text(encoding="utf-8")
        compile(fonte, "carregar_dados.py", "exec")
        importados = set(re.findall(r"^(?:import|from) (\w+)", fonte, re.M)) - {"__future__"}
        self.assertLessEqual(importados, set(sys.stdlib_module_names), "a skill roda em ambientes sem pip")


class TestCarregarDados(unittest.TestCase):
    def setUp(self):
        self.api = helpers.resposta_api()["value"]

    def test_de_wide_converte_registros_da_api(self):
        linhas = cd._de_wide(self.api)
        self.assertEqual(len(linhas), len(self.api) * 6)
        l = next(x for x in linhas if x["ano_mes"] == "2021-12" and x["forma_pagamento"] == "Pix")
        reg = next(r for r in self.api if r["AnoMes"] == "202112")
        self.assertEqual((l["quantidade"], l["valor"]), (reg["quantidadePix"], reg["valorPix"]))

    def test_de_wide_trata_nulo_e_forma_ausente(self):
        linhas = cd._de_wide([{"AnoMes": "202401", "quantidadePix": None, "valorPix": 5}])
        self.assertEqual(linhas, [{"ano_mes": "2024-01", "forma_pagamento": "Pix", "quantidade": 0.0, "valor": 5.0}])

    def test_de_csv_aceita_tidy_do_projeto(self):
        linhas = cd._de_csv(_linhas_do_csv_publico())
        self.assertEqual({l["forma_pagamento"] for l in linhas}, set(cd.FORMAS))
        self.assertIsInstance(linhas[0]["quantidade"], float)

    def test_de_csv_aceita_bom_utf8(self):
        linhas = cd._de_csv("﻿" + _linhas_do_csv_publico())
        self.assertTrue(linhas)

    def test_de_csv_aceita_wide_exportado_do_bcb(self):
        wide = "AnoMes,quantidadePix,valorPix\n202401,10,20\n"
        self.assertEqual(cd._de_csv(wide)[0]["forma_pagamento"], "Pix")

    def test_de_csv_rejeita_vazio_e_formato_desconhecido(self):
        with self.assertRaises(ValueError):
            cd._de_csv("")
        with self.assertRaises(ValueError):
            cd._de_csv("a,b\n1,2\n")

    def test_janela_ativa_marca_zeros_de_forma_inexistente(self):
        linhas = cd._de_wide(self.api)
        janelas = cd.marcar_janela_ativa(linhas)
        self.assertEqual(janelas["Pix"][0], "2020-11")
        self.assertEqual(janelas["DOC"][1], "2024-02")
        pix_antes = next(l for l in linhas if l["forma_pagamento"] == "Pix" and l["ano_mes"] == "2020-10")
        pix_dentro = next(l for l in linhas if l["forma_pagamento"] == "Pix" and l["ano_mes"] == "2021-01")
        doc_depois = next(l for l in linhas if l["forma_pagamento"] == "DOC" and l["ano_mes"] == "2024-04")
        self.assertFalse(pix_antes["ativa"])
        self.assertTrue(pix_dentro["ativa"])
        self.assertFalse(doc_depois["ativa"])
        self.assertIsNone(doc_depois["ticket_medio_reais"])

    def test_ticket_medio_em_reais(self):
        linhas = [{"ano_mes": "2024-01", "forma_pagamento": "Pix", "quantidade": 2000.0, "valor": 10.0}]
        cd.marcar_janela_ativa(linhas)
        self.assertEqual(linhas[0]["ticket_medio_reais"], 5.0)     # R$ 10 mi / 2 mi transações

    def test_arquivo_csv_do_usuario(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = Path(tmp) / "anexo.csv"
            arq.write_text(_linhas_do_csv_publico(), encoding="utf-8")
            linhas, origem = cd.carregar("auto", str(arq))
        self.assertTrue(linhas)
        self.assertIn("anexo.csv", origem)

    def test_arquivo_json_nos_dois_formatos(self):
        with tempfile.TemporaryDirectory() as tmp:
            # JSON que seja só uma lista (sem "value"/"registros") hoje quebra com AttributeError
            # em carregar(); o código sugere que deveria ser aceito. Não coberto até ser corrigido.
            for nome, corpo in (("api.json", {"value": self.api}), ("bruto.json", {"registros": self.api})):
                arq = Path(tmp) / nome
                arq.write_text(json.dumps(corpo), encoding="utf-8")
                linhas, _ = cd.carregar("auto", str(arq))
                self.assertEqual(len(linhas), len(self.api) * 6, nome)

    def test_arquivo_inexistente_sai_com_codigo_1(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            cd.carregar("auto", "nao_existe.csv")
        self.assertEqual(ctx.exception.code, 1)

    def test_origem_auto_cai_para_o_site_quando_a_api_falha(self):
        def baixar(url, timeout=60):
            if url == cd.URL_SITE:
                return _linhas_do_csv_publico().encode("utf-8")
            raise OSError("sem rede")
        with mock.patch.object(cd, "_baixar", side_effect=baixar):
            linhas, origem = cd.carregar("auto", None)
        self.assertTrue(linhas)
        self.assertIn("site", origem)

    def test_origem_bcb_usa_a_api(self):
        corpo = json.dumps({"value": self.api}).encode("utf-8")
        with mock.patch.object(cd, "_baixar", return_value=corpo) as baixar:
            linhas, origem = cd.carregar("bcb", None)
        baixar.assert_called_once()
        self.assertEqual(baixar.call_args.args[0], cd.URL_BCB)
        self.assertIn("Olinda", origem)
        self.assertEqual(len(linhas), len(self.api) * 6)

    def test_sem_nenhuma_origem_sai_com_codigo_2_e_orienta(self):
        err = io.StringIO()
        with mock.patch.object(cd, "_baixar", side_effect=OSError("bloqueado")), \
             contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            cd.carregar("auto", None)
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--arquivo", err.getvalue())

    def test_deflacionar_com_ipca_simulado(self):
        linhas = [{"ano_mes": "2024-01", "valor": 100.0}, {"ano_mes": "2024-03", "valor": 100.0}]
        ipca = [{"data": "01/01/2024", "valor": "1.0"}, {"data": "01/02/2024", "valor": "1.0"},
                {"data": "01/03/2024", "valor": "1.0"}]
        with mock.patch.object(cd, "_baixar", return_value=json.dumps(ipca).encode()):
            base = cd.deflacionar(linhas)
        self.assertEqual(base, "2024-03")
        self.assertEqual(linhas[1]["valor_real"], 100.0)                 # mês-base não muda
        self.assertAlmostEqual(linhas[0]["valor_real"], 100 * 1.01 ** 2, places=2)

    def test_deflacionar_sem_rede_segue_sem_valor_real(self):
        linhas = [{"ano_mes": "2024-01", "valor": 1.0}]
        with mock.patch.object(cd, "_baixar", side_effect=OSError), contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(cd.deflacionar(linhas))
        self.assertNotIn("valor_real", linhas[0])

    def test_main_de_ponta_a_ponta_com_arquivo_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            entrada = Path(tmp) / "entrada.csv"
            saida = Path(tmp) / "saida.csv"
            entrada.write_text(_linhas_do_csv_publico(), encoding="utf-8")
            argv = ["carregar_dados.py", "--arquivo", str(entrada), "--saida", str(saida)]
            buf = io.StringIO()
            buf.reconfigure = lambda **_: None
            with mock.patch("sys.argv", argv), contextlib.redirect_stdout(buf):
                with mock.patch.object(sys, "stderr", mock.MagicMock()):
                    cd.main()
            cabecalho = saida.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(cabecalho, "ano_mes,forma_pagamento,quantidade,valor,ativa,ticket_medio_reais")
        self.assertIn("Janela ativa por forma", buf.getvalue())


class TestZipPublicadoEmDia(unittest.TestCase):
    """O zip servido pelo site precisa refletir a pasta skill/ (o pipeline o regenera)."""

    def test_zip_tem_os_mesmos_arquivos_e_conteudo_da_pasta(self):
        fontes = {p.relative_to(DIR_SKILL.parent).as_posix(): p for p in DIR_SKILL.rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts}
        with zipfile.ZipFile(ZIP_PUBLICO) as zf:
            self.assertEqual(sorted(zf.namelist()), sorted(fontes), "arquivos do zip diferem de skill/")
            velhos = [n for n, p in fontes.items()
                      if zf.read(n).replace(b"\r\n", b"\n") != p.read_bytes().replace(b"\r\n", b"\n")]
        self.assertEqual(velhos, [], "zip desatualizado: rode `python -m src.publicacao.skill`")

    def test_eventos_md_da_skill_acompanha_o_catalogo_do_painel(self):
        with helpers.ambiente_isolado(), helpers.sem_saida():
            empacotador.gerar_eventos_md()
            gerado = helpers.ler_texto(empacotador.DIR_SKILL / "references" / "eventos.md")
        atual = helpers.ler_texto(DIR_SKILL / "references" / "eventos.md")
        self.assertEqual(gerado, atual, "references/eventos.md diverge de eventos_meios_pagamento.json")

    def test_zip_sem_lixo(self):
        with zipfile.ZipFile(ZIP_PUBLICO) as zf:
            self.assertIsNone(zf.testzip())
            self.assertFalse([n for n in zf.namelist() if "__pycache__" in n or n.endswith(".pyc")])


if __name__ == "__main__":
    unittest.main()
