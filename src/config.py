"""Configuração do repositório — fonte `meios_pagamento_mensal`.

Concentra caminhos de pastas e o registro da fonte usado por todas as etapas.
Este repositório cobre **uma única fonte**; o registro segue em formato de dicionário
por slug para manter o mesmo contrato de código das demais fontes do projeto.
"""
from __future__ import annotations

from pathlib import Path

# --- Caminhos base -----------------------------------------------------------
# src/config.py  ->  raiz do projeto = parent de src/
RAIZ = Path(__file__).resolve().parent.parent

DIR_DADOS = RAIZ / "dados"
DIR_BRUTOS = DIR_DADOS / "brutos"            # Etapa 2 (respostas cruas da API)
DIR_PROCESSADOS = DIR_DADOS / "processados"  # Etapa 3 (CSV tidy)
DIR_PUBLICADOS = RAIZ / "docs" / "dados"     # Etapa 5 (JSON consumido pelo front)


def garantir_pastas() -> None:
    """Cria as pastas de dados caso ainda não existam."""
    for pasta in (DIR_BRUTOS, DIR_PROCESSADOS, DIR_PUBLICADOS):
        pasta.mkdir(parents=True, exist_ok=True)


# --- Registro da fonte -------------------------------------------------------
BCB_OLINDA_BASE = "https://olinda.bcb.gov.br/olinda/servico"

SLUG = "meios_pagamento_mensal"

FONTES: dict[str, dict] = {
    "meios_pagamento_mensal": {
        "nome": "BCB — Estatísticas de Meios de Pagamento (mensal)",
        "descricao": (
            "Quantidade e valor de movimentação por AnoMes e forma de pagamento no Brasil."
        ),
        "url": (
            f"{BCB_OLINDA_BASE}/MPV_DadosAbertos/versao/v1/odata/"
            "MeiosdePagamentosMensalDA(AnoMes=@AnoMes)?@AnoMes=''&$format=json"
        ),
        # Formas de pagamento e o sufixo das colunas quantidade{X}/valor{X}.
        "formas": {
            "Pix": "Pix",
            "TED": "TED",
            "TEC": "TEC",
            "Cheque": "Cheque",
            "Boleto": "Boleto",
            "DOC": "DOC",
        },
        "unidades": {
            "quantidade": "milhares de transações",
            "valor": "R$ milhões",
        },
        "periodicidade": "mensal",
        "licenca": "Dados abertos — Banco Central do Brasil",
    },
}


def fonte(slug: str = SLUG) -> dict:
    """Retorna a configuração da fonte pelo slug, com erro claro se ausente."""
    if slug not in FONTES:
        disponiveis = ", ".join(FONTES) or "(nenhuma)"
        raise KeyError(f"Fonte '{slug}' não registrada. Disponíveis: {disponiveis}")
    return FONTES[slug]
