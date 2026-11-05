# 3. One entry point for every tool

Status: accepted

## Context
The same project is worked on in Claude Code and in Google Antigravity. Both offer PreToolUse hooks, with
different event formats and different response protocols. Claude Code denies with exit code 2, and Antigravity
expects a JSON with `deny` or `force_ask`. Keeping two sets of guards would let the rules drift apart.

## Decision
Both hook configurations call the same script, `tools/guards/pre_tool_use.py`. `event.py` turns each tool's event
into a neutral format (`kind`, `path`, `command`, `cwd`) and returns the decision in each tool's protocol. The
guards only see the neutral event. Skills and worker prompts follow the same idea: the source lives in
`.agents/`, and `sync_adapters.py` generates the copies in `.claude/`, which CI checks.

## Consequences
- A new tool needs a mapping in `normalize()` and an output in `render()`, not new guards.
- Antigravity's "Always Allow" would skip an `ask`; that is why the adapter emits `force_ask`.
- Every decision is logged in one format, whichever tool it came from.
