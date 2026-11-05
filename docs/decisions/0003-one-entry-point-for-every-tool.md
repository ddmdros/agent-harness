# 3. One entry point for every agent tool

Status: accepted

## Context
The same project is worked on with Claude Code and with Google Antigravity. Both offer PreToolUse hooks, with
different event shapes and different answer protocols. Claude Code denies with exit code 2, while Antigravity
expects JSON with `deny` or `force_ask`. Keeping two sets of guards would let the rules drift apart.

## Decision
Both hook configurations call the same script, `tools/guards/pre_tool_use.py`. `event.py` turns each tool's event
into one neutral shape (`kind`, `path`, `command`, `cwd`) and renders the decision back in each protocol. Guards
only see the neutral event. Skills and worker prompts follow the same idea: the source lives in `.agents/`, and
`sync_adapters.py` generates the `.claude/` copies, which CI checks.

## Consequences
- A new tool needs a mapping in `normalize()` and an output in `render()`, not new guards.
- Antigravity's "Always Allow" would skip an `ask`, so the adapter emits `force_ask`.
- Every decision is logged in one format, whatever tool made the call.
