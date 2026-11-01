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

    def test_roadmap_table(self):
        self.write("map.md", MAP)
        table = ("## Срезы\n\n| ID | Срез | Волна | Состояние | Предшественники | Change |\n"
                 "| --- | --- | --- | --- | --- | --- |\n"
                 "| S1 | base | 1 | ready-for-build | — | `s1` |\n| S2 | next | 2 | candidate | S1 | |\n\n"
                 "### S2 — next\nПодробности.\n")
        self.assertTrue(self.check("roadmap", self.write("roadmap.md", table))["valid"])
        broken = table.replace("| S1 | base | 1 | ready-for-build | — |", "| S1 | base | 1 | ready-for-build | S2 |")
        broken = broken.replace("Подробности.", "Ждёт R2_Q1").replace("| S2 | next | 2 | candidate |", "| S2 | next | 2 | ready-for-build |")
        self.assertEqual(self.codes(self.check("roadmap", self.write("roadmap.md", broken))), {"roadmap.cycle", "roadmap.ready"})
        duplicate = table.replace("| S2 | next | 2 | candidate | S1 | |", "| S2 | next | 2 | candidate | S1 | |\n| S2 | again | 2 | candidate | | |")
        self.assertEqual(self.codes(self.check("roadmap", self.write("roadmap.md", duplicate))), {"roadmap.duplicate"})
        planned = (table.replace("| Change |", "| Change | Исполнение | Параллельно с |").replace("| --- |\n| S1", "| --- | --- | --- |\n| S1")
                   .replace("| `s1` |", "| `s1` | средняя/высокий | S3 |").replace("| S2 | next | 2 | candidate | S1 | |", "| S2 | next | 2 | candidate | S1 | | | |")
                   + "\n### S3 — side\nВолна: 1\nИсполнение: лёгкая/низкий\nПараллельно с: S1\n")
        self.assertTrue(self.check("roadmap", self.write("roadmap.md", planned))["valid"])
        wrong = planned.replace("лёгкая/низкий", "opus/high").replace("Параллельно с: S1", "Параллельно с: S2, S9, S3")
        self.assertEqual(self.codes(self.check("roadmap", self.write("roadmap.md", wrong))),
                         {"roadmap.execution", "roadmap.parallel"})
        chain = ("### S1 — a\nВолна: 1\nПараллельно с: S3\n### S2 — b\nВолна: 1\nПредшественник: S1\n"
                 "### S3 — c\nВолна: 1\nПредшественник: S2\n")
        self.assertEqual(self.codes(self.check("roadmap", self.write("roadmap.md", chain))), {"roadmap.parallel"})
        cleared = ("## Срезы\n\n| ID | Срез | Волна | Параллельно с |\n| --- | --- | --- | --- |\n| S1 | a | 1 | — |\n\n"
                   "### S1 — a\nПараллельно с: S9\n")
        self.assertTrue(self.check("roadmap", self.write("roadmap.md", cleared))["valid"])
        foreign = "# Roadmap\n\n## Q1\n- Epic A: login\n- Epic B: billing, depends on A\n"
        self.assertEqual(self.codes(self.check("roadmap", self.write("roadmap.md", foreign))), {"roadmap.empty"})

    def test_acceptance(self):
        good = "".join(f"## {name}\nok\n\n" for name in ["Ревизии", "Тесты", "Ревью по осям", "QA",
                                                          "Повторившиеся классы находок"])
        good += "## Не выполнено\n- Стенд — владелец: Иван; следующий шаг: поднять стенд\n"
        self.assertTrue(self.check("acceptance", self.write("acceptance.md", good))["valid"])
        broken = good.replace("## QA\n", "## Прогон\n").replace("владелец: Иван; ", "")
        self.assertEqual(self.codes(self.check("acceptance", self.write("acceptance.md", broken))),
                         {"acceptance.section", "acceptance.open"})
        self.write("qa-report.md", "| ID | Статус | Доказательство |\n| --- | --- | --- |\n"
                   "| QA-1 | пройден | a.png |\n| QA-2 | не пройден | |\n| QA-12 | заблокирован | |\n")
        self.assertEqual(self.codes(self.check("acceptance", self.write("acceptance.md", good))), {"acceptance.qa"})
        listed = good + "- QA-2 падает на Safari — владелец: Иван; следующий шаг: исправить\n" \
                        "- QA-12 нет стенда — владелец: Пётр; следующий шаг: поднять стенд\n"
        self.assertTrue(self.check("acceptance", self.write("acceptance.md", listed))["valid"])
        self.write("qa-report.md", "| ID | Статус | Доказательство |\n| --- | --- | --- |\n"
                   "| QA-2 | не пройден | |\n| QA-2 | пройден | b.png |\n")
        self.assertTrue(self.check("acceptance", self.write("acceptance.md", good))["valid"])

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

    def test_run(self):
        claude = ('claude -p "<бриф>" --model <модель> --permission-mode acceptEdits '
                  '--allowedTools "Edit Bash(git commit:*)" --disallowedTools "Bash(git push:*)"')
        codex = "codex exec -m <модель> -s workspace-write -C <worktree> -o <ответ> <бриф>"
        self.write("set/map.md", MAP + "\n## Контракт прогона\n\n```bash\n" + claude + "\n" + codex + "\n```\n\n"
                   "Desktop: `start_session permission_mode=acceptEdits`.\n")
        header = "| Время | Волна | Что | Почему | Свидетельство | Результат | Класс модели |\n" + "| --- " * 7 + "|\n"
        row = "| 10:00 | 1 | запуск волны | бриф | `{}` | ok | лёгкая |\n"
        actual = "CLAUDE_CODE_TMPDIR=/tmp/w1 " + claude.replace("<бриф>", "волна 1").replace("<модель>", "haiku")
        good = (header + row.format(actual) + row.format("start_session permission_mode=acceptEdits model=haiku")
                + row.format("/opt/homebrew/bin/codex exec -m gpt -s workspace-write -C /tmp/w2 -o /tmp/a.md 'волна 2'"))
        self.write("set/run-log.md", good + row.format(actual + " --effort high")
                   + row.format("codex exec -m gpt -s workspace-write -c model_reasoning_effort=low -C /tmp/w2 -o /tmp/a.md x"))
        self.assertTrue(self.check("run", self.base / "set")["valid"])
        self.write("set/run-log.md", good)
        widened = [actual.replace("acceptEdits", "bypassPermissions"),
                   actual.replace('"Edit Bash(git commit:*)"', '"Edit Bash(git commit:*)" Bash'),
                   "env " + actual + " --dangerously-skip-permissions",
                   "codex exec -m gpt -s workspace-write --ignore-rules -C /tmp/w2 -o /tmp/a.md x",
                   "codex exec -p unsafe -m gpt -s workspace-write -C /tmp/w2 -o /tmp/a.md x",
                   "start_session permission_mode=bypassPermissions"]
        for line in widened:
            self.write("set/run-log.md", good + row.format(line))
            self.assertEqual(self.codes(self.check("run", self.base / "set")), {"run.permissions"}, line)
        substituted = actual.replace('"волна 1"', '"$(claude --dangerously-skip-permissions -p x)"')
        self.write("set/run-log.md", good + row.format("bash -c 'claude -p x'") + row.format(substituted)
                   + "| 10:09 | 2 | запуск волны | бриф | вручную | ok | лёгкая |\n")
        self.assertEqual(self.codes(self.check("run", self.base / "set")), {"run.unparsed", "run.shell", "run.evidence"})
        other = "other-agent --sandbox workspace-write --model <модель> <бриф>"
        self.write("models.md", "| Модель | Среда и запуск | Класс |\n| --- | --- | --- |\n"
                   f"| local | `{other}` | средняя |\n| big | `claude -p` | сильная |\n")
        self.write("set/map.md", MAP + "\n## Контракт прогона\n\n```bash\n" + claude + "\n" + other + "\n```\n")
        launched = row.format("other-agent --sandbox workspace-write --model q 'волна 3'")
        self.write("set/run-log.md", good.split("| 10:00")[0] + launched)
        self.assertTrue(self.check("run", self.base / "set")["valid"])
        self.write("set/run-log.md", good.split("| 10:00")[0] + launched.replace("workspace-write", "danger-full-access"))
        self.assertEqual(self.codes(self.check("run", self.base / "set")), {"run.permissions"})
        hidden = launched.replace("` | ok", "` `bash -c 'other-agent --sandbox danger-full-access x'` | ok")
        self.write("set/run-log.md", good.split("| 10:00")[0] + hidden)
        self.assertEqual(self.codes(self.check("run", self.base / "set")), {"run.unparsed"})
        npx = "npx -y @google/gemini-cli --sandbox --model <модель> <бриф>"
        self.write("models.md", f"| Модель | Среда и запуск | Класс |\n| --- | --- | --- |\n| g | `{npx}` | средняя |\n")
        self.write("set/map.md", MAP + "\n## Контракт прогона\n\n```bash\n" + npx + "\n```\n")
        self.write("set/run-log.md", good.split("| 10:00")[0] + row.format("npx -y @google/gemini-cli --sandbox --model g 'в'"))
        self.assertTrue(self.check("run", self.base / "set")["valid"])
        self.write("set/run-log.md", good.split("| 10:00")[0] + row.format("npx -y attacker-package --sandbox --model g 'в'"))
        self.assertEqual(self.codes(self.check("run", self.base / "set")), {"run.launch"})
        glued = 'claude -p x --permission-mode acceptEdits --allowedTools Read "<бриф>"'
        self.write("set/map.md", MAP + "\n## Контракт прогона\n\n```bash\n" + glued + "\n```\n")
        self.write("set/run-log.md", good.split("| 10:00")[0])
        self.assertEqual(self.codes(self.check("run", self.base / "set")), {"run.brief"})
        self.write("models.md", "")
        self.write("set/map.md", MAP + "\n## Контракт прогона\n\n```bash\n" + claude + "\n"
                   + "codex exec -m <модель> -c sandbox_mode=danger-full-access -c sandbox_mode=workspace-write\n"
                   + '"/opt/homebrew/bin/gemini" --sandbox --model <модель> <бриф>\n```\n')
        bypasses = [actual + ' & eval "claude --dangerously-skip-permissions -p x"',
                    actual + ' > >(eval x)',
                    "codex exec -m g -c sandbox_mode=workspace-write -c sandbox_mode=danger-full-access"]
        for line in bypasses:
            self.write("set/run-log.md", good.split("| 10:00")[0] + row.format(line))
            self.assertFalse(self.check("run", self.base / "set")["valid"], line)
        self.write("set/run-log.md", good.split("| 10:00")[0]
                   + row.format("bash -c 'gemini --yolo -p x'"))
        self.assertEqual(self.codes(self.check("run", self.base / "set")), {"run.unparsed", "run.evidence"})
        self.write("set/map.md", MAP)
        self.assertEqual(self.codes(self.check("run", self.base / "set")), {"run.contract"})

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
        self.write("change/specs/cap/spec.md",
                   "## ADDED Requirements\n\n### Requirement: Export works\n\n#### Scenario: Export shown\n\n"
                   "#### Scenario: Export fails\n")
        self.write("change/acceptance/qa-plan.md", "| ID | Scenario |\n| --- | --- |\n| QA-1 | Export shown |\n")
        self.assertEqual(self.codes(self.check("trace", change)), {"trace.scenario-uncovered"})
        self.write("change/specs/cap/spec.md",
                   "## ADDED Requirements\n\n### Requirement: Export works\n\n#### Scenario: Unauthorized\n\n"
                   "### Requirement: Import works\n\n#### Scenario: Unauthorized\n")
        self.write("change/acceptance/spec-matrix.md",
                   "| Requirement | Scenario | Где | Тест | Статус |\n| --- | --- | --- | --- | --- |\n"
                   "| Export works | Unauthorized | e.py | t | покрыто тестом |\n| Import works | | i.py | t | покрыто тестом |\n")
        self.write("change/acceptance/qa-plan.md", "| ID | Scenario |\n| --- | --- |\n| QA-1 | Unauthorized |\n")
        self.assertEqual(self.codes(self.check("trace", change)), {"trace.scenario-uncovered"})


if __name__ == "__main__":
    unittest.main()
