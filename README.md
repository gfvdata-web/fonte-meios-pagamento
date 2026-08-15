# Meios de Pagamento no Brasil — BCB

Pipeline e dashboard da série **BCB — Estatísticas de Meios de Pagamento (mensal)**:
quantidade e valor de movimentação por mês e forma de pagamento (Pix, TED, TEC, Cheque,
Boleto, DOC), coletados da API Olinda/OData do Banco Central.

**Painel publicado:** https://gfvdata-web.github.io/fonte-meios-pagamento/
**Explorar os dados (Etapa E):** https://gfvdata-web.github.io/fonte-meios-pagamento/explorar.html

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

O pipeline executa Etapa 2 (coleta) → Etapa 3 (tratamento) → **Etapa E (perfil)** →
Etapa 5 (publicação) e grava em `docs/dados/` o JSON que o dashboard consome e o
`perfil_meios_pagamento_mensal.json` que a página de exploração consome.

- `python run_pipeline.py --sem-coleta` reaproveita o dado bruto já baixado (não chama a API).
- `python run_pipeline.py --sem-perfil` pula a Etapa E.

> **`docs/dados/notas_meios_pagamento_mensal.json` é escrito à mão** e nenhum script o
> sobrescreve. É onde ficam as armadilhas, os comparativos, o contexto externo pesquisado e a
> pauta de visualizações que alimentam a página `explorar.html`.

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
| `src/perfil/` | E | Perfil das tabelas → `docs/dados/perfil_*.json` |
| `src/publicacao/` | 5 | JSON → `docs/dados/` |
| `docs/index.html` | 6 | Dashboard (site publicado) |
| `docs/explorar.html` | E | Perfil das tabelas + pauta analítica |

## Licença dos dados

Dados abertos do Banco Central do Brasil. Detalhes em
[`catalogo/fonte.md`](catalogo/fonte.md).
