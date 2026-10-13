---
name: meios-pagamento-bcb
description: Analisa a série mensal oficial do Banco Central sobre meios de pagamento no Brasil — Pix, TED, boleto, cheque, DOC e TEC, em quantidade de transações e valor movimentado, de 2002 até o mês mais recente. Baixa o dado atualizado, corrige as armadilhas da fonte (unidades diferentes, zeros que significam "não existia", valores nominais) e situa os resultados nos marcos históricos (lançamento do Pix, fim do DOC, Pix Automático...). Use sempre que o usuário perguntar sobre uso, crescimento, participação, ticket médio, sazonalidade ou substituição entre Pix, TED, boleto, cheque, DOC ou TEC; quiser gráficos, relatórios ou números sobre pagamentos e transferências no Brasil; ou citar o painel "Meios de Pagamento no Brasil", mesmo sem mencionar o Banco Central.
---

# Meios de pagamento no Brasil (BCB)

Esta skill acompanha o painel **Meios de Pagamento no Brasil**
(https://meiospagamento.gfvdata.com/). A fonte é a estatística mensal de
meios de pagamento do Banco Central do Brasil, que é aberta e gratuita.

O dado é simples: uma linha por mês e por forma de pagamento, com quantidade e valor. Os
erros de análise vêm de três detalhes que não aparecem na tabela. O papel desta skill é
evitar esses erros e devolver ao usuário uma análise em que ele possa confiar.

## 1. Carregar os dados

Rode o script incluído. Ele busca a série completa, converte para o formato longo e
acrescenta colunas auxiliares:

```bash
python scripts/carregar_dados.py            # grava meios_pagamento.csv
python scripts/carregar_dados.py --ipca     # + valor_real deflacionado pelo IPCA
```

O script tenta a API do Banco Central e, se ela falhar, o CSV publicado no site do
projeto. Ao terminar, imprime o período, a janela de existência de cada forma e um retrato
do último mês. Leia esse resumo antes de analisar: ele já responde muitas perguntas simples.

**Se a rede estiver bloqueada** (comum em ambientes isolados), o script sai com código 2.
Nesse caso:
1. Se você tiver uma ferramenta de busca na web, tente abrir
   `https://meiospagamento.gfvdata.com/dados/meios_pagamento_mensal.csv`
   e salvar o conteúdo num arquivo.
2. Se não der, peça ao usuário para baixar esse CSV pelo navegador e anexá-lo à conversa.
3. Depois rode `python scripts/carregar_dados.py --arquivo <caminho>`. O script aceita
   tanto o CSV do projeto quanto o CSV ou JSON exportado direto do portal do BCB.

Não invente nem "lembre" números da série. Se não conseguir carregar os dados, diga isso
ao usuário. Números de memória ficam desatualizados em semanas.

### Colunas do arquivo gerado

| Coluna | Significado |
|---|---|
| `ano_mes` | `AAAA-MM` |
| `forma_pagamento` | Pix, TED, TEC, Cheque, Boleto, DOC |
| `quantidade` | **milhares** de transações no mês |
| `valor` | **R$ milhões** movimentados no mês, em valores nominais |
| `ativa` | `True` se a forma existia na série naquele mês |
| `ticket_medio_reais` | valor médio por transação, já convertido para **reais** |
| `valor_real` | só com `--ipca`: R$ milhões a preços do último mês com IPCA |

## 2. As armadilhas (leia antes de calcular qualquer coisa)

1. **Unidades diferentes.** A quantidade está em milhares e o valor em milhões de reais.
   Por isso o ticket médio é `valor / quantidade × 1000`, e não `valor / quantidade`.
   Errar isso dá um número mil vezes menor que ainda parece plausível. Use a coluna
   `ticket_medio_reais`. Ao mostrar números, converta para uma unidade legível ("8,1
   bilhões de transações", "R$ 3,7 trilhões") e diga qual unidade está usando.

2. **Zero nem sempre é zero.** A fonte grava ausência como 0. Pix antes de nov/2020, DOC e
   TEC depois de fev/2024, e cheque e boleto antes de entrarem na estatística aparecem
   como zero, mas a forma simplesmente não existia ali. Média, mediana, mínimo, desvio,
   taxa de crescimento e "queda de 100%" precisam ser calculados **só com `ativa == True`**.
   Ao comparar períodos, deixe claro em que janela cada forma existe.

3. **Valores nominais.** A série cobre mais de 20 anos sem correção pela inflação.
   Qualquer comparação de valor entre anos distantes ("o cheque caiu X%", "o TED cresceu
   Y vezes") deve usar `--ipca` e mostrar o número real ao lado do nominal. Quantidade não
   precisa de deflação.

4. **Não é o mercado inteiro.** Cartão de crédito, cartão de débito e dinheiro em espécie
   **não estão** nesta série, que cobre transferências e liquidação. Fale em "participação
   entre Pix, TED, boleto, cheque, DOC e TEC", nunca em "participação nos pagamentos do
   Brasil". Se o usuário perguntar sobre cartão, diga que a série não cobre cartões e que
   eles estão nas estatísticas trimestrais de pagamentos de varejo do BCB.

5. **Os meses recentes podem ser revisados.** O BCB às vezes ajusta números já
   publicados. Diferenças pequenas entre o seu resultado e outra fonte podem vir daí.
   Informe sempre o último mês disponível usado na análise.

Mais detalhes e exemplos em `references/armadilhas.md`.

## 3. Como analisar

Escolha a medida certa para a pergunta. Quantidade e valor contam histórias opostas: o
Pix lidera com folga em número de transações, mas o TED ainda movimenta mais dinheiro,
porque cada TED vale, em média, mais de cem vezes um Pix. Quando a pergunta for
"quem está ganhando" ou "o Pix substituiu X?", mostre **as duas medidas** e o ticket
médio. Mostrar só uma delas leva o leitor a uma conclusão errada.

Receitas comuns (pandas):

```python
import pandas as pd
df = pd.read_csv("meios_pagamento.csv", parse_dates=["ano_mes"])
ativo = df[df["ativa"]]

# Participação no mês (só formas ativas)
part = ativo.pivot_table(index="ano_mes", columns="forma_pagamento", values="valor")
part = part.div(part.sum(axis=1), axis=0)

# Crescimento sobre o mesmo mês do ano anterior (evita a sazonalidade)
serie = ativo.pivot_table(index="ano_mes", columns="forma_pagamento", values="quantidade")
yoy = serie.pct_change(12, fill_method=None)

# Soma anual: só para anos completos. Avise se o ano corrente está parcial.
anual = ativo.assign(ano=ativo["ano_mes"].dt.year).groupby(["ano", "forma_pagamento"])[["quantidade", "valor"]].sum()
```

- **Sazonalidade é forte**: dezembro (13º salário, festas) e março (IPVA/IPTU no boleto)
  têm picos. Compare um mês com o mesmo mês do ano anterior, nunca com o mês anterior,
  a menos que o usuário peça.
- **Ano corrente parcial**: não compare a soma de um ano incompleto com anos fechados.
  Use os meses equivalentes (jan–ago contra jan–ago) ou o acumulado de 12 meses.
- **Para explicar mudanças**, consulte `references/eventos.md`, que lista os marcos
  catalogados por forma (lançamento do Pix, fim do DOC/TEC, boleto D+0, Pix Automático...).
  Cite o evento só quando a data bater com o que o dado mostra. Coincidência não prova
  causa, então use "coincide com", não "foi causado por".
- `references/achados.md` traz leituras já verificadas no projeto (Pix contra TED, quem o
  Pix canibalizou, o declínio do cheque). Use como ponto de partida, mas **recalcule os
  números com o dado atual** antes de citá-los.

## 4. Gráficos

Se for fazer gráficos, use as cores do painel para manter a identidade visual:

| Forma | Cor |
|---|---|
| Pix | `#2a78d6` |
| TED | `#eb6834` |
| Boleto | `#1baf7a` |
| Cheque | `#eda100` |
| TEC | `#e87ba4` |
| DOC | `#4a3aa7` |

- Para a evolução de Pix e cheque no mesmo gráfico, use escala logarítmica. Eles diferem
  em três ordens de grandeza, e em escala linear o cheque some.
- Para participação, use área empilhada 100%. Para ticket médio, use barras ou linhas,
  nunca empilhadas, porque é uma razão e não um total.
- Corte cada série na sua janela ativa. Uma linha do Pix colada no zero de 2002 a 2020
  não informa nada e achata o resto do gráfico.
- Marque eventos relevantes como linhas verticais com rótulo curto.

## 5. Como entregar a resposta

- Comece pela resposta direta, em uma ou duas frases, com o número principal.
- Diga o período e o último mês usado ("dados até ago/2026").
- Diga a unidade e se o valor é nominal ou corrigido pelo IPCA.
- Quando a pergunta tocar alguma das armadilhas, mencione-a numa linha, sem sermão.
- Termine com a fonte: *Fonte: Banco Central do Brasil — Estatísticas de Meios de
  Pagamento (dados abertos). Tratamento: painel Meios de Pagamento no Brasil.*
- Escreva no idioma do usuário (a fonte e os nomes das formas ficam em português).
