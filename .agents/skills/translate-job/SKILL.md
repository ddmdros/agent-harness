---
name: translate-job
description: Translate a job of the demo project with one drafter and two reviewers in parallel, then merge their output by a fixed rule and show the human only what needs a decision. Use when the user asks to translate a job under projects/*/jobs/.
---

# translate-job

Orchestrates a small multi-agent loop over `projects/<project>/jobs/<job>/`.

1. Read `projects/<project>/AGENTS.md`, the job's `source/strings.json` and the project glossary.
2. Reserve the output path of each worker:
   `python -I tools/runs.py name projects/<project>/jobs/<job>/wip <worker>` for `drafter`,
   `mechanics-reviewer` and `style-reviewer`.
3. Run the `drafter` worker with `OUTPUT=<its path>`. Wait for it.
4. Run `mechanics-reviewer` and `style-reviewer` **in parallel**, each with its own `OUTPUT`.
5. Merge: `python -I tools/merge_reviews.py projects/<project>/jobs/<job>/wip`.
6. Show the human only the segments with `warnings` in `wip/merged.json`, with the alternatives.
7. After the human decides, write the deliverable to `output/`.
8. Record the decisions you made by inference (`tools/pending.py decision`), including the ones the workers listed.

If the loop runs unattended, create `.scratch/unattended` first and delete it at the end.
Measure the cost at the end: `python -I tools/session_cost.py --words <source words>`.
