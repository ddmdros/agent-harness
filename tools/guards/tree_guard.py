"""Tree guard: every write obeys the write-zone map .agents/tree.toml.

Usage: called by tools/guards/pre_tool_use.py via evaluate(ev); does not run on its own.

File tools (deterministic), by the mode of the path's zone:
  free -> allow | blocked -> deny | ask -> confirm | script -> deny (only the tool named in `by` writes there)
  deliver -> new file allowed; existing file or edit -> confirm
  append  -> new file allowed; existing file or edit -> deny
Shell (best effort over the text): splits the command into segments and finds the target of each write
  (rm, mv, touch, mkdir, tee, sed -i, Remove-Item, Set-Content...; the destination of cp; > redirection),
  following the event's cwd and the command's own `cd`s, then applies the target zone's mode as above.
  A `script` zone allows the command when it runs the tool named in `by`. An existing folder as the
  destination means "create inside it".
  Python code that writes files (-c or heredoc): finds the target of each write call (a literal in
  open(..., 'w'), Path(...).write_text, shutil, os.remove... or a variable assigned to a literal) and applies
  that zone's mode; a path mentioned only as data does not count. If some write has an unreadable target
  (built at runtime), falls back to the strict rule: blocked and ask zones of every quoted path.
  SQL writes that mention a .db file, and the `build` command of the tools in [tree_guard].db_builders:
  the target is the database.
Paths built at runtime are not caught. Outside the repository: no opinion. Reading is never blocked.
"""
import os, re, shlex, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import tree  # noqa: E402  (tools/tree.py)

WRITES_OR_CREATES = {"rm", "rmdir", "del", "erase", "rd", "touch", "mkdir", "truncate", "tee", "remove-item",
                     "new-item", "set-content", "add-content", "clear-content", "out-file", "rename-item", "ren",
                     "unlink", "shred", "install"}
MOVE = {"mv", "move", "move-item"}                         # source and destination change
COPY = {"cp", "copy", "copy-item", "xcopy", "robocopy"}    # only the destination changes
UNPACK = {"unzip", "tar", "7z", "expand-archive"}          # destination not always explicit: every quoted path
CD = {"cd", "set-location", "pushd", "sl"}
NULLS = {"/dev/null", "nul", "$null", "/dev/stdout", "/dev/stderr"}
# Cmdlet parameters whose value is not a path: -Encoding utf8NoBOM is not a file to write.
NOT_A_PATH = {"-encoding", "-value", "-itemtype", "-delimiter", "-inputobject", "-width"}

PY_WRITE = re.compile(r"open\([^)]*,\s*(?:mode\s*=\s*)?['\"][^'\"]*[wax+]|write_text|write_bytes|to_csv|to_json|shutil\.|"
                      r"os\.(remove|rename|replace|unlink)|unlink\(|rmtree")
SQL_WRITE = re.compile(r"\b(insert|update|delete|drop|create|alter|replace|vacuum)\s", re.I)
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
PATHISH = re.compile(r"[\w.~:-]*/[^\s'\"`)>|;&,]*")  # only tokens with "/": os.path is not a path


def _build_regex():
    builders = tree.settings("tree_guard").get("db_builders", [])
    return re.compile(r"\b(" + "|".join(map(re.escape, builders)) + r")\.py['\"]?\s+build\b") if builders else None


def _abs(path, cwd):
    c = path.replace("\\", "/")
    if re.match(r"^/[a-z]/", c, re.I):  # Git Bash: /c/... -> C:/...
        c = c[1] + ":" + c[2:]
    return os.path.normpath(c if os.path.isabs(c) else os.path.join(cwd, c))


def decide(rel, new, command=""):
    """Decision for writing to `rel`. new=True when the write only creates (the file does not exist yet)."""
    mode, z = tree.zone(rel)
    where = z["path"] if z else "outside the map"
    note = f" {z['note']}" if z and z.get("note") else ""
    hint = f" See: python -I tools/tree.py where {rel}"
    if mode == "free":
        return None
    if mode == "blocked":
        way_out = (" A new place needs a zone in .agents/tree.toml, approved by the human." if z is None
                   else " Reading is fine; to change something here, ask the human.")
        return ("deny", f"BLOCKED by the write-zone map: {rel} is in '{where}' (blocked).{note}{way_out}{hint}")
    if mode == "ask":
        return ("ask", f"Write-zone map: {rel} is in '{where}' (ask).{note}")
    if mode == "script":
        if z.get("by") and os.path.basename(z["by"]).lower() in command.lower():
            return None
        return ("deny", f"BLOCKED by the write-zone map: {rel} is only written by {z.get('by')}.{note}{hint}")
    if new:
        return None
    if mode == "deliver":
        return ("ask", f"Write-zone map: {rel} is a deliverable ('{where}'): confirm the change to an existing"
                       f" file.{note}")
    return ("deny", f"BLOCKED by the write-zone map: {rel} is in '{where}' (append): an existing file never changes"
                    f" or disappears; write a new file.{note}")


def _file(ev):
    rel = tree.relative(ev["path"]) if ev["path"] else None
    if rel is None:
        return None
    abs_ = _abs(ev["path"], ev.get("cwd") or ev["root"])
    new = ev["kind"] == "write" and not os.path.exists(abs_)
    return decide(rel, new)


def _strip_heredoc(cmd):
    """(command without heredoc bodies, text of the bodies)."""
    outside, body, tag = [], [], None
    for ln in cmd.split("\n"):
        if tag is not None:
            if ln.strip() == tag:
                tag = None
            else:
                body.append(ln)
            continue
        outside.append(ln)
        m = HEREDOC.search(ln)
        if m:
            tag = m.group(1)
    return "\n".join(outside), "\n".join(body)


SHELL_WORDS = {"do", "then", "else", "elif", "if", "while", "until", "time", "!", "{", "(", "&"}
SEPARATORS = {";", "&&", "||", "|", "&", ";;", "(", ")"}


def _newlines_to_semicolons(cmd):
    """Replace newlines outside quotes with ';' (each line is a command)."""
    out, quote = [], None
    for ch in cmd:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "\n":
            ch = ";"
        out.append(ch)
    return "".join(out)


def _tokens(text):
    """Tokens with operators (; && | > >>) split out, honoring quotes; plain split when quotes don't close."""
    text = _newlines_to_semicolons(text.replace("\\", "/"))
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return text.split()


def _usable(t):
    return t and not t.startswith("-") and "$" not in t and "`" not in t and t.lower() not in NULLS


def shell_targets(cmd, cwd):
    """[(absolute path, creates_only)] the command writes, as far as the text shows."""
    without, _ = _strip_heredoc(cmd)
    segments, current = [], []
    for t in _tokens(without):
        if t in SEPARATORS:
            segments.append(current); current = []
        else:
            current.append(t)
    segments.append(current)
    targets = []
    for toks in segments:
        # redirection: > x, >> x, 2> x; >& / <& / < do not write a file
        rest, i = [], 0
        while i < len(toks):
            t = toks[i]
            if t in (">", ">>", ">|", "&>") and i + 1 < len(toks):
                if rest and rest[-1].isdigit():
                    rest.pop()
                if _usable(toks[i + 1]):
                    targets.append((_abs(toks[i + 1], cwd), t != ">>"))
                i += 2
                continue
            if t in (">&", "<&", "<", "<<", "<<<", "<<-") and i + 1 < len(toks):
                i += 2
                continue
            rest.append(t); i += 1
        while rest and (rest[0].lower() in SHELL_WORDS or re.match(r"^\w+=", rest[0])):
            rest = rest[1:]
        if not rest:
            continue
        verb = rest[0].lower()
        args = [t for j, t in enumerate(rest[1:]) if _usable(t) and (j == 0 or rest[j].lower() not in NOT_A_PATH)]
        if verb in ("sudo", "command", "exec") and args:
            verb, args = args[0].lower(), args[1:]
        if verb in CD:
            if args:
                cwd = _abs(args[0], cwd)
            continue
        if verb in WRITES_OR_CREATES:
            creates = verb in ("touch", "mkdir", "new-item")
            targets += [(_abs(a, cwd), creates) for a in args]
        elif verb in MOVE and args:
            targets += [(_abs(a, cwd), False) for a in args[:-1]] + [(_abs(args[-1], cwd), True)]
        elif verb in COPY and args:
            targets.append((_abs(args[-1], cwd), True))
        elif verb in UNPACK:
            targets += [(_abs(a, cwd), True) for a in args]
        elif verb == "sed" and any(re.match(r"^-\w*i", t) or t == "--in-place" for t in rest[1:]):
            targets += [(_abs(a, cwd), False) for a in args[1:]]  # args[0] is the sed script
    return targets


# Python write calls. "arg": target is the 1st argument; "args": every argument; "recv": the object before the dot.
PY_CALLS = re.compile(r"(?P<recv>\.(?:write_text|write_bytes|unlink|rmdir|touch|mkdir|rename|replace)\()|"
                      r"(?P<arg>\bopen\(|\.to_(?:csv|json|excel|parquet)\()|"
                      r"(?P<args>\bshutil\.\w+\(|\bos\.(?:remove|rename|replace|unlink|makedirs|mkdir|rmdir)\(|"
                      r"(?<![.\w])(?:rmtree|unlink|remove)\()")
LITERAL = re.compile(r"[rRbBuU]{0,2}(['\"])(.*?)(?<!\\)\1")
IDENT = re.compile(r"[A-Za-z_]\w*")


def _closing(txt, i):
    """Index of the ')' that closes the '(' at txt[i-1]; len(txt) when it never closes."""
    level, quote = 1, None
    for j in range(i, len(txt)):
        ch = txt[j]
        if quote:
            quote = None if ch == quote and txt[j - 1] != "\\" else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "([{":
            level += 1
        elif ch in ")]}":
            level -= 1
            if level == 0:
                return j
    return len(txt)


def _call_args(txt, i):
    """Arguments (as text) of the call whose '(' is at txt[i-1], split on top-level commas."""
    end, parts, cur, level, quote = _closing(txt, i), [], "", 0, None
    for ch in txt[i:end]:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "([{":
            level += 1
        elif ch in ")]}":
            level -= 1
        elif ch == "," and level == 0:
            parts.append(cur); cur = ""
            continue
        cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _receiver(txt, dot):
    """Text of the object before txt[dot] == '.': Path('x'), (root / 'y'), name or name.attribute."""
    j = dot
    if j > 0 and txt[j - 1] == ")":
        level, k = 0, j - 1
        while k >= 0:
            level += txt[k] == ")"
            level -= txt[k] == "("
            if level == 0:
                break
            k -= 1
        k = max(k, 0)
        while k > 0 and (txt[k - 1].isalnum() or txt[k - 1] in "_."):
            k -= 1
        return txt[k:j]
    k = j
    while k > 0 and (txt[k - 1].isalnum() or txt[k - 1] in "_."):
        k -= 1
    return txt[k:j]


def _resolve(expr, assigned, depth=0):
    """Paths (literals) the expression builds, following names assigned to literals; [] when no literal."""
    lits = [m.group(2) for m in LITERAL.finditer(expr)]
    if depth < 2:
        for name in IDENT.findall(LITERAL.sub("", expr)):
            if name in assigned:
                lits += _resolve(assigned[name], assigned, depth + 1)
    paths = [l for l in lits if "/" in l.replace("\\", "/") or re.search(r"\.\w{1,5}$", l)]
    if not paths and len(lits) > 1:  # os.path.join('.scratch', 'x'), Path('a') / 'b'
        paths = ["/".join(lits)]
    return paths


def python_targets(cmd):
    """Paths the command's Python code writes; None when some write has a target the text does not show."""
    assigned = {}
    for m in re.finditer(r"^[ \t]*([A-Za-z_]\w*)[ \t]*=(?!=)[ \t]*(.+)$", cmd, re.M):
        assigned[m.group(1)] = m.group(2)
    targets = []
    for m in PY_CALLS.finditer(cmd):
        start = m.end()
        if m.group("recv"):
            expr = _receiver(cmd, m.start())
        elif m.group("arg"):
            args = _call_args(cmd, start)
            if not args:
                continue
            if m.group("arg").startswith("open"):
                mode = args[1] if len(args) > 1 and "=" not in args[1] else next(
                    (a.split("=", 1)[1] for a in args[1:] if a.replace(" ", "").startswith("mode=")), "'r'")
                if not re.search(r"['\"][^'\"]*[wax+]", mode):
                    continue  # open for reading
            expr = args[0]
        else:
            expr = ",".join(_call_args(cmd, start))
        paths = _resolve(expr, assigned)
        if not paths:
            return None
        targets += paths
    return targets


def _shell(ev):
    cmd, root = ev["command"], ev["root"]
    cwd = ev.get("cwd") or root
    asked = None

    def weigh(r):
        nonlocal asked
        if r and r[0] == "deny":
            return r
        asked = asked or r
        return None

    for abs_, creates in shell_targets(cmd, cwd):
        rel = tree.relative(abs_)
        if rel is None:
            continue
        # Existing folder as destination (cp x folder/, mkdir -p folder): writes inside it, not on it.
        new = creates and (not os.path.exists(abs_) or os.path.isdir(abs_))
        target = rel + "/new" if os.path.isdir(abs_) and creates else rel
        if (r := weigh(decide(target, new, cmd))):
            return r

    low = cmd.replace("\\", "/").lower()
    quoted = {m.group(0).strip("'\"") for m in PATHISH.finditer(low)}
    if PY_WRITE.search(cmd):
        py = python_targets(cmd)
        if py is None:  # some write without a readable target: every quoted path, blocked and ask zones only
            for c in quoted:
                rel = tree.relative(_abs(c, cwd))
                if rel is None:
                    continue
                mode, z = tree.zone(rel)
                if z is not None and mode in ("blocked", "ask"):  # outside the map: may not even be a path
                    if (r := weigh(decide(rel, False, cmd))):
                        return r
        else:
            for c in py:
                abs_ = _abs(c, cwd)
                rel = tree.relative(abs_)
                if rel is None:
                    continue
                mode, z = tree.zone(rel)
                if z is None:  # outside the map: the literal may be only part of the path (root in a variable)
                    continue
                if (r := weigh(decide(rel, not os.path.exists(abs_), cmd))):
                    return r
    # SQL write: the quoted database.
    if SQL_WRITE.search(cmd) and not PY_WRITE.search(cmd):
        for c in quoted:
            if not c.endswith(".db"):
                continue
            rel = tree.relative(_abs(c, cwd))
            if rel is None:
                continue
            mode, z = tree.zone(rel)
            if z is not None and mode in ("blocked", "ask"):
                if (r := weigh(decide(rel, False, cmd))):
                    return r
    build = _build_regex()
    b = build.search(low) if build else None
    if b:
        weigh(("ask", f"{b.group(1)}.py build regenerates a .db database: confirm."))
    return asked


def evaluate(ev):
    if ev["kind"] in ("write", "edit"):
        return _file(ev)
    if ev["kind"] == "shell":
        return _shell(ev)
    return None
