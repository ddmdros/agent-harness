#!/usr/bin/env python3
"""Single entry point for every PreToolUse guard, for any agent tool.

Usage: called by the hook shells, never by hand:
  Claude Code  .claude/settings.json  -> python -I "$CLAUDE_PROJECT_DIR/tools/guards/pre_tool_use.py"
  Antigravity  .agents/hooks.json     -> python -I ../tools/guards/pre_tool_use.py
Reads the event from stdin, normalizes it (event.py), runs the guards and returns the strongest decision:
deny beats ask, which beats no opinion. Every write and shell command is then appended to the audit log.
New guard: a module with evaluate(ev) -> None | ("deny"|"ask", reason), added to GUARDS.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import event, git_guard, tree_guard  # noqa: E402

# tree_guard: every write obeys .agents/tree.toml; git_guard: commit, push and repository visibility.
GUARDS = [tree_guard, git_guard]

UNATTENDED_FLAG = os.path.join(".scratch", "unattended")


def unattended(ev):
    """Unattended mode (an agent loop with nobody at the keyboard): HARNESS_UNATTENDED=1 in the tool's environment,
    or the file .scratch/unattended (the orchestrator creates it when the loop starts and deletes it at the end).
    Turning it on only makes the guards stricter, so any agent may create the flag."""
    return os.environ.get("HARNESS_UNATTENDED") == "1" or os.path.isfile(os.path.join(ev["root"], UNATTENDED_FLAG))


def decide(ev):
    asked = None
    for g in GUARDS:
        r = g.evaluate(ev)
        if r and r[0] == "deny":
            return r
        asked = asked or r
    # Unattended: nobody answers a confirmation prompt, and a pending prompt would stall the loop. It becomes a
    # deny with the reason, and the agent records the open question for the human and moves on.
    if asked and asked[0] == "ask" and unattended(ev):
        return ("deny", f"UNATTENDED (no human present): {asked[1]} This needs the human: do not look for another"
                        " route; record it (main agent: python -I tools/pending.py question; worker: in its final"
                        " answer) and continue without this write.")
    return asked


def log(data, ev, decision):
    """Audit log per session. The logic lives in tools/audit_log.py and is loaded only if present.
    A logging failure never blocks and never changes the decision."""
    try:
        import importlib.util
        path = os.path.join(ev["root"], "tools", "audit_log.py")
        if not os.path.isfile(path):
            return
        spec = importlib.util.spec_from_file_location("audit_log", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.record(data, ev, decision)
    except Exception:
        pass


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        data = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    ev = event.normalize(data)
    decision = decide(ev)
    log(data, ev, decision)
    event.emit(ev, decision)


if __name__ == "__main__":
    main()
