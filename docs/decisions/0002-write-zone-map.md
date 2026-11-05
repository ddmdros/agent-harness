# 2. One write-zone map, last match wins, default blocked

Status: accepted

## Context
Protection rules had grown as separate lists inside each guard: protected references, protected databases,
generated folders. Adding a folder meant editing code in several places, and nothing told an agent where a new
file *could* go.

## Decision
One TOML map (`.agents/tree.toml`) assigns each path one of six modes:

| Mode | New file | Existing file |
|---|---|---|
| `free` | allow | allow |
| `deliver` | allow | ask |
| `append` | allow | deny |
| `ask` | ask | ask |
| `script` | only the tool in `by` | only the tool in `by` |
| `blocked` | deny | deny |

Globs are matched in order and the **last** match wins, so the map reads from the general rule to the exception
(`references/**` blocked, then `references/glossary.csv` ask). Anything no zone covers falls into `default`,
which is `blocked`: a new folder requires a new zone, approved by a human.

## Consequences
- The guard, `tools/tree.py check` (which lists files on disk outside the map) and the tests read the same file.
- `append` makes logs and worker output tamper-proof for agents without any extra code.
- `script` zones let a generator own its output: `.claude/skills/**` can only be written by `sync_adapters.py`.
