#!/usr/bin/env python3
"""Write-zone map: tells which zone a path falls in and checks the disk against the map.

Usage:
  python -I tools/tree.py where <path> [<path> ...]   zone and mode of each path
  python -I tools/tree.py check [--all]               files on disk that no zone covers (fall into the default mode)

The map is .agents/tree.toml. Importable: load(), zone(rel) -> (mode, zone dict or None), relative(path).
"""
import os, re, sys, tomllib
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / ".agents" / "tree.toml"
MODES = {"free", "deliver", "append", "ask", "script", "blocked"}
SKIP = {".git", "__pycache__"}  # `check` does not walk into these


def glob_to_regex(glob):
    """Map glob -> regex. `*` = one name, `**` = zero or more folders, `{a,b}` = a or b, `?` = one char."""
    out, i = [], 0
    while i < len(glob):
        c = glob[i]
        if glob.startswith("**/", i):
            out.append(r"(?:.*/)?"); i += 3
        elif glob.startswith("/**", i) and i + 3 == len(glob):
            out.append(r"(?:/.*)?"); i += 3
        elif glob.startswith("**", i):
            out.append(r".*"); i += 2
        elif c == "*":
            out.append(r"[^/]*"); i += 1
        elif c == "?":
            out.append(r"[^/]"); i += 1
        elif c == "{":
            end = glob.index("}", i)
            out.append("(?:" + "|".join(glob_to_regex(p) for p in glob[i + 1:end].split(",")) + ")"); i = end + 1
        else:
            out.append(re.escape(c)); i += 1
    return "".join(out)


@lru_cache(maxsize=4)
def load(map_path=MAP):
    """(default mode, [(compiled regex, zone dict)], full TOML data). Raises ValueError on an invalid map."""
    with open(map_path, "rb") as f:
        data = tomllib.load(f)
    default = data.get("default", "blocked")
    if default not in MODES:
        raise ValueError(f"{map_path}: invalid default: {default!r}")
    zones = []
    for z in data.get("zone", []):
        if z.get("mode") not in MODES:
            raise ValueError(f"{map_path}: invalid mode in {z.get('path')!r}: {z.get('mode')!r}")
        if z["mode"] == "script" and not z.get("by"):
            raise ValueError(f"{map_path}: script zone without `by` in {z['path']!r}")
        zones.append((re.compile(glob_to_regex(z["path"].lower()) + r"\Z"), z))
    return default, zones, data


def settings(section, map_path=MAP):
    """Extra settings table from the map (e.g. [git]); {} when absent."""
    return load(map_path)[2].get(section, {})


def relative(path, root=ROOT):
    """Path relative to the root, lowercase, with "/"; None when outside the project."""
    p = os.path.normpath(path if os.path.isabs(path) else os.path.join(root, path))
    try:
        rel = os.path.relpath(p, root)
    except ValueError:  # another drive on Windows
        return None
    if rel == ".." or rel.startswith(".." + os.sep) or rel.startswith("../"):
        return None
    return rel.replace("\\", "/").lower()


def zone(rel, map_path=MAP):
    """(mode, zone) of the LAST zone that matches `rel`; (default, None) when none matches."""
    default, zones, _ = load(map_path)
    rel = rel.strip("/").lower()
    found = None
    for rx, z in zones:
        if rx.match(rel):
            found = z
    return (found["mode"], found) if found else (default, None)


def where(paths):
    for p in paths:
        rel = relative(p)
        if rel is None:
            print(f"{p}\n  outside the repository: the map does not apply")
            continue
        mode, z = zone(rel)
        print(f"{rel}\n  {mode}  <- {z['path'] if z else 'default (no zone)'}")
        if z and z.get("by"):
            print(f"  only via: {z['by']}")
        if z and z.get("note"):
            print(f"  {z['note']}")


def check(show_all=False):
    """List files on disk that no zone covers. A folder that is entirely outside the map is one line."""
    default, _, _ = load()
    outside_files, count = [], {}
    total, total_out = {}, {}  # per folder: files below it, and how many of them are outside
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP)
        rel_dir = os.path.relpath(dirpath, ROOT).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        for f in sorted(filenames):
            rel = rel_dir + f
            mode, z = zone(rel)
            count[mode] = count.get(mode, 0) + 1
            folders = ["/".join(rel.split("/")[:i]) for i in range(1, rel.count("/") + 1)]
            for d in folders:
                total[d] = total.get(d, 0) + 1
            if z is None:
                outside_files.append(rel)
                for d in folders:
                    total_out[d] = total_out.get(d, 0) + 1
    whole = {d for d, n in total_out.items() if n == total[d]}
    outside, seen = [], set()
    for rel in outside_files:
        parts = rel.split("/")
        top = next(("/".join(parts[:i]) for i in range(1, len(parts)) if "/".join(parts[:i]) in whole), None)
        if top is None:
            outside.append(rel)
        elif top not in seen:
            seen.add(top)
            outside.append(f"{top}/  ({total[top]} files)")
    print("Files per mode:", ", ".join(f"{m} {n}" for m, n in sorted(count.items())))
    print(f"Outside the map (falls into '{default}'): {len(outside)}")
    for item in outside if show_all else outside[:60]:
        print("  " + item)
    if not show_all and len(outside) > 60:
        print(f"  ... {len(outside) - 60} more (use --all)")
    return 1 if outside else 0


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) >= 2 and argv[0] == "where":
        where(argv[1:])
        return 0
    if argv and argv[0] == "check":
        return check("--all" in argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
