# 4. Unattended, "ask" becomes "deny"

Status: accepted

## Context
The translation loop runs a translator and reviewers with nobody watching. Every `ask` decision opened a
confirmation prompt that nobody answered, and the whole loop stopped until someone came back.

## Decision
With `HARNESS_UNATTENDED=1`, or with the `.scratch/unattended` file created by the orchestrator, the entry point
turns every `ask` into `deny`. The reason tells the agent not to look for another route, to record the blocked
write as a question (`tools/pending.py question`) and to carry on without it.

## Consequences
- Unattended mode only makes the guards stricter; that is why any agent may turn it on.
- What needed approval is not lost: it waits in the queue for when the human comes back.
