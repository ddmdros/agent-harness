# 3. Um ponto de entrada para todas as ferramentas

Status: aceita

## Contexto
O mesmo projeto é trabalhado no Claude Code e no Google Antigravity. Os dois oferecem hooks PreToolUse, com
eventos em formatos diferentes e protocolos de resposta diferentes. O Claude Code nega com código de saída 2, e
o Antigravity espera um JSON com `deny` ou `force_ask`. Manter dois conjuntos de travas deixaria as regras
divergirem.

## Decisão
As duas configurações de hook chamam o mesmo script, `tools/guards/pre_tool_use.py`. O `event.py` transforma o
evento de cada ferramenta num formato neutro (`kind`, `path`, `command`, `cwd`) e devolve a decisão no protocolo
de cada uma. As travas só veem o evento neutro. Skills e prompts dos workers seguem a mesma ideia: a fonte mora
em `.agents/`, e o `sync_adapters.py` gera as cópias de `.claude/`, que o CI confere.

## Consequências
- Uma ferramenta nova pede um mapeamento em `normalize()` e uma saída em `render()`, não travas novas.
- O «Always Allow» do Antigravity pularia um `ask`; por isso o adaptador emite `force_ask`.
- Toda decisão é registrada num formato só, venha da ferramenta que vier.
