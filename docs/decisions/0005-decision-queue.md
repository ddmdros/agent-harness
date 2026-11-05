# 5. Decisions made by inference go to an approval queue

Status: accepted

## Context
Agents make many small choices nobody asked for: a file format, a name, a limit, what to leave out. In a
conversation, they vanish in the scrollback. With the human away part of the time, they are never reviewed and
become rules without anyone noticing.

## Decision
A *decision by inference* (a choice the agent made without being told, and that outlives the session) is recorded
at once with `tools/pending.py decision`, with the reason, where it applies and the alternatives left out. A
question that did not block the work goes to a second queue, with how to resolve it. At the end of the session,
the agent lists what it recorded and asks for approval. The human answers by id (`D003 ok`, `D004 change: ...`),
and whatever is refused or changed is undone in the same session. Workers do not write to the queue: they list
their decisions in their final answer, and the main agent records them.

## Consequences
- Writes go through a single script, with a file lock and an atomic replace, so parallel sessions do not lose
  entries. The queue folder is a `script` zone.
- The queue is not a source of rules: an approved decision that becomes a rule goes to a rules file.
