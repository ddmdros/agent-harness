# 1. Hooks garantem, prompts explicam

Status: aceita

## Contexto
A primeira versão do harness dependia dos arquivos de instrução e das regras de permissão da própria
ferramenta. Dois problemas apareceram no trabalho real. Os agentes deixavam arquivos descartáveis na raiz do
repositório (`out.txt`, `diff_output.txt`, pastas `_tmp_extract/` com scripts avulsos), mesmo com a regra
dizendo onde ficam os rascunhos. E as regras de permissão que protegiam as pastas de referência só cobriam as
ferramentas Edit e Write: um `rm`, um `cp` ou um script Python curto no terminal passavam direto.

## Decisão
Toda regra que protege um arquivo é garantida por um hook PreToolUse, em código, antes de a ferramenta rodar.
Os prompts continuam explicando as regras, porque o agente que sabe o porquê erra menos, mas o prompt deixou de
ser a proteção. Cada negação diz o motivo e o que fazer (`tools/tree.py where <caminho>`), para o agente se
recuperar.

## Consequências
- As regras são testáveis: `tests/test_tree_guard.py` tem 60 casos, da escrita simples ao heredoc em Python.
- A trava do terminal é melhor esforço sobre o texto do comando; por isso os limites estão documentados e ela
  erra para o lado seguro.
- Afrouxar uma trava também é vigiado: `tools/guards/**` é uma zona `ask`.
