"""Exercise skills/spydell/scripts/check.py on temporary fixtures."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/spydell/scripts/check.py"

MAP = """# Work

## Назначение
Done state.

## Состояние
Wave 1.

## Принятые решения
| Код | Решение |
| --- | --- |
| R1_Q1 | First |
| R1_Q2 | Second, see [roadmap](roadmap.md) |

## Открытый фронтир
- R2_Q1 open choice
"""


class CheckScriptTests(unittest.TestCase):
    """Each subcommand accepts a valid artifact and reports a concrete issue for a broken one."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="spydell-check-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def write(self, name, text):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def check(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if report["valid"] else 1)
        return report

    def codes(self, report):
        return {item["code"] for item in report["issues"]}

    def test_map(self):
        self.write("roadmap.md", "# Roadmap\n")
        self.assertTrue(self.check("map", self.write("map.md", MAP))["valid"])
        broken = MAP.replace("R1_Q2", "R1_Q1").replace("## Состояние", "## Статус") + "\nR3-Q4 and [x](missing.md)\n"
        self.assertEqual(self.codes(self.check("map", self.write("map.md", broken))),
                         {"map.section", "map.code", "map.duplicate", "map.link"})
        grouped = MAP.replace("| R1_Q2 | Second", "Decisions from another round.\n\n| R1_Q1 | Second")
        self.assertEqual(self.codes(self.check("map", self.write("map.md", grouped))), {"map.duplicate"})

    def test_several_paths(self):
        self.write("a/roadmap.md", "# Roadmap\n")
        self.write("b/roadmap.md", "# Roadmap\n")
        good = self.write("a/map.md", MAP)
        bad = self.write("b/map.md", MAP.replace("## Состояние", "## Статус"))
        report = self.check("map", good, bad)
        self.assertEqual({item["location"] for item in report["issues"]}, {str(bad)})

    def test_roadmap(self):
        self.write("map.md", MAP)
        good = "## Slices\n\n### S1 — base\nСостояние: ready-for-build\n\n### S2 — next\nПредшественник: S1\n"
        self.assertTrue(self.check("roadmap", self.write("roadmap.md", good))["valid"])
        broken = ("### S1 — a\nПредшественник: S2\n\n### S2 — b\nПредшественник: S1, S9\n\n"
                  "### S3 — c\nСостояние: ready-for-build\nЖдёт R2_Q1\n")
        self.assertEqual(self.codes(self.check("roadmap", self.write("roadmap.md", broken))),
                         {"roadmap.cycle", "roadmap.unknown", "roadmap.ready"})

    def test_acceptance(self):
        good = "".join(f"## {name}\nok\n\n" for name in ["Ревизии", "Тесты", "Ревью по осям", "QA",
                                                          "Повторившиеся классы находок"])
        good += "## Не выполнено\n- Стенд — владелец: Иван; следующий шаг: поднять стенд\n"
        self.assertTrue(self.check("acceptance", self.write("acceptance.md", good))["valid"])
        broken = good.replace("## QA\n", "## Прогон\n").replace("владелец: Иван; ", "")
        self.assertEqual(self.codes(self.check("acceptance", self.write("acceptance.md", broken))),
                         {"acceptance.section", "acceptance.open"})

    def test_qa(self):
        good = ("| ID | Статус | Доказательство |\n| --- | --- | --- |\n"
                "| QA-1 | пройден | screenshot.png |\n| QA-2 | заблокирован | |\n")
        self.assertTrue(self.check("qa", self.write("qa-report.md", good))["valid"])
        broken = good.replace("screenshot.png", "").replace("заблокирован", "ок")
        self.assertEqual(self.codes(self.check("qa", self.write("qa-report.md", broken))), {"qa.evidence", "qa.status"})
        escaped = good.replace("screenshot.png", "https://ci\\|build.png")
        self.assertTrue(self.check("qa", self.write("qa-report.md", escaped))["valid"])
        raw = good.replace("screenshot.png", "https://ci|build.png")
        self.assertEqual(self.codes(self.check("qa", self.write("qa-report.md", raw))), {"qa.row"})

    def test_trace(self):
        change = self.base / "change"
        self.write("change/specs/cap/spec.md",
                   "## ADDED Requirements\n\n### Requirement: Export works\nText.\n\n#### Scenario: Export shown\n"
                   "- WHEN x\n- THEN y\n\n## REMOVED Requirements\n\n### Requirement: Legacy export\n")
        self.write("change/acceptance/spec-matrix.md",
                   "| Requirement | Scenario | Где реализовано | Тест | Статус |\n| --- | --- | --- | --- | --- |\n"
                   "| Export works | Export shown | export.py | test_export | покрыто тестом |\n")
        self.write("change/acceptance/qa-plan.md", "| ID | Scenario |\n| --- | --- |\n| QA-1 | Export shown |\n")
        self.assertTrue(self.check("trace", change)["valid"])
        self.write("change/acceptance/qa-plan.md", "| ID | Scenario |\n| --- | --- |\n| QA-1 | Export hidden |\n")
        self.write("change/specs/cap/spec.md",
                   "## ADDED Requirements\n\n### Requirement: Export works\n\n#### Scenario: Export shown\n\n"
                   "### Requirement: Import works\n")
        self.assertEqual(self.codes(self.check("trace", change)), {"trace.uncovered", "trace.scenario"})


if __name__ == "__main__":
    unittest.main()
