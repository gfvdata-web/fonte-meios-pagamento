"""Etapa 2 — Coleta da fonte BCB: Meios de Pagamento (mensal).

Consulta a API Olinda/OData do Banco Central e grava a resposta crua em
``dados/brutos/meios_pagamento_mensal.json``. Não transforma nada aqui: o
objetivo é preservar o dado original (Etapa 3 cuida do tratamento).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import requests

from src import config

SLUG = "meios_pagamento_mensal"


def coletar(slug: str = SLUG, timeout: int = 60) -> list[dict]:
    """Baixa a série completa da API e salva o JSON bruto. Retorna os registros."""
    config.garantir_pastas()
    cfg = config.fonte(slug)

    print(f"[coleta] consultando: {cfg['nome']}")
    resposta = requests.get(cfg["url"], timeout=timeout)
    resposta.raise_for_status()
    corpo = resposta.json()
    registros = corpo.get("value", [])

    envelope = {
        "fonte": cfg["nome"],
        "url": cfg["url"],
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "total_registros": len(registros),
        "registros": registros,
    }
    destino = config.DIR_BRUTOS / f"{slug}.json"
    destino.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[coleta] {len(registros)} registros salvos em {destino}")
    return registros


if __name__ == "__main__":
    coletar()
