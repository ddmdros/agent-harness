# 1. Hooks enforce, prompts inform

Status: accepted

## Context
The first version of the harness relied on instruction files and on the tool's own permission rules. Two
problems showed up in real work. Agents kept leaving throwaway files at the repository root (`out.txt`,
`diff_output.txt`, `_tmp_extract/` folders with ad-hoc scripts) even though the rules said where scratch files
go. And the permission rules that protected the reference folders covered only the Edit and Write tools: a
`rm`, a `cp` or a short Python script in the shell went straight through.

## Decision
Every rule that protects a file is enforced by a PreToolUse hook, in code, before the tool runs. Prompts still
explain the rules, because an agent that knows why makes fewer denied attempts, but the prompt is no longer the
safeguard. Each denial says why and how to proceed (`tools/tree.py where <path>`), so the agent can recover.

## Consequences
- Rules are testable: `tests/test_tree_guard.py` has 60 cases, from plain writes to Python heredocs.
- The shell guard is best effort over command text, so its limits are documented and it errs on the safe side.
- Loosening a guard is itself guarded: `tools/guards/**` is an `ask` zone.
