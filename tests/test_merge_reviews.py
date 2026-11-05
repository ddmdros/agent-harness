"""Fixed-rule merge (tools/merge_reviews.py), on unit cases and on the demo job."""
import os, sys, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from merge_reviews import merge, merge_job  # noqa: E402

DRAFT = {"id": "s1", "text": "A", "alternatives": [{"text": "A2", "note": "alt"}]}


class MergeTest(unittest.TestCase):
    def test_keep(self):
        m = merge(DRAFT, [("mech", {"verdict": "keep"}), ("style", None)])
        self.assertEqual((m["text"], m["origin"], m["warnings"]), ("A", "drafter", []))
        self.assertEqual([a["text"] for a in m["alternatives"]], ["A2"])

    def test_single_change(self):
        m = merge(DRAFT, [("mech", {"verdict": "keep"}), ("style", {"verdict": "change", "proposal": "B"})])
        self.assertEqual((m["text"], m["origin"]), ("B", "style"))
        self.assertEqual(m["alternatives"][0], {"from": "drafter", "text": "A", "note": ""})
        self.assertEqual(m["warnings"], [])

    def test_priority_wins_and_warns(self):
        m = merge(DRAFT, [("mech", {"verdict": "change", "proposal": "M"}),
                          ("style", {"verdict": "change", "proposal": "S", "reason": "flow"})])
        self.assertEqual((m["text"], m["origin"]), ("M", "mech"))
        self.assertIn("S", [a["text"] for a in m["alternatives"]])
        self.assertTrue(any("mech wins by priority" in w for w in m["warnings"]))

    def test_escalate_keeps_text(self):
        m = merge(DRAFT, [("style", {"verdict": "escalate", "proposal": "E", "reason": "gender"})])
        self.assertEqual(m["text"], "A")
        self.assertIn("E", [a["text"] for a in m["alternatives"]])
        self.assertTrue(m["warnings"][0].startswith("style asks for your decision"))

    def test_drafter_flags_and_dedupe(self):
        d = dict(DRAFT, important="check gender", alternatives=[{"text": "B"}])
        m = merge(d, [("mech", {"verdict": "change", "proposal": "B"})])
        self.assertEqual(m["text"], "B")
        self.assertEqual([a["text"] for a in m["alternatives"]], ["A"])  # B is the text now: not repeated
        self.assertEqual(m["warnings"], ["drafter: check gender"])

    def test_demo_job(self):
        r = merge_job(HERE.parent / "projects" / "sample-rpg" / "jobs" / "2026-11-patch" / "wip")
        self.assertEqual(r["summary"], {"segments": 5, "changed_by_review": 2, "need_human": 2})
        seg = {s["id"]: s for s in r["segments"]}
        self.assertEqual(seg["ui_002"]["text"], "Vigor insuficiente")  # glossary fix beats the style proposal


if __name__ == "__main__":
    unittest.main()
