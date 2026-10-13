# Armadilhas da fonte, em detalhe

## Formato original e cobertura

A API Olinda do BCB (serviço `MPV_DadosAbertos`, recurso `MeiosdePagamentosMensalDA`)
entrega uma linha por mês, do mais recente para o mais antigo. Cada forma ocupa um par de
colunas (`quantidadePix`/`valorPix` etc.). O script converte isso para uma linha por mês e
por forma. Se o BCB acrescentar uma forma nova, ela aparece como um par de colunas novo, e
o script só a reconhece se ela estiver em `FORMAS`.

A série é mensal e nacional, sem recorte por estado ou município, e não tem lacunas de mês
desde abr/2002.

| Forma | Entra na série | Sai da série | Observação |
|---|---|---|---|
| TED | abr/2002 | — | única que cobre a série inteira |
| DOC | fev/2004 | fev/2024 | encerrado pelos bancos em 29/02/2024 |
| Cheque | mai/2004 | — | o cheque é anterior a 2004: é a entrada na estatística, não a criação do instrumento |
| Boleto | fev/2005 | — | idem: entrada na estatística |
| TEC | abr/2007 | fev/2024 | encerrada junto com o DOC |
| Pix | nov/2020 | — | lançamento do Pix |

O script calcula essas janelas a partir do dado (primeiro e último mês com quantidade > 0)
e grava o resultado na coluna `ativa`. Prefira o resumo impresso à tabela acima se elas
divergirem, porque o dado é a fonte da verdade.

## Zero estrutural

Exemplo do erro: "a média mensal de transações Pix desde 2002 é X". O resultado divide por
cerca de 290 meses um total que só tem cerca de 70 parcelas. O mesmo acontece com:
- mínimo histórico, que vira 0;
- desvio-padrão e coeficiente de variação, que ficam inflados;
- taxa de crescimento a partir de zero, que é infinita ou indefinida;
- "o DOC caiu 100%". Correto: o DOC foi encerrado em fev/2024.

Filtre com `ativa == True` antes de qualquer estatística.

## Ticket médio

`quantidade` está em milhares e `valor` em R$ milhões, logo:

```
ticket (R$) = (valor × 1.000.000) / (quantidade × 1.000) = valor / quantidade × 1000
```

Para ter uma ideia da ordem de grandeza (meados de 2026): o TED fica na casa das dezenas
de milhares de reais por transação, o cheque em alguns milhares, o boleto em torno de
R$ 1,7 mil e o Pix em algumas centenas de reais. Se o seu ticket do Pix deu menos de
R$ 1, você esqueceu o × 1000.

## Deflação

`--ipca` usa a série 433 do SGS/BCB (IPCA, variação mensal %), monta um índice acumulado e
leva cada valor a preços do último mês disponível tanto no IPCA quanto na série de
pagamentos. O IPCA sai por volta do dia 10 do mês seguinte, então o último mês de
pagamentos pode ficar sem valor real. Nesse caso `valor_real` fica vazio nessas linhas.
Avise o usuário.

Ao apresentar, use "R$ X bilhões a preços de <mês/ano>".

## Cobertura temática

Estão na série: Pix, TED, TEC, DOC, cheque e boleto. Não estão: cartão de crédito,
cartão de débito, cartão pré-pago, dinheiro em espécie, débito automático e transferências
entre contas do mesmo banco que não passam pelos sistemas interbancários.

Frases que devem ser evitadas:
- "o Pix já é X% de todos os pagamentos do Brasil";
- "os brasileiros pararam de usar cartão".

Frase correta: "entre os instrumentos desta série, o Pix responde por X% das transações".

## Revisões

Comparando coletas feitas em datas diferentes, vimos o BCB ajustar números de meses já
publicados, com diferenças pequenas, na casa de milésimos de por cento. Na prática isso não
muda conclusões. Mas, se o usuário comparar com um número de outra fonte e houver diferença
pequena, a revisão é uma explicação provável.
