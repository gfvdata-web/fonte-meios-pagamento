"""Catálogo de séries: registro em src/config.py, dicionário em catalogo/fonte.md e declarações do perfil."""
from __future__ import annotations

import re
import unittest
from urllib.parse import urlparse

from src import config
from src.perfil import meios_pagamento as perfil

from tests.helpers import RAIZ, SLUG, ler_json, ler_texto, DADOS_PUB

FONTE_MD = ler_texto(RAIZ / "catalogo" / "fonte.md")


class TestRegistroDasFontes(unittest.TestCase):
    def test_slug_registrado_e_unico(self):
        self.assertIn(config.SLUG, config.FONTES)
        self.assertEqual(config.SLUG, SLUG)
        self.assertRegex(config.SLUG, r"^[a-z0-9_]+$")
        self.assertEqual(len(config.FONTES), len(set(config.FONTES)))

    def test_campos_obrigatorios_de_cada_fonte(self):
        for slug, cfg in config.FONTES.items():
            for campo in ("nome", "descricao", "url", "formas", "unidades", "periodicidade", "licenca"):
                self.assertTrue(cfg.get(campo), f"{slug}: falta {campo}")
            self.assertEqual(set(cfg["unidades"]), {"quantidade", "valor"})
            self.assertEqual(cfg["periodicidade"], "mensal")

    def test_url_da_api_bem_formada(self):
        for cfg in config.FONTES.values():
            u = urlparse(cfg["url"])
            self.assertEqual((u.scheme, u.netloc), ("https", "olinda.bcb.gov.br"))
            self.assertIn("$format=json", cfg["url"])
            self.assertIn("MeiosdePagamentosMensalDA", cfg["url"])
            self.assertTrue(cfg["url"].startswith(config.BCB_OLINDA_BASE))

    def test_formas_sao_rotulo_e_sufixo_de_coluna(self):
        formas = config.fonte()["formas"]
        self.assertEqual(list(formas), ["Pix", "TED", "TEC", "Cheque", "Boleto", "DOC"])
        self.assertEqual(len(set(formas.values())), len(formas), "sufixos de coluna repetidos")

    def test_pastas_de_dados_ficam_dentro_do_repo(self):
        for pasta in (config.DIR_BRUTOS, config.DIR_PROCESSADOS, config.DIR_PUBLICADOS):
            self.assertTrue(pasta.is_relative_to(config.RAIZ))
        self.assertEqual(config.DIR_PUBLICADOS, RAIZ / "docs" / "dados")

    def test_erro_de_slug_lista_os_disponiveis(self):
        with self.assertRaises(KeyError) as ctx:
            config.fonte("outra")
        self.assertIn(SLUG, str(ctx.exception))

    def test_modulos_das_etapas_usam_o_mesmo_slug(self):
        from src.analise import meios_pagamento as an
        from src.coleta import meios_pagamento as co
        from src.publicacao import meios_pagamento as pu
        from src.tratamento import meios_pagamento as tr
        for m in (an, co, pu, tr, perfil):
            self.assertEqual(m.SLUG, SLUG, m.__name__)


class TestDicionarioDeDados(unittest.TestCase):
    """catalogo/fonte.md (Etapa 1) deve descrever o que o código realmente usa."""

    def test_menciona_slug_url_e_recurso(self):
        self.assertIn(f"`{SLUG}`", FONTE_MD)
        self.assertIn(config.fonte()["url"], FONTE_MD)
        self.assertIn("MPV_DadosAbertos", FONTE_MD)

    def test_lista_as_mesmas_formas_do_config(self):
        linha = next(l for l in FONTE_MD.splitlines() if l.startswith("Formas ("))
        doc = set(re.findall(r"`(\w+)`", linha.split(":", 1)[1]))
        self.assertEqual(doc, set(config.fonte()["formas"]))

    def test_unidades_documentadas(self):
        self.assertIn("milhares", FONTE_MD)
        self.assertIn("R$ milhões", FONTE_MD)
        self.assertIn("milhares de transações", config.fonte()["unidades"]["quantidade"])
        self.assertIn("milhões", config.fonte()["unidades"]["valor"])

    def test_colunas_do_tidy_documentadas(self):
        secao = FONTE_MD.split("## Formato tidy")[1]
        for col in ("ano_mes", "forma_pagamento", "quantidade", "valor"):
            self.assertIn(f"`{col}`", secao)


class TestDeclaracaoDoPerfil(unittest.TestCase):
    def test_colunas_do_bruto_sao_anomes_mais_duas_por_forma(self):
        esperado = {"AnoMes"}
        for sufixo in config.fonte()["formas"].values():
            esperado |= {f"quantidade{sufixo}", f"valor{sufixo}"}
        self.assertEqual(set(perfil.DECLARACAO["bruto"]["colunas"]), esperado)

    def test_colunas_do_tidy_batem_com_o_csv_publicado(self):
        cab = (DADOS_PUB / f"{SLUG}.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
        self.assertEqual(set(perfil.DECLARACAO["tidy"]["colunas"]), set(cab))
        self.assertEqual(perfil.DECLARACAO["tidy"]["chave_primaria"], ["ano_mes", "forma_pagamento"])

    def test_papeis_declarados_sao_conhecidos(self):
        conhecidos = {"data", "medida", "dimensao", "chave", "texto"}
        for camada, decl in perfil.DECLARACAO.items():
            for nome, (papel, _, desc) in decl["colunas"].items():
                self.assertIn(papel, conhecidos, f"{camada}.{nome}")
                self.assertTrue(desc, f"{camada}.{nome} sem descrição")

    def test_medidas_tem_unidade(self):
        for camada, decl in perfil.DECLARACAO.items():
            for nome, (papel, unidade, _) in decl["colunas"].items():
                if papel == "medida":
                    self.assertTrue(unidade, f"{camada}.{nome} é medida sem unidade")


class TestCatalogoDeEventos(unittest.TestCase):
    """Os marcos históricos são parte do catálogo: ordem, formas e cobertura por forma."""

    def test_toda_forma_ativa_na_serie_tem_pelo_menos_um_marco(self):
        eventos = ler_json(DADOS_PUB / "eventos_meios_pagamento.json")
        citadas = {f for e in eventos for f in e["formas"]}
        for forma in ("Pix", "TED", "Boleto", "Cheque", "DOC", "TEC"):
            self.assertIn(forma, citadas, f"nenhum marco para {forma}")


if __name__ == "__main__":
    unittest.main()
