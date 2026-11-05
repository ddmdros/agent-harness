#!/usr/bin/env python3
"""Worker output with a unique name: every run is a new file in wip/runs/, so two runs never overwrite each other.

Usage:
  python -I tools/runs.py name <slice folder> <worker> [--session S]     free path for the run (does not create it)
  python -I tools/runs.py save <slice folder> <worker> <file> [--session S]
                                                                         copy the file into a new run (exclusive)
  python -I tools/runs.py latest <slice folder> <worker>                 latest run of the worker
  python -I tools/runs.py list <slice folder> [<worker>]                 runs of the slice, oldest first
Importable: name(), save(), latest(), runs().

Where: <job>/wip/runs/<slice>/<time>-<session>-<worker>.json. <slice> is the slice folder relative to the job's
wip/ (empty when the folder is wip/ itself); <time> is YYYYMMDD-HHMMSS. The zone wip/runs/** is `append` in the
map: a new file is free and an existing one never changes or disappears.
The orchestrator runs `name` and hands the path to the worker as OUTPUT; the worker writes there with its Write
tool (the guard denies writing over an existing run).
Worker names: the run name is <time>-<session>-<worker> and all three may contain "-", so a worker name must not
end with "-<another worker's name>" (e.g. `reviewer` next to `style-reviewer`): filtering by `reviewer` would also
match the other worker's runs.
Session: --session; else the tool's environment variable; else the session that just ran this command, read from
the audit log (tools/audit_log.py); else "no_session".
"""
import json, os, re, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION_ENV = ("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "ANTIGRAVITY_SESSION_ID")
RUN_NAME = re.compile(r"^(\d{8}-\d{6})-(.+)\.json$")


def _clean(s, limit=80):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(s))[:limit].strip(".") or "x"


def wip_of(folder):
    """(job's wip/ folder, slice relative to it with '/'). Error when the folder is not inside a wip/."""
    p = Path(folder).resolve()
    for anc in [p, *p.parents]:
        if anc.name.lower() == "wip":
            rel = p.relative_to(anc).as_posix()
            return anc, "" if rel == "." else rel
    raise ValueError(f"{folder}: not inside a job's wip/ folder (wip/runs/ belongs to the job).")


def _session_from_audit_log(root=ROOT, window=15):
    """Session whose newest audit line (last `window` seconds) runs tools/runs.py."""
    base = root / ".audit"
    best = ("", None)
    try:
        now = time.time()
        days = sorted((d for d in base.iterdir() if d.is_dir()), reverse=True)[:2]
        for d in days:
            for f in d.glob("*.jsonl"):
                if now - f.stat().st_mtime > window:
                    continue
                with open(f, "rb") as fh:
                    fh.seek(max(0, f.stat().st_size - 20000))
                    for ln in fh.read().decode("utf-8", "replace").splitlines():
                        try:
                            e = json.loads(ln)
                        except ValueError:
                            continue
                        if "runs.py" in e.get("command", "") and e.get("time", "") > best[0]:
                            best = (e["time"], e.get("session"))
    except OSError:
        pass
    return best[1]


def session(explicit=None):
    if explicit:
        return _clean(explicit)
    for k in SESSION_ENV:
        if os.environ.get(k):
            return _clean(os.environ[k])
    return _clean(_session_from_audit_log() or "no_session")


def runs_folder(folder):
    wip, sl = wip_of(folder)
    return wip / "runs" / sl if sl else wip / "runs"


def name(folder, worker, sess=None, now=None):
    """Free path (does not exist yet) for the run. Does not create it: the worker writes it."""
    dest = runs_folder(folder)
    now = now or datetime.now()
    base = f"{now:%Y%m%d-%H%M%S}-{session(sess)}-{_clean(worker, 60)}"
    path, n = dest / f"{base}.json", 2
    while path.exists():
        path, n = dest / f"{base}.{n}.json", n + 1
    return path


def save(folder, worker, text, sess=None):
    """Write `text` to a new run in exclusive mode (O_EXCL); return its path. Never overwrites."""
    path = None
    for _ in range(50):
        path = name(folder, worker, sess)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
        except FileExistsError:
            continue
        try:
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)
        return path
    raise FileExistsError(f"no free name in {path.parent}")


def runs(folder, worker=None):
    """Runs of the slice (Path), oldest first; only the worker's, if given."""
    d = runs_folder(folder)
    if not d.is_dir():
        return []
    out = []
    for f in d.iterdir():
        m = RUN_NAME.match(f.name)
        if f.is_file() and m and (worker is None
                                  or re.sub(r"\.\d+$", "", m.group(2)).endswith("-" + _clean(worker, 60))):
            out.append(f)
    return sorted(out, key=_order)


def _order(f):
    """Sort key: time, then the base name, then the collision counter (x.json < x.2.json < x.10.json)."""
    m = re.match(r"^(.*?)(?:\.(\d+))?\.json$", f.name)
    return m.group(1), int(m.group(2) or 1)


def latest(folder, worker):
    """Latest run of the worker in the slice, or None."""
    r = runs(folder, worker)
    return r[-1] if r else None


def _opt(args, key):
    if key in args:
        i = args.index(key)
        v = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
        return v
    return None


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    args = list(argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    c = args.pop(0)
    sess = _opt(args, "--session")
    try:
        if c == "name" and len(args) == 2:
            print(name(args[0], args[1], sess))
        elif c == "save" and len(args) == 3:
            print(save(args[0], args[1], Path(args[2]).read_text(encoding="utf-8"), sess))
        elif c == "latest" and len(args) == 2:
            r = latest(args[0], args[1])
            if r is None:
                print(f"No run of {args[1]} in {args[0]}.", file=sys.stderr)
                return 1
            print(r)
        elif c == "list" and len(args) in (1, 2):
            for f in runs(args[0], args[1] if len(args) == 2 else None):
                print(f)
        else:
            print(__doc__)
            return 2
    except (ValueError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
