# 1. Hooks enforce, prompts inform

Status: accepted

## Context
The first version of the harness relied on instruction files and the tool's own permission rules. Two problems
showed up in real work. Agents left throwaway files at the repository root (`out.txt`, `diff_output.txt`,
`_tmp_extract/` folders with loose scripts), even though the rules said where scratch files go. And the
permission rules that protected the reference folders only covered the Edit and Write tools: an `rm`, a `cp` or a
short Python script in the terminal went straight through.

## Decision
Every rule that protects a file is enforced by a PreToolUse hook, in code, before the tool runs. Prompts still
explain the rules, because an agent that knows why makes fewer mistakes, but the prompt is no longer the
protection. Every denial gives the reason and what to do (`tools/tree.py where <path>`), so the agent can recover.

## Consequences
- The rules are testable: `tests/test_tree_guard.py` has 60 cases, from a plain write to a Python heredoc.
- The terminal guard is best effort over the command text; that is why its limits are documented and it errs on
  the safe side.
- Loosening a guard is watched too: `tools/guards/**` is an `ask` zone.
