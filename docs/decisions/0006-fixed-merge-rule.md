# 6. A fixed merge rule instead of an LLM judge

Status: accepted

## Context
The pilot of the translation loop had a drafter, two reviewers (one for verifiable correctness, one for style)
and an LLM judge to reconcile them. The judge applied 6 of the 6 proposals it saw. It cost tokens and time and
added no information.

## Decision
The merge is code (`tools/merge_reviews.py`). Reviewers are listed in priority order, with correctness before
style. The highest-priority `change` becomes the text, and every other proposal becomes an alternative.
`escalate` and the drafter's open questions become warnings. The human sees only the segments with warnings.

## Consequences
- Deterministic, unit-tested and free to run. When the rule is wrong, the fix is a code change, not a new prompt.
- Each reviewer judges one axis and is told not to judge the other, which keeps conflicts rare and visible.
- Each worker writes once to its own run file (`tools/runs.py`), and the merge always reads the latest run.
