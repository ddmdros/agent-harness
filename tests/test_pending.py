"""Decision and question queue (tools/pending.py). Writes to a temporary folder only."""
import json, os, sys, tempfile, threading, unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import pending as p  # noqa: E402


class PendingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pending_"))
        self.D, self.Q = self.tmp / "decisions.json", self.tmp / "questions.json"

    def test_ids_and_initial_status(self):
        a = p.record_decision("format X", "because Y", task="T1", session="s1", path=self.D)
        b = p.record_decision("name Z", "because W", session="s2", path=self.D)
        self.assertEqual((a["id"], b["id"]), ("D001", "D002"))
        self.assertEqual((a["status"], a["answer"]), ("awaiting approval", None))
        q = p.record_question("which field?", "test it", path=self.Q)
        self.assertEqual((q["id"], q["status"]), ("Q001", "open"))

    def test_answer(self):
        p.record_decision("a", "b", path=self.D)
        p.record_decision("c", "d", path=self.D)
        self.assertEqual(p.answer("D001", "ok", path=self.D)["status"], "approved")
        self.assertEqual(p.answer("d002", "change", "use E", path=self.D)["answer"], "use E")
        self.assertEqual(p.open_items("D", path=self.D), [])
        self.assertEqual(len(p.open_items("D", include_answered=True, path=self.D)), 2)
        p.record_question("q", "h", path=self.Q)
        self.assertEqual(p.answer("Q001", "ok", "it is X", path=self.Q)["status"], "resolved")

    def test_bad_answers(self):
        p.record_decision("a", "b", path=self.D)
        with self.assertRaises(ValueError):
            p.answer("D001", "maybe", path=self.D)
        with self.assertRaises(ValueError):
            p.answer("D999", "ok", path=self.D)
        with self.assertRaises(ValueError):
            p.answer("X001", "ok", path=self.D)

    def test_filter_by_session(self):
        p.record_decision("a", "b", session="abc123", path=self.D)
        p.record_decision("c", "d", session="xyz", path=self.D)
        self.assertEqual([i["id"] for i in p.open_items("D", session="abc", path=self.D)], ["D001"])

    def test_parallel_writers_lose_nothing(self):
        threads = [threading.Thread(target=p.record_decision, args=(f"d{i}", "w"), kwargs={"path": self.D})
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        ids = [i["id"] for i in json.loads(self.D.read_text(encoding="utf-8"))["decisions"]]
        self.assertEqual(sorted(ids), [f"D{n:03d}" for n in range(1, 21)])
        self.assertFalse(any(self.tmp.glob("*.lock")))

    def test_cli_requires_why(self):
        self.assertEqual(p.main(["decision", "x"]), 1)


if __name__ == "__main__":
    unittest.main()
