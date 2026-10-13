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
├── .github/
│   ├── workflows/atualizacao-mensal.yml       # Etapa 7 — roda o pipeline todo dia 25
│   └── scripts/descartar_mudancas_cosmeticas.py  # Etapa 7 — evita commit só de carimbo
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
│   ├── index.html                      # Etapa 6 — painel (ex-v2; a v1 só existe no histórico do git)
│   ├── explorar.html                   # Etapa E — perfil + pauta analitica
│   ├── css/estilo-v2.css               # estilo do painel
│   ├── css/estilo.css                  # estilo do explorar.html
│   ├── js/app-v2.js                    # painel
│   ├── js/explorar.js
│   ├── skill/meios-pagamento-bcb.zip   # Etapa 5 (gerado) — skill do Claude para download
│   └── dados/
│       ├── meios_pagamento_mensal.json         # Etapa 5 (gerado)
│       ├── meios_pagamento_mensal.csv          # Etapa 5 (gerado) — cópia pública do tidy
│       ├── perfil_meios_pagamento_mensal.json  # Etapa E (gerado)
│       ├── eventos_meios_pagamento.json        # marcos da linha do tempo (a mao)
│       └── notas_meios_pagamento_mensal.json   # Etapa E (a mao, nunca sobrescrito)
├── skill/meios-pagamento-bcb/  # fonte da skill do Claude (SKILL.md, scripts/, references/)
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
| 7 | Documentação & deploy | `README.md`, `.github/workflows/`, GitHub Pages | — → site no ar, atualizado todo mês | ✅ |

**Etapa 7.** O GitHub Pages serve `docs/` da `main` (build legado, sem workflow de deploy).
A atualização é automática: [`.github/workflows/atualizacao-mensal.yml`](.github/workflows/atualizacao-mensal.yml)
roda `python run_pipeline.py` (Python 3.13) **no dia 25 de cada mês, 09:17 UTC**, e também
sob demanda (`workflow_dispatch`). O dia 25 vem do calendário do BCB: os instrumentos mensais
são atualizados "17 dias após o final do mês de referência" (portal de dados abertos,
conjunto `estatisticas-meios-pagamentos`), e a folga cobre fim de semana e feriado.

- **O que é commitado:** só os arquivos gerados — `docs/dados/meios_pagamento_mensal.{json,csv}`,
  `docs/dados/perfil_meios_pagamento_mensal.json`, `dados/processados/meios_pagamento_mensal.csv`
  e `docs/skill/meios-pagamento-bcb.zip`. `notas_*.json` e `eventos_*.json` são escritos à mão e
  ficam de fora; se o pipeline os alterar, o workflow descarta a alteração e emite um aviso.
- **Sem commit vazio:** `.github/scripts/descartar_mudancas_cosmeticas.py` restaura todo arquivo
  cuja diferença seja só carimbo de execução (`meta.gerado_em`, o alerta "coletado em …" do
  perfil, a data interna dos membros do zip, quebra de linha). Só sobra commit se o BCB trouxe
  mês novo ou revisou dado.
- **Disparo manual:** aba Actions → "Atualização mensal dos dados" → Run workflow, ou
  `gh workflow run atualizacao-mensal.yml`.
- **Cuidado:** em repositório público o GitHub desativa agendamentos após 60 dias sem atividade.
  Se a série parar de mudar, reative em Actions.

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
- [x] Etapa 7: automação de atualização agendada (`.github/workflows/atualizacao-mensal.yml`).
- [ ] Etapa 7: melhorias de acessibilidade.
