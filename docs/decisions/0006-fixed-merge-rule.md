# 6. A fixed merge rule instead of an LLM judge

Status: accepted

## Context
The pilot of the translation loop had a translator, two reviewers (one for verifiable correctness, one for style)
and an LLM judge to reconcile them. The judge applied 6 of the 6 proposals it saw: it cost tokens and time and
added no information.

## Decision
The merge is code (`tools/merge_reviews.py`). Reviewers come in priority order, correctness before style. The
highest-priority `change` becomes the text, and every other proposal becomes an alternative. An `escalate` and the
translator's questions become warnings. The human only sees the segments with a warning.

## Consequences
- It is deterministic, has unit tests and costs nothing to run. When the rule is wrong, the fix is a code change,
  not a new prompt.
- Each reviewer judges one axis and is told not to judge the other, which keeps conflicts rare and visible.
- Each worker writes once to its run file (`tools/runs.py`), and the merge always reads the newest run.
