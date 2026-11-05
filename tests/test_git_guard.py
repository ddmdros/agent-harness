"""Git guard (tools/guards/git_guard.py): commit checks, push by visibility, no public repositories."""
import os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "guards"))
import git_guard  # noqa: E402
from event import ROOT  # noqa: E402


def sh(command):
    return {"source": "claude", "kind": "shell", "path": "", "command": command, "root": ROOT, "cwd": ROOT}


def decision(command, visibility="PRIVATE", allowed=("PRIVATE",)):
    with mock.patch.object(git_guard, "visibility", return_value=visibility), \
         mock.patch.object(git_guard, "allowed", return_value=set(allowed)):
        r = git_guard.evaluate(sh(command))
    return r[0] if r else None


class GitGuardTest(unittest.TestCase):
    def test_commit_is_allowed(self):
        self.assertIsNone(decision('git add tools/tree.py && git commit -m "fix: map"'))

    def test_skipping_hooks_is_denied(self):
        self.assertEqual(decision('git commit --no-verify -m "x"'), "deny")
        self.assertEqual(decision('git commit -n -m "x"'), "deny")
        self.assertEqual(decision("git push --no-verify"), "deny")

    def test_push_dry_run_flag_is_not_no_verify(self):
        self.assertEqual(decision("git push -n origin main"), "ask")

    def test_force_add_is_denied(self):
        self.assertEqual(decision("git add -f secrets.db"), "deny")
        self.assertEqual(decision("git -C repo add --force x"), "deny")

    def test_push_by_visibility(self):
        self.assertEqual(decision("git push -u origin main", "PRIVATE"), "ask")
        self.assertEqual(decision("git push origin main", "PUBLIC"), "deny")
        self.assertEqual(decision("git push origin main", None), "deny")  # fail closed
        self.assertEqual(decision("git push origin main", "PUBLIC", ("PRIVATE", "PUBLIC")), "ask")

    def test_making_a_repository_public(self):
        self.assertEqual(decision("gh repo create my-repo --public"), "deny")
        self.assertEqual(decision("gh repo create my-repo"), "deny")
        self.assertIsNone(decision("gh repo create my-repo --private"))
        self.assertEqual(decision("gh repo edit --visibility public"), "deny")
        self.assertEqual(decision("gh api -X PATCH repos/o/r -f visibility=internal"), "deny")
        self.assertIsNone(decision("gh repo edit --visibility public", allowed=("PRIVATE", "PUBLIC")))

    def test_mentions_inside_text_do_not_count(self):
        self.assertIsNone(decision("echo 'then run git push origin main'"))

    def test_known_false_positive_fails_closed(self):
        # The guard reads the command text, not a parsed git invocation: a commit message that quotes the flag
        # is denied too. Accepted on purpose: the error is on the safe side and the agent can reword.
        self.assertEqual(decision('git commit -m "docs: explain --no-verify"'), "deny")


if __name__ == "__main__":
    unittest.main()
