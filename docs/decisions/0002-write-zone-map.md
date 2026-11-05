# 2. Um mapa de zonas de escrita: vale a última zona, o resto é bloqueado

Status: aceita

## Contexto
As regras de proteção tinham virado listas separadas dentro de cada trava: referências protegidas, bancos
protegidos, pastas geradas. Uma pasta nova exigia mexer em código em vários lugares, e nada dizia ao agente
onde um arquivo novo *podia* ficar.

## Decisão
Um mapa em TOML (`.agents/tree.toml`) dá a cada caminho um de seis modos:

| Modo | Arquivo novo | Arquivo existente |
|---|---|---|
| `free` | segue | segue |
| `deliver` | segue | pede confirmação |
| `append` | segue | nega |
| `ask` | pede confirmação | pede confirmação |
| `script` | só a ferramenta de `by` | só a ferramenta de `by` |
| `blocked` | nega | nega |

Os globs são lidos em ordem e vale a **última** zona que casa, então o mapa vai da regra geral para a exceção
(`references/**` bloqueado e, depois, `references/glossary.csv` com confirmação). O que nenhuma zona cobre cai
no `default`, que é `blocked`: pasta nova exige zona nova, aprovada por um humano.

## Consequências
- A trava, o `tools/tree.py check` (que lista o que existe no disco fora do mapa) e os testes leem o mesmo arquivo.
- O modo `append` protege registros e saídas de worker contra os agentes sem nenhum código extra.
- O modo `script` dá a um gerador a posse da sua saída: `.claude/skills/**` só é escrito pelo `sync_adapters.py`.
