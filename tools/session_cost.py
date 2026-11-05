#!/usr/bin/env python3
"""Real token usage of a Claude Code session, per agent, read from the session transcripts.

Usage:
  python -I tools/session_cost.py                                  the most recent session of this repository
  python -I tools/session_cost.py <session> [--since HH:MM] [--words N] [--json FILE]

Sums, per agent (main agent and each subagent), every model call: input, cache write, cache read and output.
The number a subagent reports when it finishes is only its final context size, not what it consumed.
"Equivalent" is an estimate in input tokens with typical weights (cache read 0.1, cache write 1.25, output 5).
It is meant to compare runs, not to be a price. --since (UTC time in the transcript) trims the main agent so that
what the session did before the loop is left out. Only Claude Code writes these transcripts.
Importable: measure(session, since="", folder=None) -> {"agents": [...], "total": {...}}.
"""
import argparse, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = {"input": 1, "cache_write": 1.25, "cache_read": 0.1, "output": 5}


def transcripts_folder(root=ROOT):
    # Another Claude Code account may use another config folder (CLAUDE_CONFIG_DIR).
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root))


def latest_session(folder=None):
    folder = folder or transcripts_folder()
    files = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f"{folder}: no transcripts.")
    return files[-1].stem


def equivalent(a):
    return round(sum(a[k] * w for k, w in WEIGHTS.items()))


def read(path, since=""):
    """One entry per model call: the same message shows up on several lines, and the last one has the final usage."""
    calls, model = {}, ""
    with open(path, encoding="utf-8") as f:
        for ln in f:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            m = r.get("message") or {}
            if r.get("type") != "assistant" or not m.get("usage"):
                continue
            hhmm = (r.get("timestamp") or "")[11:16]
            if since and hhmm < since:
                continue
            calls[m.get("id") or r.get("uuid")] = m["usage"]
            model = m.get("model") or model
    a = {"calls": len(calls), "input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "model": model}
    context = []
    for u in calls.values():
        a["input"] += u.get("input_tokens", 0)
        a["cache_write"] += u.get("cache_creation_input_tokens", 0)
        a["cache_read"] += u.get("cache_read_input_tokens", 0)
        a["output"] += u.get("output_tokens", 0)
        context.append(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                       + u.get("cache_read_input_tokens", 0))
    a["context_start"] = context[0] if context else 0
    a["context_end"] = context[-1] if context else 0
    a["equivalent"] = equivalent(a)
    return a


def measure(session, since="", folder=None):
    folder = folder or transcripts_folder()
    main_file = folder / f"{session}.jsonl"
    if not main_file.exists():
        raise SystemExit(f"{main_file}: transcript not found.")
    agents = [dict(read(main_file, since), name="main agent", type="main")]
    for f in sorted((folder / session / "subagents").glob("*.jsonl")):
        meta = f.with_suffix(".meta.json")
        info = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
        agents.append(dict(read(f), name=info.get("description") or f.stem, type=info.get("agentType", "")))
    total = {k: sum(a[k] for a in agents) for k in ("calls", "input", "cache_write", "cache_read", "output", "equivalent")}
    return {"session": session, "since": since, "agents": agents, "total": total}


def main():
    ap = argparse.ArgumentParser(description="Real token usage of a session, per agent.")
    ap.add_argument("session", nargs="?")
    ap.add_argument("--since", default="", help="HH:MM UTC: trims the main agent before this time")
    ap.add_argument("--words", type=int, help="source words processed, for the cost per word")
    ap.add_argument("--json", type=Path, help="write the result to this file")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    r = measure(a.session or latest_session(), a.since)
    print(f"Session {r['session']}" + (f", since {a.since} UTC" if a.since else ""))
    print(f"{'agent':38} {'calls':>5} {'cache rd':>11} {'cache wr':>9} {'output':>8} {'ctx 1st':>8} {'ctx last':>8} {'equiv.':>10}")
    for x in r["agents"]:
        print(f"{x['name'][:38]:38} {x['calls']:5} {x['cache_read']:11,} {x['cache_write']:9,} {x['output']:8,} "
              f"{x['context_start']:8,} {x['context_end']:8,} {x['equivalent']:10,}")
    t = r["total"]
    print(f"{'TOTAL':38} {t['calls']:5} {t['cache_read']:11,} {t['cache_write']:9,} {t['output']:8,} {'':8} {'':8} {t['equivalent']:10,}")
    if a.words:
        print(f"Equivalent tokens per source word: {t['equivalent'] / a.words:,.0f}")
    if a.json:
        a.json.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
