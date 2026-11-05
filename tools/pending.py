#!/usr/bin/env python3
"""Decisions and questions from agents that wait for the human: queue/decisions.json and queue/questions.json.

Usage:
  python -I tools/pending.py                                       what waits for the human (open items)
  python -I tools/pending.py list [--all] [--session S]            same; --all includes answered items
  python -I tools/pending.py decision "<decision>" --why "<reason>" [--task T12] [--where "<file/ADR>"]
                             [--alternatives "<what was left out>"] [--session S] [--agent claude]
  python -I tools/pending.py question "<question>" --how "<how to resolve>" [--task T12] [--context "..."]
                             [--session S]
  python -I tools/pending.py answer <D001|Q001> <ok|no|change> ["<the human's answer>"]

A *decision by inference* is any choice an agent made without being told, that outlives the session (a format,
a name, a place, a rule, what was left out). The agent records it at once; the human approves it later by id.
A *question* is something only the human or a test can settle, that did not block the work.
Each entry gets an id (D### decision, Q### question) and starts as «awaiting approval» / «open».
Writes: read, append, and replace the whole file at once (os.replace) under a short lock file, so two sessions
never erase each other. Importable: record_decision(), record_question(), answer(), open_items().
"""
import json, os, sys, time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {"D": ROOT / "queue" / "decisions.json", "Q": ROOT / "queue" / "questions.json"}
KEY = {"D": "decisions", "Q": "questions"}
OPEN = {"D": "awaiting approval", "Q": "open"}
VERDICT = {"ok": "approved", "no": "rejected", "change": "change requested"}
ABOUT = {
    "D": "Decisions an agent made on its own that wait for the human's approval. Status: «awaiting approval» -> "
         "«approved» | «rejected» | «change requested» (the human says what changes in 'answer'). Record and "
         "answer only through tools/pending.py.",
    "Q": "Questions only the human or a test can settle, that did not block the work. Status: «open» -> "
         "«resolved». Record and answer only through tools/pending.py.",
}
SESSION_ENV = ("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "ANTIGRAVITY_SESSION_ID")


def _session(s=None):
    return s or next((os.environ[k] for k in SESSION_ENV if os.environ.get(k)), "")


class _Lock:
    def __init__(self, path, stale_after=10):
        self.lock, self.stale_after = path.with_suffix(".lock"), stale_after

    def __enter__(self):
        for _ in range(100):
            try:
                os.close(os.open(self.lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.lock.stat().st_mtime > self.stale_after:  # forgotten lock
                        self.lock.unlink()
                except OSError:
                    pass
                time.sleep(0.05)
        raise TimeoutError(f"{self.lock}: another session is writing")

    def __exit__(self, *a):
        try:
            self.lock.unlink()
        except OSError:
            pass


def _read(kind, path=None):
    path = path or FILES[kind]
    if not path.exists():
        return {"about": ABOUT[kind], KEY[kind]: []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(kind, data, path=None):
    path = path or FILES[kind]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _record(kind, fields, path=None):
    path = path or FILES[kind]
    path.parent.mkdir(parents=True, exist_ok=True)
    with _Lock(path):
        d = _read(kind, path)
        items = d.setdefault(KEY[kind], [])
        n = max([int(i["id"][1:]) for i in items] or [0]) + 1
        item = {"id": f"{kind}{n:03d}", "date": date.today().isoformat(), **fields, "status": OPEN[kind],
                "answer": None, "answered": None}
        items.append(item)
        _write(kind, d, path)
    return item


def record_decision(decision, why, task="", where="", alternatives="", session=None, agent="", path=None):
    return _record("D", {"session": _session(session), "agent": agent, "task": task, "decision": decision,
                         "why": why, "alternatives": alternatives, "where": where}, path)


def record_question(question, how, task="", context="", session=None, agent="", path=None):
    return _record("Q", {"session": _session(session), "agent": agent, "task": task, "question": question,
                         "context": context, "how_to_resolve": how}, path)


def answer(id_, verdict, text="", path=None):
    kind = id_[:1].upper()
    if kind not in FILES:
        raise ValueError(f"{id_}: ids start with D (decision) or Q (question)")
    path = path or FILES[kind]
    with _Lock(path):
        d = _read(kind, path)
        for i in d[KEY[kind]]:
            if i["id"].upper() == id_.upper():
                if kind == "Q":
                    i["status"] = "resolved"
                else:
                    if verdict not in VERDICT:
                        raise ValueError(f"verdict: {', '.join(VERDICT)}")
                    i["status"] = VERDICT[verdict]
                i["answer"] = text or verdict
                i["answered"] = date.today().isoformat()
                _write(kind, d, path)
                return i
    raise ValueError(f"{id_}: not found")


def open_items(kind, include_answered=False, session=None, path=None):
    items = _read(kind, path)[KEY[kind]]
    return [i for i in items if (include_answered or i["status"] == OPEN[kind]) and
            (not session or str(i.get("session", "")).startswith(session))]


def _opt(args, key, default=""):
    if key in args:
        i = args.index(key)
        v = args[i + 1] if i + 1 < len(args) else default
        del args[i:i + 2]
        return v
    return default


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    args = list(argv)
    c = args.pop(0) if args else "list"
    try:
        if c in ("-h", "--help"):
            print(__doc__)
        elif c == "list":
            every, sess = "--all" in args, _opt(args, "--session") or None
            for kind, title, field in (("D", "Decisions", "decision"), ("Q", "Questions", "question")):
                items = open_items(kind, every, sess)
                print(f"{title} ({len(items)}):")
                for i in items:
                    extra = f" [{i['status']}]" if every else ""
                    print(f"  {i['id']}{extra} {i.get('task') or '-'}: {i[field]}")
        elif c == "decision" and args:
            kw = dict(why=_opt(args, "--why"), task=_opt(args, "--task"), where=_opt(args, "--where"),
                      alternatives=_opt(args, "--alternatives"), session=_opt(args, "--session") or None,
                      agent=_opt(args, "--agent"))
            if not kw["why"]:
                raise ValueError("decision without --why")
            print(record_decision(args[0], **kw)["id"])
        elif c == "question" and args:
            kw = dict(how=_opt(args, "--how"), task=_opt(args, "--task"), context=_opt(args, "--context"),
                      session=_opt(args, "--session") or None, agent=_opt(args, "--agent"))
            if not kw["how"]:
                raise ValueError("question without --how (how it gets resolved)")
            print(record_question(args[0], **kw)["id"])
        elif c == "answer" and len(args) >= 2:
            i = answer(args[0], args[1], args[2] if len(args) > 2 else "")
            print(f"{i['id']}: {i['status']}")
        else:
            print(__doc__)
            return 2
    except (ValueError, TimeoutError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
