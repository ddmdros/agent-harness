#!/usr/bin/env python3
"""Merge a drafter's output with its reviewers' verdicts by a fixed rule, with no LLM judge.

Usage:
  python -I tools/merge_reviews.py <job wip/ folder> [--drafter NAME] [--reviewers A,B,...] [--out FILE]
      reads the latest run of each worker in <wip>/runs/ and writes <wip>/merged.json (or --out)

Why a rule and not a judge: in the pilot, an LLM judge applied 6 of the 6 reviewer proposals it saw. A judge that
always agrees adds cost and latency and no information, so the merge became deterministic code that is
cheap, testable and explainable. Ambiguity is not hidden: it becomes a warning for the human.

Rule, per segment (reviewers listed in priority order, highest first):
- `change` from the highest-priority reviewer that changed it: its proposal becomes the text;
  the drafter's text stays as an alternative.
- `change` from a lower-priority reviewer too: its proposal becomes an alternative and the card warns.
- `escalate`: the text does not change, the reason becomes a warning and any proposal an alternative.
- the drafter's `question` and `important` fields: warnings. The human decides.

Formats (JSON):
  drafter   {"segments": [{"id", "text", "alternatives": [{"text", "note"}], "question", "important"}]}
  reviewer  {"segments": [{"id", "verdict": "keep"|"change"|"escalate", "proposal", "reason"}]}
Importable: merge(draft_segment, [(reviewer, review_segment), ...]) -> dict.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script folder from sys.path
import runs  # noqa: E402

DRAFTER = "drafter"
REVIEWERS = ["mechanics-reviewer", "style-reviewer"]  # priority order: correctness beats style


def merge(draft, reviews):
    """Fixed-rule merge of one segment. `reviews`: [(reviewer name, its segment dict or None)], highest first."""
    original = draft["text"]
    text, origin, warnings = original, "drafter", []
    alts = [{"from": "drafter", "text": a["text"], "note": a.get("note", "")}
            for a in draft.get("alternatives") or [] if a.get("text")]
    changes = [(name, r) for name, r in reviews if r and r.get("verdict") == "change" and r.get("proposal")]
    if changes:
        winner, r = changes[0]
        text, origin = r["proposal"], winner
        for name, other in changes[1:]:
            alts.append({"from": name, "text": other["proposal"], "note": other.get("reason", "")})
        if len(changes) > 1:
            warnings.append(f"{len(changes)} reviewers changed this segment; {winner} wins by priority. "
                            "Check the other proposals.")
    if text != original:
        alts.insert(0, {"from": "drafter", "text": original, "note": draft.get("reasoning", "")})
    for name, r in reviews:
        if r and r.get("verdict") == "escalate":
            warnings.append(f"{name} asks for your decision: {r.get('reason', '')}")
            if r.get("proposal"):
                alts.append({"from": name, "text": r["proposal"], "note": r.get("reason", "")})
    for field in ("question", "important"):
        if draft.get(field):
            warnings.append(f"drafter: {draft[field]}")
    seen, unique = {text}, []
    for a in alts:
        if a["text"] not in seen:
            seen.add(a["text"])
            unique.append(a)
    return {"id": draft["id"], "text": text, "origin": origin, "alternatives": unique, "warnings": warnings}


def _by_id(data):
    items = data["segments"] if isinstance(data, dict) else data
    return {x["id"]: x for x in items}


def _load_latest(wip, worker, required=True):
    path = runs.latest(wip, worker)
    if path is None:
        if required:
            raise SystemExit(f"Missing output of worker {worker} in {runs.runs_folder(wip)}.")
        return {}
    return _by_id(json.loads(path.read_text(encoding="utf-8")))


def merge_job(wip, drafter=DRAFTER, reviewers=REVIEWERS):
    draft = _load_latest(wip, drafter)
    revs = [(r, _load_latest(wip, r, required=False)) for r in reviewers]
    segments = [merge(d, [(name, rev.get(sid)) for name, rev in revs]) for sid, d in draft.items()]
    changed = sum(s["origin"] != "drafter" for s in segments)
    flagged = sum(bool(s["warnings"]) for s in segments)
    return {"summary": {"segments": len(segments), "changed_by_review": changed, "need_human": flagged},
            "segments": segments}


def main():
    ap = argparse.ArgumentParser(description="Merge drafter output with reviewer verdicts by a fixed rule.")
    ap.add_argument("wip", type=Path)
    ap.add_argument("--drafter", default=DRAFTER)
    ap.add_argument("--reviewers", default=",".join(REVIEWERS), help="comma-separated, highest priority first")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    result = merge_job(a.wip, a.drafter, [r for r in a.reviewers.split(",") if r])
    out = a.out or a.wip / "merged.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    s = result["summary"]
    print(f"{out}: {s['segments']} segments, {s['changed_by_review']} changed by review, "
          f"{s['need_human']} need the human")


if __name__ == "__main__":
    main()
