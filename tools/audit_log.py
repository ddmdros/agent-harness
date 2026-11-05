#!/usr/bin/env python3
"""Per-session audit log: what each agent wrote or ran in the repository, and what the guards decided.

Usage:
  python -I tools/audit_log.py sessions [--date YYYY-MM-DD]       logged sessions (events, first and last time)
  python -I tools/audit_log.py session <id or prefix> [--denied]  what the session did, in order
  python -I tools/audit_log.py file <path>                        who touched the file (or folder), and when

Writes: the guard entry point (tools/guards/pre_tool_use.py) calls record(data, ev, decision) on every write or
shell command, from Claude Code or Antigravity. File reads are not logged.

Where: .audit/<date>/<session>.jsonl, one file per session, opened only in append mode (two agents never write
to the same file). The .audit/** zone is `append` in the map: no agent edits, deletes or moves a log line.
.audit/ stays out of git (.audit/.gitignore with '*'), because it quotes paths and commands. One JSON line per event:
  time (ISO, with offset)  session  agent ("claude" | "antigravity")  subagent (if any)  tool
  kind ("write" | "edit" | "shell")  path (relative to the root, file tools)
  command (shell, up to 4000 characters)  targets (relative paths the command writes, as far as the text shows)
  cwd  decision ("allow" | "ask" | "deny")  reason (from the guard, up to 500 characters)
record() never raises and never changes the guard's decision.
"""
import json, os, re, sys
from datetime import datetime

FOLDER = ".audit"
KINDS = ("write", "edit", "shell")
MAX_COMMAND, MAX_REASON = 4000, 500
# Where each tool puts the session id in the hook event. Claude Code: session_id. Antigravity: not confirmed;
# tries the likely names and, with none, falls back to the parent process id.
SESSION_KEYS = ("session_id", "sessionId", "conversation_id", "conversationId", "cascadeId",
                "cascade_id", "trajectoryId", "trajectory_id")


def session_of(data):
    v = None
    for source in (data, data.get("toolCall") if isinstance(data.get("toolCall"), dict) else {}):
        v = next((source.get(k) for k in SESSION_KEYS if source.get(k)), None)
        if v:
            break
    v = re.sub(r"[^A-Za-z0-9_.-]", "_", str(v or f"pid{os.getppid()}"))[:80].strip(".")
    return v or "no_session"


def _relative(path, root):
    try:
        p = os.path.normpath(path if os.path.isabs(path) else os.path.join(root, path))
        rel = os.path.relpath(p, root)
        return None if rel == ".." or rel.startswith("../") or rel.startswith(".." + os.sep) else rel.replace("\\", "/").lower()
    except ValueError:
        return None


def _targets(ev):
    """Relative paths the shell command writes, read the same way the guard reads them."""
    try:
        g = sys.modules.get("tree_guard")
        if g is None:
            sys.path.insert(0, os.path.join(ev["root"], "tools", "guards"))
            import tree_guard as g
        out = []
        for abs_, _ in g.shell_targets(ev["command"], ev.get("cwd") or ev["root"]):
            rel = _relative(abs_, ev["root"])
            if rel is not None and rel not in out:
                out.append(rel)
        return out
    except Exception:
        return []


def line(data, ev, decision, now=None):
    """Dict for one log line (or None when the event is not logged)."""
    if ev.get("kind") not in KINDS:
        return None
    now = now or datetime.now().astimezone()
    d = {"time": now.isoformat(timespec="milliseconds"), "session": session_of(data), "agent": ev.get("source"),
         "tool": data.get("tool_name") or (data.get("toolCall") or {}).get("name", ""), "kind": ev["kind"]}
    sub = data.get("agent_type") or data.get("agent_id")
    if sub:
        d["subagent"] = str(sub)[:80]
    if ev["kind"] == "shell":
        d["command"] = ev.get("command", "")[:MAX_COMMAND]
        d["targets"] = _targets(ev)
    else:
        d["path"] = _relative(ev.get("path", ""), ev["root"]) or ev.get("path", "")
    d["cwd"] = ev.get("cwd", "")
    d["decision"] = decision[0] if decision else "allow"
    if decision:
        d["reason"] = str(decision[1])[:MAX_REASON]
    return d


def _append(path, text):
    """One single write with O_APPEND: lines from parallel calls never interleave."""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)


def record(data, ev, decision):
    """Called by the guard entry point. Never raises."""
    try:
        d = line(data, ev, decision)
        if d is None:
            return
        base = os.path.join(ev["root"], FOLDER)
        folder = os.path.join(base, d["time"][:10])
        os.makedirs(folder, exist_ok=True)
        gi = os.path.join(base, ".gitignore")
        if not os.path.exists(gi):
            try:
                fd = os.open(gi, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                os.write(fd, b"*\n")
                os.close(fd)
            except OSError:
                pass
        _append(os.path.join(folder, d["session"] + ".jsonl"),
                json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- queries

def read(root, day=None):
    """Yield (file name, dict) for every log line (of one date, if given), in file order."""
    base = os.path.join(root, FOLDER)
    if not os.path.isdir(base):
        return
    for d in sorted(os.listdir(base)):
        if day and d != day:
            continue
        folder = os.path.join(base, d)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".jsonl"):
                continue
            with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as f:
                for ln in f:
                    try:
                        yield name, json.loads(ln)
                    except ValueError:
                        continue


def _summary(d):
    target = d.get("path") or d.get("command", "").replace("\n", " ⏎ ")
    if len(target) > 160:
        target = target[:157] + "..."
    mark = "" if d.get("decision") == "allow" else f" [{d.get('decision')}]"
    return f"{d.get('time', '')[:19]}  {d.get('tool', '')}{mark}  {target}"


def cmd_sessions(root, day=None):
    s = {}
    for _, d in read(root, day):
        k = d.get("session", "?")
        r = s.setdefault(k, {"n": 0, "start": d.get("time", ""), "end": "", "agent": d.get("agent", "")})
        r["n"] += 1
        r["end"] = d.get("time", "")
    for k, r in sorted(s.items(), key=lambda kv: kv[1]["start"]):
        print(f"{r['start'][:16]} -> {r['end'][11:16]}  {r['agent']:<11}  {r['n']:>5} events  {k}")
    if not s:
        print("No log entries.")
    return 0


def cmd_session(root, prefix, denied_only=False):
    found = set()
    for _, d in read(root):
        if not str(d.get("session", "")).startswith(prefix):
            continue
        found.add(d["session"])
        if denied_only and d.get("decision") == "allow":
            continue
        print(_summary(d))
    if len(found) > 1:
        print(f"\n(warning: the prefix matched {len(found)} sessions: {', '.join(sorted(found))})")
    if not found:
        print(f"No session starts with {prefix!r}.")
        return 1
    return 0


def cmd_file(root, path):
    rel = (_relative(path, root) or path.replace("\\", "/").lower()).rstrip("/")
    n = 0
    for _, d in read(root):
        targets = [d["path"]] if d.get("path") else d.get("targets", [])
        if any(a == rel or a.startswith(rel + "/") for a in targets):
            n += 1
            print(f"{d.get('session', '?')}  {d.get('agent', '')}  {_summary(d)}")
    if not n:
        print(f"Nobody logged a write to {rel}. (Commands whose path is built at runtime do not show up.)")
    return 0


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    c, rest = argv[0], argv[1:]
    if c == "sessions":
        day = rest[rest.index("--date") + 1] if "--date" in rest else None
        return cmd_sessions(root, day)
    if c == "session" and rest:
        return cmd_session(root, rest[0], "--denied" in rest)
    if c == "file" and rest:
        return cmd_file(root, rest[0])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
