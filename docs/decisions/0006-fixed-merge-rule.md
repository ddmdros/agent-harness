# 6. Uma regra fixa de junção no lugar de um juiz LLM

Status: aceita

## Contexto
O piloto do loop de tradução tinha um tradutor, dois revisores (um de correção verificável, outro de estilo) e
um juiz LLM para conciliá-los. O juiz aplicou 6 das 6 propostas que viu: custava tokens e tempo e não
acrescentava informação.

## Decisão
A junção é código (`tools/merge_reviews.py`). Os revisores vêm em ordem de prioridade, com a correção antes do
estilo. O `change` de maior prioridade vira o texto, e toda outra proposta vira alternativa. O `escalate` e as
dúvidas do tradutor viram avisos. O humano só vê os segmentos com aviso.

## Consequências
- É determinística, tem testes de unidade e não custa nada para rodar. Quando a regra está errada, a correção é
  uma mudança de código, não um prompt novo.
- Cada revisor julga um eixo e é instruído a não julgar o outro, o que deixa os conflitos raros e visíveis.
- Cada worker grava uma vez no seu arquivo de rodada (`tools/runs.py`), e a junção sempre lê a rodada mais nova.
