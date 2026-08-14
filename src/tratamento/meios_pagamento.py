"""Etapa 3 — Tratamento da fonte Meios de Pagamento (mensal).

Converte o JSON bruto (formato "wide": uma coluna por forma de pagamento) para o
formato **tidy/long** padrão do projeto:

    ano_mes | forma_pagamento | quantidade | valor

Grava o resultado em ``dados/processados/meios_pagamento_mensal.csv``.
"""
from __future__ import annotations

import json

import pandas as pd

from src import config

SLUG = "meios_pagamento_mensal"


def _carregar_bruto(slug: str) -> list[dict]:
    caminho = config.DIR_BRUTOS / f"{slug}.json"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Bruto ausente: {caminho}. Rode a Etapa 2 (coleta) antes do tratamento."
        )
    return json.loads(caminho.read_text(encoding="utf-8"))["registros"]


def tratar(slug: str = SLUG) -> pd.DataFrame:
    """Transforma o bruto em DataFrame tidy e salva CSV. Retorna o DataFrame."""
    config.garantir_pastas()
    cfg = config.fonte(slug)
    registros = _carregar_bruto(slug)

    bruto = pd.DataFrame(registros)
    # Normaliza AnoMes "202605" -> "2026-05".
    bruto["ano_mes"] = (
        bruto["AnoMes"].astype(str).str.slice(0, 4)
        + "-"
        + bruto["AnoMes"].astype(str).str.slice(4, 6)
    )

    linhas = []
    for rotulo, sufixo in cfg["formas"].items():
        col_qtd, col_val = f"quantidade{sufixo}", f"valor{sufixo}"
        if col_qtd not in bruto or col_val not in bruto:
            continue
        parte = bruto[["ano_mes", col_qtd, col_val]].copy()
        parte.columns = ["ano_mes", "quantidade", "valor"]
        parte.insert(1, "forma_pagamento", rotulo)
        linhas.append(parte)

    tidy = pd.concat(linhas, ignore_index=True)
    tidy["quantidade"] = pd.to_numeric(tidy["quantidade"], errors="coerce")
    tidy["valor"] = pd.to_numeric(tidy["valor"], errors="coerce")
    tidy = tidy.sort_values(["ano_mes", "forma_pagamento"]).reset_index(drop=True)

    destino = config.DIR_PROCESSADOS / f"{slug}.csv"
    tidy.to_csv(destino, index=False, encoding="utf-8")
    print(f"[tratamento] {len(tidy)} linhas tidy salvas em {destino}")
    return tidy


if __name__ == "__main__":
    tratar()
