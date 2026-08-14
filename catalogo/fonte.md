# Dicionário de dados — `meios_pagamento_mensal`

> BCB · Estatísticas de Meios de Pagamento (mensal). Etapa 1 do pipeline.
> Este arquivo documenta **apenas a fonte deste repositório**. A visão consolidada de todas
> as fontes do projeto vive no repositório `controle-global`.

- **Órgão:** Banco Central do Brasil (BCB)
- **API:** Olinda / OData — serviço `MPV_DadosAbertos`
- **Recurso:** `MeiosdePagamentosMensalDA` (FunctionImport, parâmetro `AnoMes`)
- **Endpoint (série completa):**
  ```
  https://olinda.bcb.gov.br/olinda/servico/MPV_DadosAbertos/versao/v1/odata/MeiosdePagamentosMensalDA(AnoMes=@AnoMes)?@AnoMes=''&$format=json
  ```
  > Passar `@AnoMes=''` (vazio) retorna todos os meses. Para um mês específico, use `@AnoMes='202606'`.
- **Periodicidade:** mensal · **Geo:** ⚪ nacional (sem recorte por UF/município)
- **Formatos disponíveis:** `json` (padrão), `xml`, `text/csv`, `text/html`
- **Licença:** Dados abertos — Banco Central do Brasil
- **Portal:** https://dadosabertos.bcb.gov.br/dataset/estatisticas-meios-pagamentos

## Dicionário de dados (formato original "wide")

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `AnoMes` | string `YYYYMM` | Ano e mês de referência |
| `quantidade{Forma}` | decimal | Quantidade de transações da forma (**milhares**) |
| `valor{Forma}` | decimal | Valor movimentado da forma (**R$ milhões**) |

Formas (`{Forma}`): `Pix`, `TED`, `TEC`, `Cheque`, `Boleto`, `DOC`.

> **Unidades:** quantidade em **milhares de transações**; valor em **R$ milhões**.
> **Observação:** `DOC` e `TEC` aparecem zerados nos meses recentes (instrumentos descontinuados).

## Formato tidy após a Etapa 3

| Coluna | Descrição |
|--------|-----------|
| `ano_mes` | `YYYY-MM` |
| `forma_pagamento` | Pix / TED / TEC / Cheque / Boleto / DOC |
| `quantidade` | milhares de transações |
| `valor` | R$ milhões |

Segue a anatomia do contrato tidy do projeto: **dimensões em linha, medidas em coluna**,
sempre com `ano_mes` como primeira dimensão.
