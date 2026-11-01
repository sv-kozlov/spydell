"""Exercise skills/spydell/scripts/dashboard.py on a temporary project, without the OpenSpec CLI."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/spydell/scripts/dashboard.py"

MAP = """# Billing

## Назначение
Invoices are paid online.

## Состояние
Wave 1 in progress, see `openspec/changes/pay-w1`.

## Следующий шаг
Finish S2.

## Принятые решения
| Код | Решение |
| --- | --- |
| R1_Q1 | Card payments first |

## Открытый фронтир
- R2_Q1 Which bank for refunds

## Команда
| Имя | Роль | Класс модели |
| --- | --- | --- |
| Anna | QA | средняя |
"""

ROADMAP = """# Roadmap

## Волны

### S1 — Invoice model
Состояние: ready-for-build
Волна: 1
Change: pay-w1

### S2 — Card checkout
Предшественник: S1
Состояние: needs-decision
Волна: 1
Depends on R2_Q1.

### S3 — Old export (поглощён S2)
Волна: 2

### W3 — Reports
Предшественник: S2
"""

RUN_LOG = """| Время | Волна и срез | Что | Почему | Свидетельство | Результат | Класс модели |
| --- | --- | --- | --- | --- | --- | --- |
| 10:00 | 1 / S1 | spec-review | gate | acceptance.md | PASS | сильная |
"""


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="spydell-dashboard-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.set = self.root / "docs/.spydell/billing"
        self.set.mkdir(parents=True)
        (self.set / "map.md").write_text(MAP, encoding="utf-8")
        (self.set / "roadmap.md").write_text(ROADMAP, encoding="utf-8")
        (self.set / "run-log.md").write_text(RUN_LOG, encoding="utf-8")
        change = self.root / "openspec/changes/pay-w1"
        (change / "specs/billing").mkdir(parents=True)
        for name in ("proposal", "design"):
            (change / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
        (change / "specs/billing/spec.md").write_text("## ADDED Requirements\n", encoding="utf-8")
        (change / "tasks.md").write_text("## 1. Model\n- [x] 1.1 a\n- [ ] 1.2 b\n- [X] 1.3 c\n", encoding="utf-8")
        (change / "acceptance").mkdir()
        (change / "acceptance/qa-report.md").write_text(
            "| Кейс | Статус |\n| --- | --- |\n| Q1 | пройден |\n| Q2 | не пройден |\n", encoding="utf-8")

    def run_dashboard(self, *extra):
        out = self.root / "out/dash.html"
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.set), "--no-openspec", "--out", str(out), *extra],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        return out, json.loads(Path(summary["json"]).read_text(encoding="utf-8"))

    def test_collects_waves_slices_and_change_state(self):
        out, data = self.run_dashboard()
        self.assertEqual([wave["id"] for wave in data["waves"]], ["1", "2", "3"])
        slices = {item["id"]: item for item in data["slices"]}
        self.assertEqual((data["format"], data["version"]), ("spydell-dashboard", 1))
        self.assertEqual(slices["S1"]["status"], "in-progress")
        self.assertEqual(slices["S1"]["stage"], 3)
        self.assertEqual(slices["S1"]["tasks"], {"total": 3, "complete": 2, "pct": 67})
        self.assertEqual(slices["S1"]["gates"]["specs"], "done")
        self.assertEqual(slices["S1"]["gates"]["qaPlan"], "")
        self.assertEqual(slices["S1"]["qa"], {"passed": 1, "failed": 1, "blocked": 0})
        self.assertEqual(slices["S1"]["dependents"], ["S2"])
        self.assertEqual(slices["S2"]["status"], "needs-decision")
        self.assertEqual(slices["S2"]["deps"], ["S1"])
        self.assertEqual(slices["S2"]["openDecisions"], ["R2_Q1"])
        self.assertEqual(slices["S3"]["status"], "dropped")
        self.assertEqual(slices["S3"]["stage"], -1)
        self.assertEqual([wave["status"] for wave in data["waves"]], ["active", "done", "upcoming"])
        self.assertEqual(data["kpis"]["tasksTotal"], 3)
        self.assertEqual(data["kpis"]["frontier"], 1)
        self.assertEqual(slices["W3"]["wave"], "3")
        self.assertEqual(data["frontier"][0]["code"], "R2_Q1")
        self.assertEqual(data["kpis"]["decisions"], 1)
        self.assertEqual(data["team"][0]["имя"], "Anna")
        self.assertEqual(data["runLog"][0]["результат"], "PASS")
        html = out.read_text(encoding="utf-8")
        self.assertNotIn('"__SPYDELL_DATA__"', html)
        self.assertIn('"initiative": "Billing"', html)

    def test_archived_change_and_script_tags_are_safe(self):
        archive = self.root / "openspec/changes/archive"
        archive.mkdir(parents=True)
        (self.root / "openspec/changes/pay-w1").rename(archive / "2026-11-01-pay-w1")
        (self.set / "roadmap.md").write_text(ROADMAP.replace("Invoice model", "Invoice </script> model"),
                                              encoding="utf-8")
        out, data = self.run_dashboard()
        slices = {item["id"]: item for item in data["slices"]}
        self.assertEqual(slices["S1"]["status"], "archived")
        self.assertNotIn("</script> model", out.read_text(encoding="utf-8"))

    def test_roadmap_table_is_the_preferred_source(self):
        table = ("# Roadmap\n\n## Срезы\n\n| ID | Срез | Волна | Состояние | Предшественники | Change |\n"
                 "| --- | --- | --- | --- | --- | --- |\n| A1 | Invoices | 1 | ready-for-build | — | `pay-w1` |\n"
                 "| A2 | Refunds | 2 | candidate | A1 | |\n\n### A2 — Refunds\nWaits for the bank choice.\n")
        (self.set / "roadmap.md").write_text(table, encoding="utf-8")
        out, data = self.run_dashboard()
        slices = {item["id"]: item for item in data["slices"]}
        self.assertEqual(list(slices), ["A1", "A2"])
        self.assertEqual(slices["A1"]["change"]["name"], "pay-w1")
        self.assertEqual(slices["A2"]["deps"], ["A1"])
        self.assertEqual(slices["A2"]["status"], "candidate")
        self.assertIn("bank choice", slices["A2"]["summary"])

    def test_requires_a_set_folder(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.root / "missing")], capture_output=True,
                                text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
