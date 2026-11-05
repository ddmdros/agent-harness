#!/usr/bin/env python3
"""Generate the per-tool copies from the tool-neutral sources in .agents/.

Usage: python -I tools/sync_adapters.py            (copy, and delete what has no source)
       python -I tools/sync_adapters.py --check    (only compare; exit 1 on any difference)

Source (edit here)              Generated copy (do not edit)
  .agents/skills/<name>/    ->    .claude/skills/<name>/
  .agents/workers/<name>.md ->    .claude/agents/<name>.md
Antigravity reads .agents/ directly; Claude Code only reads .claude/. Rules (AGENTS.md) do not go through here:
every CLAUDE.md next to an AGENTS.md holds only `@AGENTS.md`, and --check verifies that too.
"""
import filecmp, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [(ROOT / ".agents/skills", ROOT / ".claude/skills", "dir"),
         (ROOT / ".agents/workers", ROOT / ".claude/agents", "md")]
STUB = "@AGENTS.md"


def items(folder, kind):
    if not folder.exists():
        return {}
    if kind == "dir":
        return {p.name: p for p in folder.iterdir() if p.is_dir()}
    return {p.name: p for p in folder.glob("*.md")}


def same(a, b, kind):
    if not b.exists():
        return False
    if kind == "md":
        return filecmp.cmp(a, b, shallow=False)
    c = filecmp.dircmp(a, b)
    if c.left_only or c.right_only or c.funny_files:
        return False
    _, diff, err = filecmp.cmpfiles(a, b, c.common_files, shallow=False)
    return not diff and not err and all(same(a / d, b / d, "dir") for d in c.common_dirs)


def stub_problems():
    """Problems with the CLAUDE.md next to each tracked AGENTS.md."""
    r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "AGENTS.md", "*/AGENTS.md"],
                       cwd=ROOT, capture_output=True, text=True)
    errors = []
    for rel in r.stdout.split():
        c = ROOT / Path(rel).parent / "CLAUDE.md"
        if not c.exists():
            errors.append(f"{c.relative_to(ROOT).as_posix()}: missing (must hold only `{STUB}`)")
        elif c.read_text(encoding="utf-8").strip() != STUB:
            errors.append(f"{c.relative_to(ROOT).as_posix()}: must hold only `{STUB}`; rules go in AGENTS.md")
    return errors


def main():
    check = "--check" in sys.argv
    pending = []
    for source, dest, kind in PAIRS:
        src, dst = items(source, kind), items(dest, kind)
        for name, p in src.items():
            target = dest / name
            if same(p, target, kind):
                continue
            pending.append(f"{target.relative_to(ROOT).as_posix()}: differs from {p.relative_to(ROOT).as_posix()}")
            if not check:
                dest.mkdir(parents=True, exist_ok=True)
                if kind == "dir":
                    shutil.rmtree(target, ignore_errors=True)
                    shutil.copytree(p, target)
                else:
                    shutil.copy2(p, target)
        for name in set(dst) - set(src):
            target = dst[name]
            pending.append(f"{target.relative_to(ROOT).as_posix()}: no source in {source.relative_to(ROOT).as_posix()}")
            if not check:
                shutil.rmtree(target) if kind == "dir" else target.unlink()
    stubs = stub_problems()
    for ln in pending:
        print(("DIFFERENT: " if check else "synced: ") + ln)
    for ln in stubs:
        print("STUB: " + ln)
    if check and (pending or stubs):
        print("Run: python -I tools/sync_adapters.py (source: .agents/)")
        sys.exit(1)
    if stubs:
        sys.exit(1)
    if not pending:
        print("ok: .claude/ matches .agents/")


if __name__ == "__main__":
    main()
