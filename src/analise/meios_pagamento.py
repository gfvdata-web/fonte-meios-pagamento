"""Etapa 4 — Análise estatística da fonte Meios de Pagamento (mensal).

Consome o CSV tidy da Etapa 3 e produz métricas analíticas:
participação (%), crescimento interanual (YoY), CAGR, ticket médio e
estatística descritiva por forma de pagamento. Retorna um dicionário
serializável, usado pela Etapa 5 (publicação).
"""
from __future__ import annotations

import pandas as pd

from src import config

SLUG = "meios_pagamento_mensal"


def _carregar_tidy(slug: str) -> pd.DataFrame:
    caminho = config.DIR_PROCESSADOS / f"{slug}.csv"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Processado ausente: {caminho}. Rode a Etapa 3 (tratamento) antes da análise."
        )
    df = pd.read_csv(caminho, dtype={"ano_mes": str})
    return df


def _cagr_aa(serie: pd.Series, meses_por_ano: int = 12) -> float | None:
    """CAGR anual entre o primeiro e o último valor positivo da série (ordenada asc)."""
    positivos = serie[serie > 0]
    if len(positivos) < 2:
        return None
    v0, vn = positivos.iloc[0], positivos.iloc[-1]
    n_meses = positivos.index[-1] - positivos.index[0]
    anos = n_meses / meses_por_ano
    if anos <= 0 or v0 <= 0:
        return None
    return (vn / v0) ** (1 / anos) - 1


def _yoy_pct(serie: pd.Series) -> float | None:
    """Variação percentual do último mês contra o mesmo mês do ano anterior."""
    if len(serie) < 13:
        return None
    atual, anterior = serie.iloc[-1], serie.iloc[-13]
    if anterior in (0, None) or pd.isna(anterior):
        return None
    return (atual / anterior - 1) * 100


def _desc(serie: pd.Series) -> dict:
    """Estatística descritiva básica de uma série."""
    s = serie.dropna()
    media = float(s.mean()) if len(s) else None
    desvio = float(s.std()) if len(s) > 1 else None
    return {
        "media": media,
        "mediana": float(s.median()) if len(s) else None,
        "desvio_padrao": desvio,
        "coef_variacao_pct": (desvio / media * 100) if (media and desvio) else None,
        "minimo": float(s.min()) if len(s) else None,
        "maximo": float(s.max()) if len(s) else None,
    }


def analisar(slug: str = SLUG) -> dict:
    """Calcula todas as métricas e devolve um dicionário serializável."""
    cfg = config.fonte(slug)
    df = _carregar_tidy(slug)

    meses = sorted(df["ano_mes"].unique())
    formas = list(cfg["formas"].keys())
    valor_total_geral = df["valor"].sum()
    qtd_total_geral = df["quantidade"].sum()

    por_forma = []
    estatisticas = {}
    series = {}

    for forma in formas:
        g = df[df["forma_pagamento"] == forma].sort_values("ano_mes").reset_index(drop=True)
        if g.empty:
            continue
        valor, qtd = g["valor"], g["quantidade"]
        valor_total, qtd_total = float(valor.sum()), float(qtd.sum())
        qtd_ult = float(qtd.iloc[-1])
        val_ult = float(valor.iloc[-1])
        # ticket médio do último mês: valor(R$ milhões) / qtd(milhares) => R$/transação
        ticket = (val_ult * 1_000) / qtd_ult if qtd_ult else None

        por_forma.append({
            "forma": forma,
            "valor_total": valor_total,
            "qtd_total": qtd_total,
            "part_valor_pct": (valor_total / valor_total_geral * 100) if valor_total_geral else None,
            "part_qtd_pct": (qtd_total / qtd_total_geral * 100) if qtd_total_geral else None,
            "valor_ultimo": val_ult,
            "qtd_ultimo": qtd_ult,
            "ticket_medio_ultimo_rs": ticket,
            "yoy_valor_pct": _yoy_pct(valor),
            "cagr_valor_aa_pct": (lambda c: c * 100 if c is not None else None)(_cagr_aa(valor)),
        })
        estatisticas[forma] = {"valor": _desc(valor), "quantidade": _desc(qtd)}
        series[forma] = {
            "quantidade": [None if pd.isna(v) else float(v) for v in qtd],
            "valor": [None if pd.isna(v) else float(v) for v in valor],
        }

    # Ordena ranking por valor total (desc).
    por_forma.sort(key=lambda x: x["valor_total"], reverse=True)

    return {
        "labels": meses,
        "formas": formas,
        "series": series,
        "kpis": {
            "por_forma": por_forma,
            "totais": {
                "mes_ref": meses[-1],
                "valor_ultimo_mes": float(df[df["ano_mes"] == meses[-1]]["valor"].sum()),
                "qtd_ultimo_mes": float(df[df["ano_mes"] == meses[-1]]["quantidade"].sum()),
                "meses_cobertos": len(meses),
            },
        },
        "estatisticas": estatisticas,
    }


if __name__ == "__main__":
    import json

    resultado = analisar()
    print(json.dumps(resultado["kpis"]["totais"], ensure_ascii=False, indent=2))
