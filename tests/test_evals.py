"""Offline checks of the routing eval: descriptions, prompt and answer parsing (no network)."""

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_routing", ROOT / "evals/run_routing.py")
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class RoutingEvalTests(unittest.TestCase):
    def test_every_skill_has_a_description_and_a_case(self):
        skills = routing.descriptions()
        cases = json.loads((ROOT / "evals/routing.json").read_text(encoding="utf-8"))["cases"]
        self.assertEqual(sorted(skills), sorted(path.parent.name for path in ROOT.glob("skills/*/SKILL.md")))
        for name, text in skills.items():
            with self.subTest(skill=name):
                self.assertGreater(len(text), 80)
                self.assertIn(name, {case["expect"] for case in cases})

    def test_parse_prefers_the_longest_name(self):
        names = ["spydell", "spydell-qa", "grilling", "spydell-grilling"]
        self.assertEqual(routing.parse("`spydell-qa`", names), "spydell-qa")
        self.assertEqual(routing.parse("Skill: spydell-grilling.", names), "spydell-grilling")
        self.assertEqual(routing.parse("spydell", names), "spydell")
        self.assertEqual(routing.parse("none", names), "none")
        self.assertEqual(routing.parse("I would ask a question first", names), "?")

    def test_prompt_lists_rules_and_all_skills(self):
        text = routing.prompt({"a": "x"}, {"b": "y"}, "RULES", "do it")
        for part in ("RULES", "- a: x", "- b: y", "Request: do it"):
            self.assertIn(part, text)


if __name__ == "__main__":
    unittest.main()
