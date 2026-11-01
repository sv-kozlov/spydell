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


class LinkTests(unittest.TestCase):
    """Relative markdown links in skills and docs resolve to existing files."""

    def test_relative_links_resolve(self):
        import re
        broken = []
        for path in [*ROOT.glob("skills/**/*.md"), *ROOT.glob("docs/*.md"), ROOT / "README.md", ROOT / "INSTALL.md"]:
            text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
            for target in re.findall(r"\]\(([^)#\s]+)", text):
                if re.match(r"^[a-z]+://|^mailto:", target):
                    continue
                if not (path.parent / target).exists():
                    broken.append(f"{path.relative_to(ROOT)} -> {target}")
        self.assertEqual(broken, [])


class SkillInventoryTests(unittest.TestCase):
    """Every skill directory has Codex metadata and a row in the README; descriptions name no stale count."""

    def test_skills_listed(self):
        import re
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for skill in sorted(path.name for path in (ROOT / "skills").iterdir() if (path / "SKILL.md").exists()):
            with self.subTest(skill=skill):
                self.assertTrue((ROOT / "skills" / skill / "agents/openai.yaml").exists())
                self.assertIn(f"`{skill}`", readme)
        counts = re.compile(r"\b(восемь|девять|десять|одиннадцать|двенадцать|тринадцать)\s+навык", re.I)
        for path in (ROOT / "INSTALL.md", ROOT / ".claude-plugin/marketplace.json", ROOT / ".claude-plugin/plugin.json",
                     ROOT / ".codex-plugin/plugin.json"):
            with self.subTest(file=path.name):
                self.assertIsNone(counts.search(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
