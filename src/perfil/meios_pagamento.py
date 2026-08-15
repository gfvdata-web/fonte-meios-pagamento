"""Etapa E — perfil das tabelas da fonte `meios_pagamento_mensal`.

Perfila as três camadas:

- **bruto**    — resposta da API Olinda, formato wide (uma coluna por forma × medida);
- **tidy**     — `dados/processados/meios_pagamento_mensal.csv`, o contrato do projeto;
- **auxiliar** — `formas`, o de-para entre as colunas do bruto e a dimensão do tidy,
  enriquecido com a vida útil de cada forma (é o que revela TEC e DOC zerados).

Gera `docs/dados/perfil_meios_pagamento_mensal.json`.
"""
from __future__ import annotations

import json

import pandas as pd

from src import config
from src.perfil import nucleo

SLUG = "meios_pagamento_mensal"

_QTD = "milhares de transações"
_VAL = "R$ milhões"

DECLARACAO: dict[str, dict] = {
    "bruto": {
        "granularidade": "uma linha por mês; formato wide, uma coluna de quantidade e uma de valor por forma",
        "chave_primaria": ["AnoMes"],
        "colunas": {
            "AnoMes": ("data", None, "Mês de referência, no formato AAAAMM da API"),
            "quantidadePix": ("medida", _QTD, "Transações Pix no mês"),
            "valorPix": ("medida", _VAL, "Montante transacionado via Pix"),
            "quantidadeTED": ("medida", _QTD, "Transferências eletrônicas disponíveis"),
            "valorTED": ("medida", _VAL, "Montante transacionado via TED"),
            "quantidadeTEC": ("medida", _QTD, "Transferências especiais de crédito"),
            "valorTEC": ("medida", _VAL, "Montante transacionado via TEC"),
            "quantidadeCheque": ("medida", _QTD, "Cheques compensados"),
            "valorCheque": ("medida", _VAL, "Montante em cheques compensados"),
            "quantidadeBoleto": ("medida", _QTD, "Boletos liquidados"),
            "valorBoleto": ("medida", _VAL, "Montante em boletos liquidados"),
            "quantidadeDOC": ("medida", _QTD, "Documentos de ordem de crédito"),
            "valorDOC": ("medida", _VAL, "Montante transacionado via DOC"),
        },
    },
    "tidy": {
        "granularidade": "uma linha por mês × forma de pagamento",
        "chave_primaria": ["ano_mes", "forma_pagamento"],
        "colunas": {
            "ano_mes": ("data", None, "Mês de referência (YYYY-MM)"),
            "forma_pagamento": ("dimensao", None, "Instrumento de pagamento"),
            "quantidade": ("medida", _QTD, "Volume de transações no mês"),
            "valor": ("medida", _VAL, "Montante transacionado no mês"),
        },
    },
    "aux_formas": {
        "granularidade": "uma linha por forma de pagamento",
        "chave_primaria": ["forma_pagamento"],
        "colunas": {
            "forma_pagamento": ("chave", None, "Valor assumido pela dimensão no tidy"),
            "coluna_quantidade": ("texto", None, "Coluna de origem no bruto (wide)"),
            "coluna_valor": ("texto", None, "Coluna de origem no bruto (wide)"),
            "primeiro_mes": ("data", None, "Primeiro mês com movimento registrado"),
            "ultimo_mes": ("data", None, "Último mês com movimento registrado"),
            "meses_com_movimento": ("medida", "meses", "Meses com quantidade > 0"),
            "situacao": ("dimensao", None, "Ativa ou descontinuada na série"),
        },
    },
}


def _ler_bruto() -> tuple[pd.DataFrame, dict]:
    caminho = config.DIR_BRUTOS / f"{SLUG}.json"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Bruto ausente: {caminho}. Rode a Etapa 2 (coleta) antes da Etapa E."
        )
    envelope = json.loads(caminho.read_text(encoding="utf-8"))
    df = pd.DataFrame(envelope["registros"])
    return df, envelope


def _montar_auxiliar(tidy: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """De-para bruto→tidy das formas, com a vida útil medida em cima do tidy."""
    ultimo_mes_serie = tidy["ano_mes"].max()
    linhas = []
    for rotulo, sufixo in cfg["formas"].items():
        parte = tidy[tidy["forma_pagamento"] == rotulo]
        ativos = parte[parte["quantidade"].fillna(0) > 0]
        ultimo = ativos["ano_mes"].max() if not ativos.empty else None
        linhas.append({
            "forma_pagamento": rotulo,
            "coluna_quantidade": f"quantidade{sufixo}",
            "coluna_valor": f"valor{sufixo}",
            "primeiro_mes": ativos["ano_mes"].min() if not ativos.empty else None,
            "ultimo_mes": ultimo,
            "meses_com_movimento": int(len(ativos)),
            "situacao": ("ativa" if ultimo == ultimo_mes_serie
                         else f"sem movimento desde {ultimo}" if ultimo
                         else "sem movimento em toda a serie"),
        })
    return pd.DataFrame(linhas)


def perfilar(slug: str = SLUG) -> dict:
    cfg = config.fonte(slug)
    bruto, envelope = _ler_bruto()
    tidy = pd.read_csv(config.DIR_PROCESSADOS / f"{slug}.csv", dtype={"ano_mes": str})
    aux = _montar_auxiliar(tidy, cfg)

    t_bruto = nucleo.perfilar_tabela(
        bruto, id="bruto", camada="bruto",
        nome="Resposta da API Olinda (formato wide)",
        arquivo=f"dados/brutos/{slug}.json",
        formato="JSON (OData v4) — não versionado; este perfil é o registro da forma dele",
        origem=cfg["url"],
        declaracao=DECLARACAO["bruto"],
        alertas_extra=[
            f"coletado em {envelope.get('coletado_em', '?')}",
            "a API devolve os meses em ordem decrescente (o mais recente é a primeira linha)",
            "formato wide: cada forma de pagamento é um par de colunas, não uma linha — "
            "é o que a Etapa 3 desfaz",
        ],
    )
    t_tidy = nucleo.perfilar_tabela(
        tidy, id="tidy", camada="tidy",
        nome="Tidy do projeto — dimensões em linha, medidas em coluna",
        arquivo=f"dados/processados/{slug}.csv",
        formato="CSV UTF-8",
        origem="Etapa 3 (src/tratamento/meios_pagamento.py)",
        declaracao=DECLARACAO["tidy"],
    )
    t_aux = nucleo.perfilar_tabela(
        aux, id="aux_formas", camada="auxiliar",
        nome="De-para das formas de pagamento (bruto wide → dimensão do tidy)",
        arquivo="derivada em memória (src/config.py FONTES['…']['formas'] + tidy)",
        formato="tabela derivada",
        origem="Etapa E",
        declaracao=DECLARACAO["aux_formas"],
    )

    # Join medido de fato: o mês do tidy tem correspondente no bruto?
    bruto_norm = pd.DataFrame({
        "ano_mes": bruto["AnoMes"].astype(str).str[:4] + "-" + bruto["AnoMes"].astype(str).str[4:6]
    })
    rel_mes = nucleo.relacionamento(
        tidy, "ano_mes", bruto_norm, "ano_mes",
        cardinalidade="N:1 (6 linhas tidy por mês do bruto)",
        uso="cada mês do bruto vira 6 linhas no tidy, uma por forma",
    )
    rel_mes["para"] = "AnoMes (normalizado para YYYY-MM)"
    rel_forma = nucleo.relacionamento(
        tidy, "forma_pagamento", aux, "forma_pagamento",
        cardinalidade="N:1",
        uso="resolve a forma para as colunas de origem no bruto e para a vida útil da série",
    )

    perfil = nucleo.montar(
        slug=slug,
        fonte_nome=cfg["nome"],
        tabelas=[t_bruto, t_tidy, t_aux],
        relacionamentos=[
            nucleo.liga(rel_mes, "tidy", "bruto"),
            nucleo.liga(rel_forma, "tidy", "aux_formas"),
        ],
        cobertura=nucleo.cobertura_temporal(tidy),
    )
    nucleo.salvar(perfil, config.DIR_PUBLICADOS / f"perfil_{slug}.json")
    return perfil


if __name__ == "__main__":
    perfilar()
