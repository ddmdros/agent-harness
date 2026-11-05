# 5. Decisões por inferência vão para uma fila de aprovação

Status: aceita

## Contexto
Os agentes fazem muitas escolhas pequenas que ninguém pediu: um formato de arquivo, um nome, um limite, o que
deixar de fora. Numa conversa, elas somem na rolagem. Com o humano ausente parte do tempo, nunca são revisadas
e viram regra sem ninguém ver.

## Decisão
Uma *decisão por inferência* (escolha que o agente fez sem ninguém dizer e que fica depois da sessão) é anotada
na hora com `tools/pending.py decision`, com o porquê, onde se aplica e as alternativas descartadas. Uma dúvida
que não bloqueou o trabalho vai para uma segunda fila, com o jeito de resolver. No fim da sessão, o agente lista
o que anotou e pede aprovação. O humano responde pelo id (`D003 ok`, `D004 change: ...`), e o que for recusado ou
mudado é desfeito na mesma sessão. Os workers não escrevem na fila: listam as decisões na resposta final, e o
agente principal as anota.

## Consequências
- A gravação passa por um único script, com trava de arquivo e troca atômica, então sessões paralelas não
  perdem anotações. A pasta da fila é uma zona `script`.
- A fila não é fonte de regra: a decisão aprovada que vira regra vai para um arquivo de regras.
