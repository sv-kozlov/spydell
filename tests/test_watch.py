"""Exercise skills/spydell/scripts/watch.py with second-scale timings."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/spydell/scripts/watch.py"
LOG = "| Время | Волна | Что |\n| --- | --- | --- |\n| 10:00 | — | старт |\n"


class WatchScriptTests(unittest.TestCase):
    """The watcher exits with the event the lead must act on: a new log row, a stall or a planned restart."""

    def setUp(self):
        self.addCleanup(self.drop_state)
        self.temporary = tempfile.TemporaryDirectory(prefix="spydell-watch-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        (self.base / "run-log.md").write_text(LOG, encoding="utf-8")

    def drop_state(self):
        key = hashlib.sha256(str(self.base.resolve()).encode()).hexdigest()[:16]
        (Path(tempfile.gettempdir()) / f"spydell-watch-{key}.json").unlink(missing_ok=True)

    def watch(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.base), "--interval", "0.1", *args],
                                capture_output=True, text=True, timeout=30)
        return result.returncode, json.loads(result.stdout)

    def test_new_row(self):
        def append():
            time.sleep(0.5)
            with (self.base / "run-log.md").open("a", encoding="utf-8") as log:
                log.write("| 10:01 | 1 | волна 1 завершена |\n")
        threading.Thread(target=append).start()
        code, report = self.watch("--stuck-after", "1", "--max-runtime", "1")
        self.assertEqual((code, report["event"]), (0, "log"))
        self.assertEqual(report["new_rows"][0]["что"], "волна 1 завершена")

    def test_stuck(self):
        code, report = self.watch("--stuck-after", "0.01", "--max-runtime", "1")
        self.assertEqual((code, report["event"]), (2, "stuck"))

    def repo(self, name):
        repo = self.base / name
        repo.mkdir()
        git = lambda *args: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                                           check=True, capture_output=True)
        git("init", "-q")
        (repo / "file.txt").write_text("start", encoding="utf-8")
        git("add", "file.txt")
        git("commit", "-qm", "start")
        return repo

    def keep_editing(self, path, seconds=2.5):
        def edit():
            for step in range(int(seconds / 0.25)):
                path.write_text(str(step), encoding="utf-8")
                time.sleep(0.25)
        thread = threading.Thread(target=edit)
        thread.start()
        self.addCleanup(thread.join)

    def test_edits_keep_alive_until_restart(self):
        repo = self.repo("repo")
        self.keep_editing(repo / "новый.py")  # untracked, quoted by git; status stays, content keeps changing
        code, report = self.watch("--worktree", str(repo), "--stuck-after", "0.02", "--max-runtime", "0.03")
        self.assertEqual((code, report["event"]), (3, "restart"))

    def test_pulse_keeps_a_long_check_alive(self):
        repo = self.repo("repo")
        git_dir = Path(subprocess.run(["git", "-C", str(repo), "rev-parse", "--absolute-git-dir"],
                                      capture_output=True, text=True).stdout.strip())
        self.keep_editing(git_dir / "spydell-pulse")  # only the pulse moves; the working tree stays clean
        code, report = self.watch("--worktree", str(repo), "--stuck-after", "0.02", "--max-runtime", "0.03")
        self.assertEqual((code, report["event"]), (3, "restart"))

    def test_stuck_worktree_among_active(self):
        active, idle = self.repo("active"), self.repo("idle")
        self.keep_editing(active / "file.txt")
        code, report = self.watch("--worktree", str(active), "--worktree", str(idle), "--stuck-after", "0.02",
                                  "--max-runtime", "1")
        self.assertEqual((code, report["event"], report["stuck"]), (2, "stuck", [str(idle.resolve())]))

    def test_restart_keeps_idle_time(self):
        repo = self.repo("repo")
        first, _ = self.watch("--worktree", str(repo), "--stuck-after", "0.05", "--max-runtime", "0.02")
        # without the saved timer the second run would restart at 3.6 s; with it the idle time crosses 3 s first
        second, report = self.watch("--worktree", str(repo), "--stuck-after", "0.05", "--max-runtime", "0.06")
        self.assertEqual((first, second, report["event"]), (3, 2, "stuck"))


if __name__ == "__main__":
    unittest.main()
