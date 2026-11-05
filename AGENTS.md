# Agent rules (agent-harness)

This file is the single source of rules for **any** agent working here: Claude Code, Antigravity or another tool.
`CLAUDE.md` only imports it (`@AGENTS.md`). Paths are relative to the repository root.

## Where things live

| What | Source (edit here) | Generated copy (do not edit) |
|---|---|---|
| Rules | `AGENTS.md` in each folder | `CLAUDE.md` next to it (`@AGENTS.md`) |
| Skills | `.agents/skills/<name>/SKILL.md` | `.claude/skills/` |
| Worker prompts (subagents) | `.agents/workers/<name>.md` | `.claude/agents/` |
| Where each agent may write | `.agents/tree.toml` | — (the guard reads it) |
| Guards (hooks) | `tools/guards/*.py` | `.claude/settings.json` and `.agents/hooks.json` only call `tools/guards/pre_tool_use.py` |

After changing a skill or a worker, run `python -I tools/sync_adapters.py`.

## Write-zone map

Every write obeys `.agents/tree.toml`. Each zone is `free`, `deliver`, `append`, `ask`, `script` or `blocked`;
anything outside the map is blocked.
- Before creating a file or folder in a new place: `python -I tools/tree.py where <path>`.
- Need a folder the map does not cover? Propose the zone to the human; the map only changes with their approval.
- A denied write is an answer, not an obstacle: do not look for another route to the same file.

## Decisions by inference and open questions

1. A **decision by inference** is any choice you made without being told, that outlives the session (a format, a
   name, a place, a rule, what you left out). Record it at once:
   `python -I tools/pending.py decision "<decision>" --why "<reason>" --where "<file>" --alternatives "<what was left out>"`
2. A **question** only the human or a test can settle, that did not block you:
   `python -I tools/pending.py question "<question>" --how "<how to resolve it>"`
3. At the end of the session, list what you recorded (`python -I tools/pending.py list --session <id>`), one line
   each with its id, and ask for approval. Record the answer with `python -I tools/pending.py answer <id> ok|no|change "<text>"`.
4. **Workers** (subagents) do not write to the queue: they list their decisions in their final answer, and the
   main agent records them.

## Unattended mode

When `HARNESS_UNATTENDED=1` or `.scratch/unattended` exists, nobody is there to answer a confirmation prompt, so the
guard turns every `ask` into a `deny`. Record the blocked write as a question and continue without it.

## Workers and runs

Each worker writes its output once, to the path the orchestrator gives it (`OUTPUT`), created by
`python -I tools/runs.py name <wip folder> <worker>`. Runs are append-only: never overwrite one.
`python -I tools/merge_reviews.py <wip>` merges the drafter with the reviewers by a fixed rule.

## Git

- Commit with explicit paths (`git add <path>`), never `git add -A` blindly.
- Never `--no-verify` and never `git add -f`: the guard denies both.
- Push asks for confirmation and only goes to a remote whose visibility is in `[git].allowed_visibility`.
