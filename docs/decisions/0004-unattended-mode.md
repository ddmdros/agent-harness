# 4. Unattended mode turns "ask" into "deny"

Status: accepted

## Context
The translation loop runs a drafter and reviewers without a human watching. Any `ask` decision opened a
confirmation prompt that nobody answered, and the whole loop stalled until someone came back.

## Decision
When `HARNESS_UNATTENDED=1` is set, or the orchestrator creates `.scratch/unattended`, the entry point turns every
`ask` into a `deny`. The reason tells the agent not to look for another route, to record the blocked write as a
question (`tools/pending.py question`), and to continue without it.

## Consequences
- Unattended mode can only make the guards stricter, so any agent may switch it on.
- Work that needed approval is not lost. It is waiting in the queue when the human returns.
