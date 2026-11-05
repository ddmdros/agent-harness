"""Tool-agnostic adapter for the guards: turns each agent tool's PreToolUse event into one neutral shape and
emits the decision in the format each tool understands.

Usage: imported by tools/guards/pre_tool_use.py (does not run on its own).

Neutral event (dict):
  source   "claude" | "antigravity"
  kind     "write" (new file or full rewrite) | "edit" (replace a span) | "shell" | "other"
  path     file path (write/edit) or ""
  command  command text (shell) or ""
  root     repository root (derived from this file's location, not from the tool)
  cwd      directory the command runs from (Claude Code: the event's `cwd`; Antigravity: the root)

Decision: None (no opinion, let it run) | ("deny", reason) | ("ask", reason).
- Claude Code: deny = exit code 2 + reason on stderr; ask = hookSpecificOutput JSON on stdout.
- Antigravity: JSON {"decision": "deny"|"force_ask", "reason"} on stdout; no opinion = {}.
  `force_ask` (not `ask`) because "Always Allow" would otherwise skip the confirmation.
New tool: add its mapping to normalize() and its output to emit().
"""
import json, sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])

# Claude Code: tool_name -> kind
CLAUDE = {"Write": "write", "Edit": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
          "Bash": "shell", "PowerShell": "shell"}
# Antigravity (IDE and CLI): tool name -> (kind, argument that holds the path)
ANTIGRAVITY = {"write_to_file": ("write", "TargetFile"), "write_file": ("write", "Path"),
               "replace_file_content": ("edit", "TargetFile"),
               "multi_replace_file_content": ("edit", "TargetFile"), "edit_file": ("edit", "Path")}


def normalize(data, root=ROOT):
    if isinstance(data.get("toolCall"), dict):
        name = data["toolCall"].get("name", "")
        args = data["toolCall"].get("args") or {}
        ev = {"source": "antigravity", "kind": "other", "path": "", "command": "", "root": root, "cwd": root}
        if name == "run_command":
            ev.update(kind="shell", command=args.get("CommandLine", ""))
        elif name in ANTIGRAVITY:
            kind, key = ANTIGRAVITY[name]
            ev.update(kind=kind, path=args.get(key, ""))
        return ev
    name = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    ev = {"source": "claude", "kind": CLAUDE.get(name, "other"), "path": "", "command": "", "root": root,
          "cwd": data.get("cwd") or root}
    if ev["kind"] == "shell":
        ev["command"] = inp.get("command", "")
    elif ev["kind"] in ("write", "edit"):
        ev["path"] = inp.get("file_path") or inp.get("notebook_path") or ""
    return ev


def render(ev, decision):
    """(stdout text, stderr text, exit code) for the decision, in the tool's own protocol."""
    if ev["source"] == "antigravity":
        if decision is None:
            return "{}", "", 0
        d, reason = decision
        return json.dumps({"decision": "deny" if d == "deny" else "force_ask", "reason": reason},
                          ensure_ascii=False), "", 0
    if decision is None:
        return "", "", 0
    d, reason = decision
    if d == "deny":
        return "", reason, 2
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                              "permissionDecisionReason": reason}}, ensure_ascii=False), "", 0


def emit(ev, decision):
    out, err, code = render(ev, decision)
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    sys.exit(code)
