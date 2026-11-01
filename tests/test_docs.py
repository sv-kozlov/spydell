"""Guard documentation invariants that reviews flagged more than once."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ArtifactPathTests(unittest.TestCase):
    """Wave acceptance artifacts are named for both layouts: with an OpenSpec change and without one."""

    def test_acceptance_artifacts_have_both_paths(self):
        text = (ROOT / "skills/spydell/references/artifacts.md").read_text(encoding="utf-8")
        for name in ("qa-plan.md", "qa-report.md", "spec-matrix.md"):
            with self.subTest(artifact=name):
                self.assertIn(f"`acceptance/{name}`", text)
                self.assertIn(f"`waves/<wave>/{name}`", text)


if __name__ == "__main__":
    unittest.main()
