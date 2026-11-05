"""Write-zone guard (tools/guards/tree_guard.py) over the demo map .agents/tree.toml.

Each case: a neutral event (as event.py builds it) -> expected decision: None (allow), "ask" or "deny".
Paths do not need to exist, except where a case says so (README.md, the demo project's folders and files).
"""
import os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools", "guards"))
import pre_tool_use, tree_guard  # noqa: E402
from event import ROOT  # noqa: E402

JOB = "projects/sample-rpg/jobs/2026-11-patch"
OUTSIDE = os.path.join(tempfile.gettempdir(), "notes.md")
DELIVERED = f"{JOB}/output/.gitkeep"  # exists in the repository


def file_ev(kind, path):
    return {"source": "claude", "kind": kind, "path": path, "command": "", "root": ROOT, "cwd": ROOT}


def sh(command, cwd=ROOT):
    return {"source": "claude", "kind": "shell", "path": "", "command": command, "root": ROOT, "cwd": cwd}


CASES = [
    # file tools
    ("Write README", file_ev("write", "README.md"), None),
    ("Write loose file at the root", file_ev("write", "junk.txt"), "deny"),
    ("Write loose file in a project", file_ev("write", "projects/sample-rpg/notes.txt"), "deny"),
    ("Write blocked reference", file_ev("write", "projects/sample-rpg/references/x.md"), "deny"),
    ("Edit glossary", file_ev("edit", "projects/sample-rpg/references/glossary.csv"), "ask"),
    ("Write database", file_ev("write", "projects/sample-rpg/db/tm.db"), "ask"),
    ("Edit source file", file_ev("edit", f"{JOB}/source/strings.json"), "deny"),
    ("Write new deliverable", file_ev("write", f"{JOB}/output/strings_pt.json"), None),
    ("Overwrite delivered file", file_ev("write", DELIVERED), "ask"),
    ("Edit delivered file", file_ev("edit", DELIVERED), "ask"),
    ("Write in the job's wip", file_ev("write", f"{JOB}/wip/notes.md"), None),
    ("Write new run", file_ev("write", f"{JOB}/wip/runs/20990101-000000-s-drafter.json"), None),
    ("Edit existing run", file_ev("edit", f"{JOB}/wip/runs/20261105-101500-demo-drafter.json"), "deny"),
    ("Write generated skill copy by hand", file_ev("write", ".claude/skills/translate-job/SKILL.md"), "deny"),
    ("Edit a guard", file_ev("edit", "tools/guards/git_guard.py"), "ask"),
    ("Edit the map", file_ev("edit", ".agents/tree.toml"), "ask"),
    ("Write skill source", file_ev("write", ".agents/skills/x/SKILL.md"), None),
    ("Edit decision queue by hand", file_ev("edit", "queue/decisions.json"), "deny"),
    ("Write outside the repository", file_ev("write", OUTSIDE), None),
    ("Absolute path inside the repository", file_ev("write", os.path.join(ROOT, "junk2.txt")), "deny"),
    # shell: reading is never blocked
    ("cat a reference", sh("cat projects/sample-rpg/references/style_guide.md"), None),
    ("grep with tee to scratch", sh("grep -r foo projects | tee .scratch/x.txt"), None),
    ("ls at the root", sh("ls -la; git status --short"), None),
    # shell: writes
    ("redirect to a loose file", sh("echo hi > out.txt"), "deny"),
    ("redirect to scratch", sh("echo hi > .scratch/out.txt"), None),
    ("2>&1 is not a file", sh("python -I tools/tree.py check 2>&1 | tail -3"), None),
    ("> /dev/null", sh("git fetch > /dev/null 2>&1"), None),
    ("rm a reference", sh("rm -rf projects/sample-rpg/references"), "deny"),
    ("rm in scratch", sh("rm -rf .scratch/dumps/x"), None),
    ("mkdir at the root", sh("mkdir _tmp_x"), "deny"),
    ("mkdir -p existing wip", sh(f"mkdir -p {JOB}/wip"), None),
    ("cp into existing output folder = create inside", sh(f"cp a.json {JOB}/output/"), None),
    ("cp over a delivered file", sh(f'cp a.json "{DELIVERED}"'), "ask"),
    ("rm a delivered file", sh(f'rm "{DELIVERED}"'), "ask"),
    ("sed -i on a guard", sh("sed -i 's/a/b/' tools/guards/git_guard.py"), "ask"),
    ("sed -n does not write", sh("sed -n 1,5p tools/guards/git_guard.py"), None),
    ("cd then write a loose file", sh("cd projects/sample-rpg && echo x > notes.txt"), "deny"),
    ("cd then write in wip", sh(f"cd {JOB} && echo x > wip/n.txt"), None),
    ("event cwd", sh("echo x > notes.txt", cwd=os.path.join(ROOT, "projects", "sample-rpg")), "deny"),
    ("PowerShell Remove-Item reference", sh("Remove-Item -Recurse projects/sample-rpg/references/x"), "deny"),
    ("PowerShell Out-File loose", sh("Get-Process | Out-File out.txt"), "deny"),
    ("PowerShell -Encoding is not a path",
     sh("Set-Content -Path .scratch/x.txt -Encoding utf8NoBOM -Value hi"), None),
    ("PowerShell -Encoding does not hide the target", sh("Set-Content -Encoding utf8NoBOM -Path out.txt"), "deny"),
    ("rm with a variable: no guessing", sh("for f in *.tmp; do rm $f; done"), None),
    ("script zone: sync_adapters writes .claude", sh("python -I tools/sync_adapters.py > .claude/skills/x/SKILL.md"), None),
    ("script zone: other tool writes .claude", sh("python -I tools/tree.py check > .claude/skills/x/SKILL.md"), "deny"),
    # shell: quotes and code
    ("> inside quotes is not a redirect", sh('python -c "print(1 > 0)"'), None),
    ("> in a commit message", sh('git commit -m "a -> b"'), None),
    ("heredoc python writes a reference",
     sh("python - <<'EOF'\nopen('projects/sample-rpg/references/x.md','w').write('a')\nEOF"), "deny"),
    ("heredoc python with os.path writes scratch",
     sh("python - <<'EOF'\nimport os\nopen(os.path.join('.scratch','x'),'w')\nEOF"), None),
    ("heredoc with > in the body", sh("python - <<'EOF'\nif 1 > 0: print('x')\nEOF"), None),
    ("python writes wip and mentions a guard as data",
     sh(f"python -I - <<'EOF'\nimport json\np='{JOB}/wip/plan.json'\n"
        "d={'files':['tools/guards/tree_guard.py','.agents/tree.toml']}\nopen(p,'w').write(json.dumps(d))\nEOF"), None),
    ("python writes a guard through a variable",
     sh("python - <<'EOF'\nq = 'tools/guards/git_guard.py'\nopen(q, 'w').write('x')\nEOF"), "ask"),
    ("python Path(...).write_text on a reference",
     sh("python - <<'EOF'\nfrom pathlib import Path\nPath('projects/sample-rpg/references/x.md').write_text('a')\nEOF"), "deny"),
    ("python reads a reference and writes scratch",
     sh("python - <<'EOF'\ns=open('projects/sample-rpg/references/glossary.csv').read()\nopen('.scratch/x.csv','w').write(s)\nEOF"), None),
    ("python -c writes a .db", sh('python -c "open(\'projects/sample-rpg/db/tm.db\',\'wb\').write(b\'\')"'), "ask"),
    ("python runtime target falls back to the strict rule",
     sh("python - <<'EOF'\nimport sys\nopen(sys.argv[1],'w')\n# projects/sample-rpg/references/x.md\nEOF"), "deny"),
    ("python mode= write", sh("python - <<'EOF'\nopen('projects/sample-rpg/references/x.md', mode='a')\nEOF"), "deny"),
    ("SQL write on a .db", sh("sqlite3 projects/sample-rpg/db/tm.db 'delete from tm'"), "ask"),
    ("SQL read on a .db", sh("sqlite3 projects/sample-rpg/db/tm.db 'select 1'"), None),
    ("db builder", sh("python -I tools/tm_index.py build"), "ask"),
]


class TreeGuardTest(unittest.TestCase):
    def test_cases(self):
        for name, ev, expected in CASES:
            with self.subTest(name):
                r = tree_guard.evaluate(ev)
                self.assertEqual(r[0] if r else None, expected, r[1] if r else "")

    def test_reasons_point_to_the_map(self):
        r = tree_guard.evaluate(file_ev("write", "junk.txt"))
        self.assertIn("tools/tree.py where junk.txt", r[1])


class UnattendedTest(unittest.TestCase):
    def setUp(self):
        self.before = os.environ.get("HARNESS_UNATTENDED")

    def tearDown(self):
        if self.before is None:
            os.environ.pop("HARNESS_UNATTENDED", None)
        else:
            os.environ["HARNESS_UNATTENDED"] = self.before

    def test_ask_becomes_deny(self):
        os.environ["HARNESS_UNATTENDED"] = "1"
        r = pre_tool_use.decide(file_ev("edit", "tools/guards/git_guard.py"))
        self.assertEqual(r[0], "deny")
        self.assertIn("UNATTENDED", r[1])

    def test_deny_and_allow_do_not_change(self):
        os.environ["HARNESS_UNATTENDED"] = "1"
        self.assertEqual(pre_tool_use.decide(file_ev("write", "junk.txt"))[0], "deny")
        self.assertIsNone(pre_tool_use.decide(file_ev("write", "README.md")))

    def test_attended_ask_stays_ask(self):
        os.environ.pop("HARNESS_UNATTENDED", None)
        if os.path.isfile(os.path.join(ROOT, pre_tool_use.UNATTENDED_FLAG)):
            self.skipTest("the .scratch/unattended flag is on in this checkout")
        self.assertEqual(pre_tool_use.decide(file_ev("edit", "tools/guards/git_guard.py"))[0], "ask")


if __name__ == "__main__":
    unittest.main()
