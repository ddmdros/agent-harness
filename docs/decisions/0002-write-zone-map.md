# 2. A write-zone map: the last zone wins, everything else is blocked

Status: accepted

## Context
The protection rules had turned into separate lists inside each guard: protected references, protected
databases, generated folders. A new folder meant changing code in several places, and nothing told the agent
where a new file *could* go.

## Decision
A TOML map (`.agents/tree.toml`) gives every path one of six modes:

| Mode | New file | Existing file |
|---|---|---|
| `free` | allow | allow |
| `deliver` | allow | ask |
| `append` | allow | deny |
| `ask` | ask | ask |
| `script` | only the tool in `by` | only the tool in `by` |
| `blocked` | deny | deny |

Globs are read in order and the **last** matching zone wins, so the map goes from the general rule to the
exception (`references/**` blocked, then `references/glossary.csv` with confirmation). Whatever no zone covers
falls to the `default`, which is `blocked`: a new folder needs a new zone, approved by a human.

## Consequences
- The guard, `tools/tree.py check` (which lists what exists on disk outside the map) and the tests read the same
  file.
- The `append` mode protects logs and worker output from the agents with no extra code.
- The `script` mode gives a generator ownership of its output: `.claude/skills/**` is written only by
  `sync_adapters.py`.
