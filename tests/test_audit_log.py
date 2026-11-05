"""Audit log (tools/audit_log.py): one append-only JSONL file per session, queries by session and by file."""
import io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import audit_log as a  # noqa: E402


class AuditLogTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="audit_")

    def ev(self, kind, **kw):
        return {"source": "claude", "kind": kind, "path": "", "command": "", "root": self.root, "cwd": self.root, **kw}

    def test_line_fields(self):
        now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        d = a.line({"tool_name": "Bash", "session_id": "s/1"}, self.ev("shell", command="echo x > out.txt"),
                   ("deny", "no"), now)
        self.assertEqual((d["session"], d["kind"], d["decision"], d["reason"]), ("s_1", "shell", "deny", "no"))
        self.assertEqual(d["targets"], ["out.txt"])
        self.assertIsNone(a.line({}, self.ev("other"), None))

    def test_write_path_is_relative(self):
        d = a.line({"tool_name": "Write", "session_id": "s"}, self.ev("write", path=os.path.join(self.root, "A", "b.md")), None)
        self.assertEqual((d["path"], d["decision"]), ("a/b.md", "allow"))

    def test_record_and_query(self):
        a.record({"tool_name": "Write", "session_id": "abc"}, self.ev("write", path="docs/x.md"), None)
        a.record({"tool_name": "Bash", "session_id": "abc"}, self.ev("shell", command="rm docs/y.md"), ("ask", "sure?"))
        a.record({"tool_name": "Bash", "session_id": "other"}, self.ev("shell", command="ls"), None)
        logs = list(Path(self.root, ".audit").rglob("*.jsonl"))
        self.assertEqual(sorted(f.name for f in logs), ["abc.jsonl", "other.jsonl"])
        self.assertEqual(Path(self.root, ".audit", ".gitignore").read_text(), "*\n")
        out = io.StringIO()
        with redirect_stdout(out):
            a.cmd_file(self.root, "docs")
        self.assertEqual(out.getvalue().count("abc"), 2)
        out = io.StringIO()
        with redirect_stdout(out):
            a.cmd_session(self.root, "ab", denied_only=True)
        self.assertIn("[ask]", out.getvalue())
        self.assertNotIn("docs/x.md", out.getvalue())

    def test_record_never_raises(self):
        a.record({}, {"kind": "write"}, None)  # no root: swallowed


if __name__ == "__main__":
    unittest.main()
