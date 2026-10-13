"""Apoio dos testes: caminhos, fixture da API e um ambiente isolado em pasta temporária.

Nada aqui acessa a rede nem escreve dentro do repositório: o pipeline roda com as pastas de
dados (src.config) e os caminhos da skill redirecionados para um diretório temporário.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
DADOS_PUB = DOCS / "dados"
FIXTURE_API = RAIZ / "tests" / "fixtures" / "olinda_resposta.json"
SLUG = "meios_pagamento_mensal"


def ler_json(caminho: Path):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def ler_texto(caminho: Path) -> str:
    """Texto com quebras de linha normalizadas (o checkout no Windows converte para CRLF)."""
    return Path(caminho).read_text(encoding="utf-8").replace("\r\n", "\n")


def resposta_api() -> dict:
    """Corpo JSON como a API Olinda devolve (cópia da fixture, segura para mutar)."""
    return ler_json(FIXTURE_API)


class RespostaFalsa:
    """Substituto mínimo de requests.Response."""

    def __init__(self, corpo, status: int = 200):
        self._corpo, self.status_code = corpo, status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._corpo


@contextlib.contextmanager
def ambiente_isolado():
    """Redireciona dados/, docs/dados/ e a skill para uma pasta temporária; devolve a raiz dela."""
    from src import config
    from src.publicacao import skill

    with tempfile.TemporaryDirectory(prefix="mp-teste-") as tmp:
        raiz = Path(tmp)
        brutos, proc, pub = raiz / "dados" / "brutos", raiz / "dados" / "processados", raiz / "docs" / "dados"
        pub.mkdir(parents=True)
        shutil.copy(DADOS_PUB / "eventos_meios_pagamento.json", pub / "eventos_meios_pagamento.json")
        dir_skill = raiz / "skill" / skill.NOME_SKILL
        shutil.copytree(skill.DIR_SKILL, dir_skill)
        with contextlib.ExitStack() as pilha:
            pilha.enter_context(mock.patch.object(config, "DIR_BRUTOS", brutos))
            pilha.enter_context(mock.patch.object(config, "DIR_PROCESSADOS", proc))
            pilha.enter_context(mock.patch.object(config, "DIR_PUBLICADOS", pub))
            pilha.enter_context(mock.patch.object(skill, "DIR_SKILL", dir_skill))
            pilha.enter_context(mock.patch.object(skill, "DESTINO_ZIP", raiz / "docs" / "skill" / "x.zip"))
            pilha.enter_context(mock.patch.object(skill, "ARQ_EVENTOS", pub / "eventos_meios_pagamento.json"))
            yield raiz


@contextlib.contextmanager
def api_falsa(corpo=None, status: int = 200):
    """Troca requests.get por uma resposta da fixture (ou o corpo/status dados). Sem rede."""
    corpo = resposta_api() if corpo is None else corpo
    with mock.patch("requests.get", return_value=RespostaFalsa(corpo, status)) as falso:
        yield falso


@contextlib.contextmanager
def sem_saida():
    """Silencia os print() do pipeline."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield
