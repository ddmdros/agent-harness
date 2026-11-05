"""Token usage per agent (tools/session_cost.py) on a synthetic transcript."""
import json, os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import session_cost as sc  # noqa: E402


def call(mid, t, inp, cw, cr, out):
    return {"type": "assistant", "timestamp": f"2026-11-05T{t}:00Z", "message": {"id": mid, "model": "m",
            "usage": {"input_tokens": inp, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr,
                      "output_tokens": out}}}


class SessionCostTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="cost_"))
        lines = [call("a", "10:00", 10, 100, 0, 5), call("a", "10:00", 10, 100, 0, 50),  # same call, final usage
                 call("b", "11:00", 0, 0, 1000, 20), {"type": "user"}]
        (self.folder / "s1.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
        sub = self.folder / "s1" / "subagents"
        sub.mkdir(parents=True)
        (sub / "w1.jsonl").write_text(json.dumps(call("c", "11:30", 5, 0, 0, 10)) + "\n")
        (sub / "w1.meta.json").write_text(json.dumps({"description": "style reviewer", "agentType": "style-reviewer"}))

    def test_measure(self):
        r = sc.measure("s1", folder=self.folder)
        main, worker = r["agents"]
        self.assertEqual((main["calls"], main["output"], main["cache_read"]), (2, 70, 1000))
        self.assertEqual((main["context_start"], main["context_end"]), (110, 1000))
        self.assertEqual((worker["name"], worker["type"]), ("style reviewer", "style-reviewer"))
        # equivalent: main = 10 + 125 + 100 + 350 = 585; worker = 5 + 50 = 55
        self.assertEqual(r["total"]["equivalent"], 640)

    def test_since_trims_main_agent(self):
        r = sc.measure("s1", since="10:30", folder=self.folder)
        self.assertEqual(r["agents"][0]["calls"], 1)


if __name__ == "__main__":
    unittest.main()
