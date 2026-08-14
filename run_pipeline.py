"""Orquestrador do pipeline — executa as Etapas 2 → 5 da fonte deste repositório.

Uso:
    python run_pipeline.py                # pipeline completo
    python run_pipeline.py --sem-coleta   # reusa o bruto já baixado
"""
from __future__ import annotations

import argparse

from src import config
from src.coleta import meios_pagamento as coleta
from src.tratamento import meios_pagamento as tratamento
from src.publicacao import meios_pagamento as publicacao


def rodar(sem_coleta: bool = False) -> None:
    print(f"=== Pipeline: {config.fonte()['nome']} ===")

    if sem_coleta:
        print("[pipeline] Etapa 2 (coleta) pulada — reusando bruto existente.")
    else:
        coleta.coletar(config.SLUG)

    tratamento.tratar(config.SLUG)
    publicacao.publicar(config.SLUG)
    print("=== Pipeline concluído com sucesso ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline da fonte meios_pagamento_mensal.")
    parser.add_argument("--sem-coleta", action="store_true",
                        help="Não consulta a API; reusa o bruto já salvo.")
    args = parser.parse_args()
    rodar(sem_coleta=args.sem_coleta)


if __name__ == "__main__":
    main()
