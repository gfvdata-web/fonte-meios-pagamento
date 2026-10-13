"""Carrega a série BCB de Meios de Pagamento (mensal) em formato tidy, pronta para análise.

Só usa a biblioteca padrão do Python, para rodar em qualquer ambiente.

Ordem de tentativa (origem "auto"):
  1. API Olinda do Banco Central (dado oficial e mais recente; formato wide, convertido aqui);
  2. CSV tratado publicado pelo projeto (GitHub Pages), caso a API esteja fora ou bloqueada;
  3. se as duas falharem, o script avisa e sai com código 2 — peça o CSV ao usuário
     e rode de novo com --arquivo.

Saída: CSV com as colunas
  ano_mes, forma_pagamento, quantidade, valor, ativa, ticket_medio_reais [, valor_real]

Uso:
  python carregar_dados.py                          # auto, grava meios_pagamento.csv
  python carregar_dados.py --origem bcb             # força a API do BCB
  python carregar_dados.py --arquivo anexo.csv      # usa um arquivo enviado pelo usuário
  python carregar_dados.py --ipca                   # acrescenta valor deflacionado pelo IPCA
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
from pathlib import Path

URL_SITE = "https://meiospagamento.gfvdata.com/dados/meios_pagamento_mensal.csv"
URL_BCB = (
    "https://olinda.bcb.gov.br/olinda/servico/MPV_DadosAbertos/versao/v1/odata/"
    "MeiosdePagamentosMensalDA(AnoMes=@AnoMes)?@AnoMes=''&$format=json"
)
# IPCA — variação mensal (%), série 433 do SGS/BCB.
URL_IPCA = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados"
    "?formato=json&dataInicial=01/01/2002"
)
FORMAS = ["Pix", "TED", "TEC", "Cheque", "Boleto", "DOC"]
CABECALHO_UA = {"User-Agent": "skill-meios-pagamento-bcb/1.0"}


def _baixar(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=CABECALHO_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# --- Leitura das origens -----------------------------------------------------

def _de_wide(registros: list[dict]) -> list[dict]:
    """Converte registros no formato da API (AnoMes + quantidadeX/valorX) para tidy."""
    linhas = []
    for reg in registros:
        am = str(reg["AnoMes"])
        ano_mes = f"{am[:4]}-{am[4:6]}"
        for forma in FORMAS:
            if f"quantidade{forma}" not in reg:
                continue
            linhas.append({
                "ano_mes": ano_mes,
                "forma_pagamento": forma,
                "quantidade": float(reg.get(f"quantidade{forma}") or 0),
                "valor": float(reg.get(f"valor{forma}") or 0),
            })
    return linhas


def _de_csv(texto: str) -> list[dict]:
    """Aceita o CSV tidy do projeto ou o CSV wide exportado da API do BCB."""
    leitor = csv.DictReader(io.StringIO(texto.lstrip("﻿")))
    linhas = list(leitor)
    if not linhas:
        raise ValueError("CSV vazio.")
    colunas = set(linhas[0])
    if {"ano_mes", "forma_pagamento", "quantidade", "valor"} <= colunas:
        return [{
            "ano_mes": l["ano_mes"],
            "forma_pagamento": l["forma_pagamento"],
            "quantidade": float(l["quantidade"] or 0),
            "valor": float(l["valor"] or 0),
        } for l in linhas]
    if "AnoMes" in colunas:
        return _de_wide(linhas)
    raise ValueError(f"Formato de CSV não reconhecido. Colunas: {sorted(colunas)}")


def carregar(origem: str, arquivo: str | None) -> tuple[list[dict], str]:
    if arquivo:
        caminho = Path(arquivo)
        if not caminho.is_file():
            print(f"Arquivo não encontrado: {caminho}", file=sys.stderr)
            sys.exit(1)
        texto = caminho.read_text(encoding="utf-8")
        if caminho.suffix.lower() == ".json":
            corpo = json.loads(texto)
            # objeto da API ("value"), bruto do pipeline ("registros") ou lista simples de registros
            registros = corpo if isinstance(corpo, list) else (corpo.get("value") or corpo.get("registros") or corpo)
            return _de_wide(registros), f"arquivo {caminho.name}"
        return _de_csv(texto), f"arquivo {caminho.name}"

    tentativas = {"site": ["site"], "bcb": ["bcb"], "auto": ["bcb", "site"]}[origem]
    erros = []
    for alvo in tentativas:
        try:
            if alvo == "site":
                return _de_csv(_baixar(URL_SITE).decode("utf-8")), f"site do projeto ({URL_SITE})"
            corpo = json.loads(_baixar(URL_BCB, timeout=120))
            return _de_wide(corpo["value"]), "API Olinda do Banco Central"
        except Exception as exc:  # rede bloqueada, timeout, formato inesperado
            erros.append(f"  - {alvo}: {type(exc).__name__}: {exc}")
    print("Não foi possível baixar os dados:\n" + "\n".join(erros), file=sys.stderr)
    print(
        "\nProvável bloqueio de rede no ambiente. Peça ao usuário para baixar o CSV em\n"
        f"  {URL_SITE}\n"
        "e anexá-lo à conversa; depois rode de novo com --arquivo <caminho>.",
        file=sys.stderr,
    )
    sys.exit(2)


# --- Enriquecimento ----------------------------------------------------------

def marcar_janela_ativa(linhas: list[dict]) -> dict[str, tuple[str, str]]:
    """Marca `ativa` = mês dentro da janela em que a forma existiu na série.

    A fonte registra ausência como zero: Pix antes de nov/2020 e DOC/TEC depois de
    fev/2024 aparecem como 0, não como vazio. A janela vai do primeiro ao último mês
    com quantidade > 0.
    """
    janelas: dict[str, tuple[str, str]] = {}
    for l in linhas:
        if l["quantidade"] > 0:
            ini, fim = janelas.get(l["forma_pagamento"], (l["ano_mes"], l["ano_mes"]))
            janelas[l["forma_pagamento"]] = (min(ini, l["ano_mes"]), max(fim, l["ano_mes"]))
    for l in linhas:
        jan = janelas.get(l["forma_pagamento"])
        l["ativa"] = bool(jan and jan[0] <= l["ano_mes"] <= jan[1])
        # quantidade em milhares e valor em R$ milhões -> ticket em reais = valor/quantidade*1000
        l["ticket_medio_reais"] = (
            round(l["valor"] / l["quantidade"] * 1000, 2) if l["quantidade"] > 0 else None
        )
    return janelas


def deflacionar(linhas: list[dict]) -> str | None:
    """Acrescenta `valor_real` (R$ milhões a preços do último mês com IPCA). Retorna o mês-base."""
    try:
        serie = json.loads(_baixar(URL_IPCA))
    except Exception as exc:
        print(f"[aviso] IPCA indisponível ({type(exc).__name__}); seguindo sem valor_real.",
              file=sys.stderr)
        return None
    indice, acumulado = {}, 1.0
    for ponto in serie:
        dia, mes, ano = ponto["data"].split("/")
        acumulado *= 1 + float(ponto["valor"]) / 100
        indice[f"{ano}-{mes}"] = acumulado
    meses_comuns = sorted(set(indice) & {l["ano_mes"] for l in linhas})
    base = meses_comuns[-1]
    for l in linhas:
        fator = indice.get(l["ano_mes"])
        l["valor_real"] = round(l["valor"] * indice[base] / fator, 2) if fator else None
    return base


# --- Saída -------------------------------------------------------------------

def _fmt(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def resumir(linhas: list[dict], janelas: dict, origem: str, base_ipca: str | None) -> None:
    meses = sorted({l["ano_mes"] for l in linhas})
    ultimo = meses[-1]
    print(f"Origem: {origem}")
    print(f"Período: {meses[0]} a {ultimo} ({len(meses)} meses, {len(linhas)} linhas)")
    print("Unidades: quantidade = milhares de transações; valor = R$ milhões (nominal)")
    if base_ipca:
        print(f"valor_real: R$ milhões a preços de {base_ipca} (IPCA, SGS 433)")
    print("\nJanela ativa por forma (fora dela, zero = forma não existia na série):")
    for forma in FORMAS:
        if forma in janelas:
            ini, fim = janelas[forma]
            status = "ativa" if fim == ultimo else "encerrada"
            print(f"  {forma:<7} {ini} a {fim}  ({status})")
    doms = [l for l in linhas if l["ano_mes"] == ultimo and l["ativa"]]
    tot_q = sum(l["quantidade"] for l in doms) or 1
    tot_v = sum(l["valor"] for l in doms) or 1
    print(f"\nÚltimo mês ({ultimo}):")
    print(f"  {'forma':<7} {'qtd (mil)':>12} {'% qtd':>6} {'valor (R$ mi)':>14} {'% valor':>8} {'ticket (R$)':>12}")
    for l in sorted(doms, key=lambda x: -x["valor"]):
        print(f"  {l['forma_pagamento']:<7} {_fmt(l['quantidade']):>12} "
              f"{l['quantidade'] / tot_q:>6.1%} {_fmt(l['valor']):>14} "
              f"{l['valor'] / tot_v:>8.1%} {_fmt(l['ticket_medio_reais']):>12}")


def gravar(linhas: list[dict], saida: Path) -> None:
    colunas = ["ano_mes", "forma_pagamento", "quantidade", "valor", "ativa", "ticket_medio_reais"]
    if any("valor_real" in l for l in linhas):
        colunas.append("valor_real")
    with saida.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(sorted(linhas, key=lambda l: (l["ano_mes"], l["forma_pagamento"])))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--origem", choices=["auto", "site", "bcb"], default="auto")
    p.add_argument("--arquivo", help="CSV/JSON enviado pelo usuário (tidy do projeto ou wide do BCB)")
    p.add_argument("--ipca", action="store_true", help="acrescenta valor_real deflacionado pelo IPCA")
    p.add_argument("--saida", default="meios_pagamento.csv")
    args = p.parse_args()
    for fluxo in (sys.stdout, sys.stderr):
        fluxo.reconfigure(encoding="utf-8")

    linhas, origem = carregar(args.origem, args.arquivo)
    janelas = marcar_janela_ativa(linhas)
    base_ipca = deflacionar(linhas) if args.ipca else None
    saida = Path(args.saida)
    gravar(linhas, saida)
    resumir(linhas, janelas, origem, base_ipca)
    print(f"\nArquivo gravado: {saida.resolve()}")


if __name__ == "__main__":
    main()
