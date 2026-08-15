# CONTEXTO — fonte `meios_pagamento_mensal`

> Arquivo-mestre de contexto **deste repositório**. Cole/aponte este arquivo ao abrir uma
> sessão sobre esta fonte. Ao pedir uma tarefa, cite a **Etapa** correspondente
> (ex.: "trabalhar na **Etapa 4**", "ajustar a **Etapa 6** sem quebrar a **Etapa 5**").
>
> A visão de todas as fontes do projeto (convenções comuns, catálogo de candidatas,
> roadmap global) vive no repositório **`controle-global`**. Aqui só o que é desta fonte.

---

## 1. O que este repositório faz

Coleta, trata, analisa e publica a série **BCB — Estatísticas de Meios de Pagamento
(mensal)**: quantidade e valor de movimentação por `AnoMes` e forma de pagamento no Brasil
(Pix, TED, TEC, Cheque, Boleto, DOC).

- **Fonte:** Banco Central do Brasil, API Olinda/OData. Dicionário completo em
  [`catalogo/fonte.md`](catalogo/fonte.md).
- **Entrega:** dashboard estático em `docs/`, publicado via GitHub Pages.
- **Escopo:** uma fonte só. Nada aqui depende de outro repositório do projeto.

## 2. Princípios de trabalho

- **Integração acima de tudo:** cada etapa tem contrato de entrada/saída definido (seção 5).
  Alterações devem respeitar esses contratos.
- **Não quebrar:** ao ajustar uma etapa, verificar as vizinhas (a que produz a entrada e a
  que consome a saída). `run_pipeline.py` deve continuar rodando de ponta a ponta.
- **Reprodutibilidade:** qualquer JSON publicado deve ser regenerável rodando o pipeline.
- **Idioma do código:** nomes de funções/variáveis e comentários em português.

## 3. Stack

| Camada | Tecnologia |
|--------|-----------|
| Coleta / tratamento / análise | Python 3.13 (`requests`, `pandas`) |
| Publicação de dados | JSON estático gerado pelo Python |
| Front-end / dashboard | HTML + CSS + JavaScript com Chart.js (via CDN) |
| Hospedagem | GitHub Pages (pasta `/docs`) |

## 4. Estrutura de pastas

```
fonte-meios-pagamento/
├── CONTEXTO.md                 # este arquivo
├── README.md
├── requirements.txt
├── run_pipeline.py             # orquestra as Etapas 2→5
├── src/
│   ├── config.py               # caminhos + registro da fonte
│   ├── coleta/meios_pagamento.py       # Etapa 2
│   ├── tratamento/meios_pagamento.py   # Etapa 3
│   ├── perfil/meios_pagamento.py       # Etapa E (+ perfil/nucleo.py, motor generico)
│   ├── analise/meios_pagamento.py      # Etapa 4
│   └── publicacao/meios_pagamento.py   # Etapa 5
├── dados/
│   ├── brutos/                 # resposta crua da API (regenerável; fora do git)
│   └── processados/            # CSV tidy
├── docs/                       # Etapas 6 e E — site publicado
│   ├── index.html                      # Etapa 6 — painel
│   ├── explorar.html                   # Etapa E — perfil + pauta analitica
│   ├── css/estilo.css
│   ├── js/app.js
│   ├── js/explorar.js
│   └── dados/
│       ├── meios_pagamento_mensal.json         # Etapa 5 (gerado)
│       ├── perfil_meios_pagamento_mensal.json  # Etapa E (gerado)
│       └── notas_meios_pagamento_mensal.json   # Etapa E (a mao, nunca sobrescrito)
└── catalogo/fonte.md           # Etapa 1 — dicionário de dados
```

## 5. As Etapas e os contratos entre elas

```
[API Olinda]  ──Etapa 2──▶  dados/brutos/meios_pagamento_mensal.json
                                │
                           ──Etapa 3──▶  dados/processados/meios_pagamento_mensal.csv
                                │
               ┌────────────────┴─────────────────┐
          ──Etapa 4──▶ métricas          ──Etapa 5──▶ docs/dados/meios_pagamento_mensal.json
                                                 │
                                            ──Etapa 6──▶ docs/index.html

               ──Etapa E──▶  docs/dados/perfil_meios_pagamento_mensal.json  (gerado)
                             docs/dados/notas_meios_pagamento_mensal.json   (a mao)
                                     └──▶ docs/explorar.html
```

**Etapa E.** Roda depois da Etapa 3 e antes da 4. Perfila as tres camadas (bruto wide da
Olinda, tidy, de-para das formas) medindo tipos, nulos, chave primaria, joins e lacunas, e
publica isso ao lado de uma pauta analitica curada. Especificacao completa no repositorio
`controle-global`, em `prompts/modelo-pagina-exploracao.md`. **A Etapa E so adiciona:** a
unica alteracao que ela fez em arquivo existente foi o link "Explorar dados" na navegacao do
`index.html`.

| Etapa | Nome | Código | Entrada → Saída | Status |
|-------|------|--------|-----------------|--------|
| 1 | Catálogo da fonte | `catalogo/fonte.md` | — → dicionário de dados | ✅ |
| 2 | Ingestão / coleta | `src/coleta/` | endpoint → JSON bruto | ✅ |
| 3 | Tratamento & modelagem | `src/tratamento/` | JSON bruto → CSV tidy | ✅ |
| 4 | Análise estatística | `src/analise/` | CSV tidy → métricas | ✅ |
| E | Exploração & pauta | `src/perfil/`, `docs/explorar.html` | bruto + tidy + auxiliares → perfil + pauta | ✅ |
| 5 | Publicação de dados | `src/publicacao/` | tidy + métricas → JSON do front | ✅ |
| 6 | Dashboard | `docs/` | JSON → site interativo | ✅ |
| 7 | Documentação & deploy | `README.md`, GitHub Pages | — → site no ar | 🟡 |

**Formato tidy (saída da Etapa 3):** colunas `ano_mes` (`YYYY-MM`), `forma_pagamento`,
`quantidade`, `valor`. Segue a anatomia comum do projeto — **dimensões em linha, medidas em
coluna**, com `ano_mes` sempre como primeira dimensão.

## 6. Convenções

- **Slug da fonte:** `meios_pagamento_mensal` — reutilizado em `src/`, `dados/` e `docs/dados/`.
- **Datas:** `AnoMes` normalizado para string `YYYY-MM`.
- **JSON do front:** sempre com bloco `meta` (fonte, url, gerado_em, unidades, período).
- **Unidades:** quantidade em milhares de transações; valor em R$ milhões.

## 7. Como referenciar as etapas nos prompts

- "Melhorar as métricas da **Etapa 4** (adicionar sazonalidade), atualizando a **Etapa 5**."
- "Redesenhar o dashboard da **Etapa 6** sem alterar o contrato de dados da **Etapa 5**."
- Sempre que uma mudança afetar o contrato da seção 5, avise para eu ajustar as etapas vizinhas.

## 8. Roadmap curto

- [ ] Etapa 4: sazonalidade, médias móveis, testes de tendência.
- [ ] Etapa 6: seletor de tema claro/escuro.
- [ ] Etapa 7: automação de atualização agendada e melhorias de acessibilidade.
