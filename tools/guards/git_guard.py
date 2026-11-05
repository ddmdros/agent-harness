#!/usr/bin/env python3
"""Git guard: keeps the pre-commit checks in force and controls where code can be pushed.

Usage: called by tools/guards/pre_tool_use.py via evaluate(ev); does not run on its own.
Settings: the [git] table of .agents/tree.toml:
  allowed_visibility = ["PRIVATE"]   push only to remotes whose GitHub visibility is listed here

- `git commit`: allowed. The data check lives in the repository's pre-commit hook, so `--no-verify`
  (and `-n` on commit) and `git add -f/--force` are denied: they would skip it or force ignored files in.
- `git push`: asks for confirmation when GitHub reports an allowed visibility; denied otherwise, including when
  the visibility cannot be read (fail closed).
- Making a repository PUBLIC or INTERNAL (`gh repo create --public`, `gh repo edit --visibility public`,
  `gh api ... visibility=public`): denied unless that visibility is allowed.

Coverage: shell commands from any tool, best effort over the command text.
"""
import os, re, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import tree  # noqa: E402  (tools/tree.py)

# git/gh only count at the start of a command (start, after ; && || | ( or a newline), so a mention inside
# text (a heredoc, a commit message, Markdown) does not trigger the guard.
START = r"(?:^|[;&|(\n])\s*"
GIT_CMD = START + r"git(?:\.exe)?(?:\s+-[cC]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+"
PUSH = re.compile(GIT_CMD + r"push\b", re.M)
FORCE_ADD = re.compile(GIT_CMD + r"add\b[^;&|\n]*\s(-f|--force)\b", re.M)
# --no-verify on commit/push; -n only on commit (on push, -n is --dry-run)
NO_VERIFY = re.compile(GIT_CMD + r"(?:(?:commit|push)\b[^;&|\n]*\s--no-verify\b|commit\b[^;&|\n]*\s-n\b)", re.M)
GH = START + r"gh(?:\.exe)?\s+"
GH_REPO_OR_API = re.compile(GH + r"(repo|api)\b", re.M)
REPO_CREATE = re.compile(GH + r"repo\s+create\b", re.M)
VISIBILITY = re.compile(r"--(public|internal)\b|visibility[=\s]+[\"']?(public|internal)", re.I)


def allowed():
    return {v.upper() for v in tree.settings("git").get("allowed_visibility", ["PRIVATE"])}


def visibility(cwd):
    """PRIVATE, PUBLIC or INTERNAL as GitHub reports it; None when it cannot be determined."""
    try:
        r = subprocess.run(["gh", "repo", "view", "--json", "visibility", "-q", ".visibility"],
                           cwd=cwd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    v = r.stdout.strip().upper()
    return v if r.returncode == 0 and v else None


def evaluate(ev):
    if ev["kind"] != "shell":
        return None
    cmd, ok = ev["command"], allowed()
    if REPO_CREATE.search(cmd) and "--private" not in cmd and "PUBLIC" not in ok:
        return ("deny", "BLOCKED by git_guard: `gh repo create` only with --private here.")
    m = VISIBILITY.search(cmd)
    if m and GH_REPO_OR_API.search(cmd) and (m.group(1) or m.group(2)).upper() not in ok:
        return ("deny", f"BLOCKED by git_guard: a {(m.group(1) or m.group(2)).lower()} repository is not allowed "
                        f"(allowed: {', '.join(sorted(ok))}).")
    if NO_VERIFY.search(cmd):
        return ("deny", "BLOCKED by git_guard: --no-verify skips the pre-commit/pre-push hooks that check the data.")
    if FORCE_ADD.search(cmd):
        return ("deny", "BLOCKED by git_guard: `git add -f` forces in files that .gitignore keeps out.")
    if PUSH.search(cmd):
        v = visibility(ev["root"])
        if v not in ok:
            return ("deny", f"BLOCKED by git_guard: push only to {', '.join(sorted(ok))} repositories; "
                            f"GitHub answered {v or 'nothing'}.")
        return ("ask", f"git_guard: push to a {v.lower()} repository; check what is going up.")
    return None
