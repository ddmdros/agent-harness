# 4. Sem supervisão, «pedir» vira «negar»

Status: aceita

## Contexto
O loop de tradução roda um tradutor e revisores sem ninguém olhando. Toda decisão `ask` abria um pedido de
confirmação que ninguém respondia, e o loop inteiro parava até alguém voltar.

## Decisão
Com `HARNESS_UNATTENDED=1`, ou com o arquivo `.scratch/unattended` criado pelo orquestrador, o ponto de entrada
transforma todo `ask` em `deny`. O motivo diz ao agente para não procurar outro caminho, anotar a escrita
bloqueada como dúvida (`tools/pending.py question`) e seguir sem ela.

## Consequências
- O modo sem supervisão só deixa as travas mais estritas; por isso qualquer agente pode ligá-lo.
- O que precisava de aprovação não se perde: fica esperando na fila quando o humano volta.
