# Meios de Pagamento no Brasil — BCB

Pipeline e dashboard da série **BCB — Estatísticas de Meios de Pagamento (mensal)**:
quantidade e valor de movimentação por mês e forma de pagamento (Pix, TED, TEC, Cheque,
Boleto, DOC), coletados da API Olinda/OData do Banco Central.

**Painel publicado:** https://gfvdata-web.github.io/fonte-meios-pagamento/

> 📄 Organização do repositório e etapas do pipeline: **[CONTEXTO.md](CONTEXTO.md)**
> 📚 Dicionário de dados da fonte: **[catalogo/fonte.md](catalogo/fonte.md)**
> 🌐 Visão de todas as fontes do projeto: repositório **`controle-global`**

## Como rodar

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_pipeline.py
```

O pipeline executa Etapa 2 (coleta) → Etapa 3 (tratamento) → Etapa 5 (publicação) e grava
o JSON que o dashboard consome em `docs/dados/`.

`python run_pipeline.py --sem-coleta` reaproveita o dado bruto já baixado (não chama a API).

Para ver o dashboard localmente:

```bash
python -m http.server 8000 --directory docs
```

## Estrutura

| Pasta | Etapa | Papel |
|-------|-------|-------|
| `catalogo/` | 1 | Dicionário de dados da fonte |
| `src/coleta/` | 2 | Coleta via API → `dados/brutos/` |
| `src/tratamento/` | 3 | Tidy → `dados/processados/` |
| `src/analise/` | 4 | Estatística e métricas |
| `src/publicacao/` | 5 | JSON → `docs/dados/` |
| `docs/` | 6 | Dashboard (site publicado) |

## Licença dos dados

Dados abertos do Banco Central do Brasil. Detalhes em
[`catalogo/fonte.md`](catalogo/fonte.md).
