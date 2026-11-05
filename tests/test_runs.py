"""Worker runs (tools/runs.py): unique names, exclusive writes, latest run per worker."""
import os, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import runs  # noqa: E402


class RunsTest(unittest.TestCase):
    def setUp(self):
        self.job = Path(tempfile.mkdtemp(prefix="runs_")) / "job"
        self.wip = self.job / "wip"
        (self.wip / "batch1").mkdir(parents=True)

    def test_wip_of(self):
        self.assertEqual(runs.wip_of(self.wip / "batch1"), (self.wip.resolve(), "batch1"))
        self.assertEqual(runs.wip_of(self.wip)[1], "")
        with self.assertRaises(ValueError):
            runs.wip_of(self.job)

    def test_name_format(self):
        p = runs.name(self.wip / "batch1", "style reviewer", "s/1", datetime(2026, 11, 5, 9, 30, 0))
        self.assertEqual(p.relative_to(self.wip.resolve()).as_posix(), "runs/batch1/20261105-093000-s_1-style_reviewer.json")

    def test_save_never_overwrites(self):
        a = runs.save(self.wip, "drafter", "one", "s")
        b = runs.save(self.wip, "drafter", "two", "s")
        self.assertNotEqual(a, b)
        self.assertEqual((a.read_text(), b.read_text()), ("one", "two"))
        self.assertEqual(runs.latest(self.wip, "drafter"), b)

    def test_latest_with_many_collisions(self):
        # Same second, same worker: x.json, x.2.json ... x.10.json. Name order alone would pick x.9.json or x.json.
        paths = [runs.save(self.wip, "drafter", str(i), "s") for i in range(11)]
        if len({p.name[:15] for p in paths}) == 1:  # all in the same second (the usual case)
            self.assertEqual(runs.latest(self.wip, "drafter").read_text(), "10")

    def test_runs_filter_by_worker(self):
        runs.save(self.wip, "drafter", "{}", "s")
        runs.save(self.wip, "style-reviewer", "{}", "s")
        self.assertEqual(len(runs.runs(self.wip)), 2)
        self.assertEqual(len(runs.runs(self.wip, "style-reviewer")), 1)
        self.assertIsNone(runs.latest(self.wip, "mechanics-reviewer"))


if __name__ == "__main__":
    unittest.main()
