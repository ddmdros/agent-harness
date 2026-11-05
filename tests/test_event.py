"""Event adapter (tools/guards/event.py) and the hook entry point, end to end."""
import json, os, subprocess, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools", "guards"))
import event  # noqa: E402

ENTRY = os.path.join(HERE, "..", "tools", "guards", "pre_tool_use.py")


class NormalizeTest(unittest.TestCase):
    def test_claude_write(self):
        ev = event.normalize({"tool_name": "Write", "tool_input": {"file_path": "a.md"}, "cwd": "/x"})
        self.assertEqual((ev["source"], ev["kind"], ev["path"], ev["cwd"]), ("claude", "write", "a.md", "/x"))

    def test_claude_bash(self):
        ev = event.normalize({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertEqual((ev["kind"], ev["command"]), ("shell", "ls"))

    def test_claude_read_is_other(self):
        self.assertEqual(event.normalize({"tool_name": "Read", "tool_input": {}})["kind"], "other")

    def test_antigravity(self):
        ev = event.normalize({"toolCall": {"name": "replace_file_content", "args": {"TargetFile": "b.py"}}})
        self.assertEqual((ev["source"], ev["kind"], ev["path"]), ("antigravity", "edit", "b.py"))
        ev = event.normalize({"toolCall": {"name": "run_command", "args": {"CommandLine": "rm x"}}})
        self.assertEqual((ev["kind"], ev["command"]), ("shell", "rm x"))


class RenderTest(unittest.TestCase):
    def test_claude_protocol(self):
        ev = {"source": "claude"}
        self.assertEqual(event.render(ev, None), ("", "", 0))
        self.assertEqual(event.render(ev, ("deny", "no")), ("", "no", 2))
        out, _, code = event.render(ev, ("ask", "sure?"))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_antigravity_protocol(self):
        ev = {"source": "antigravity"}
        self.assertEqual(event.render(ev, None)[0], "{}")
        self.assertEqual(json.loads(event.render(ev, ("ask", "x"))[0])["decision"], "force_ask")
        self.assertEqual(json.loads(event.render(ev, ("deny", "x"))[0])["decision"], "deny")


class EntryPointTest(unittest.TestCase):
    def run_hook(self, payload):
        env = {k: v for k, v in os.environ.items() if k != "HARNESS_UNATTENDED"}
        return subprocess.run([sys.executable, "-I", ENTRY], input=json.dumps(payload), capture_output=True,
                              text=True, encoding="utf-8", env=env)

    def test_claude_deny_exits_2(self):
        r = self.run_hook({"tool_name": "Write", "tool_input": {"file_path": "junk.txt"}, "session_id": "test-e2e"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKED", r.stderr)

    def test_claude_read_passes(self):
        r = self.run_hook({"tool_name": "Read", "tool_input": {"file_path": "README.md"}})
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_antigravity_ask(self):
        r = self.run_hook({"toolCall": {"name": "edit_file", "args": {"Path": ".agents/tree.toml"}}})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["decision"], "force_ask")

    def test_bad_json_never_blocks(self):
        r = subprocess.run([sys.executable, "-I", ENTRY], input="not json", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
