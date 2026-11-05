# 5. Decisions by inference go to a queue for approval

Status: accepted

## Context
Agents make many small choices nobody asked for: a file format, a name, a threshold, what to leave out. In a
chat these scroll away. When the human is away part of the time, they are never reviewed, and they quietly
become the rules.

## Decision
A *decision by inference* (a choice the agent made without being told, that outlives the session) is recorded
at once with `tools/pending.py decision`, together with why it was made, where it applies and the alternatives
that were left out. A question that did not block the work goes to a second queue with how to resolve it. At the
end of a session the agent lists what it recorded and asks for approval. The human answers by id (`D003 ok`,
`D004 change: ...`), and rejected or changed decisions are undone in that same session. Workers do not write to
the queue: they list their decisions in their final answer, and the main agent records them.

## Consequences
- Writes go through one script with a lock file and an atomic replace, so parallel sessions never lose entries.
  The queue folder is a `script` zone.
- The queue is not a source of rules: an approved decision that becomes a rule moves to a rules file.
