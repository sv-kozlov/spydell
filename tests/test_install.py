"""Exercise installation effects in temporary directories, never real agent homes."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    """Check repeatability, configuration preservation, conflicts and rollback."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="spydell-install-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.skills = self.base / "agent-skills"
        self.project = self.base / "project"
        self.project.mkdir()
        self.backups = self.base / "backups"

    def invoke(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(ROOT / "install.py"), "--skills-dir", str(self.skills),
             "--backup-dir", str(self.backups), *map(str, args)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_dry_run_and_repeat_install(self):
        self.invoke("--dry-run")
        self.assertFalse(self.skills.exists())
        self.assertFalse(self.backups.exists())
        self.invoke()
        self.assertEqual(len(list(self.skills.glob("*/SKILL.md"))), 7)
        before = {p.relative_to(self.skills): p.read_bytes() for p in self.skills.rglob("*") if p.is_file()}
        result = self.invoke()
        self.assertIn("no changes", result.stdout)
        after = {p.relative_to(self.skills): p.read_bytes() for p in self.skills.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_conflict_preflight_and_backed_up_replacement(self):
        target = self.skills / "spydell"
        target.mkdir(parents=True)
        custom = target / "SKILL.md"
        custom.write_text("local custom version", encoding="utf-8")
        self.invoke(success=False)
        self.assertEqual(custom.read_text(), "local custom version")
        self.assertEqual([p.name for p in self.skills.iterdir()], ["spydell"])
        self.invoke("--replace")
        self.assertEqual(custom.read_bytes(), (ROOT / "skills/spydell/SKILL.md").read_bytes())
        copies = list(self.backups.glob("*/skills/spydell/SKILL.md"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_text(), "local custom version")

    def test_project_merge_preserves_user_data_and_is_repeatable(self):
        config = self.project / "openspec/config.yml"
        config.parent.mkdir()
        original = {"schema": "custom-user-schema", "store": "user-store", "references": ["shared"],
                    "context": "Existing product context", "custom": {"keep": True},
                    "rules": {"proposal": ["User rule"]},
                    "operations": {"apply": {"guidance": ["User guidance"]}}}
        config.write_text(yaml.safe_dump(original), encoding="utf-8")
        existing = self.project / "openspec/changes/existing/proposal.md"
        existing.parent.mkdir(parents=True)
        existing.write_text("existing proposal", encoding="utf-8")
        args = ("--project", self.project, "--project-only")
        self.invoke(*args)
        result = yaml.safe_load(config.read_text())
        for key in ["schema", "store", "references", "custom"]:
            self.assertEqual(result[key], original[key])
        self.assertTrue(result["context"].startswith(original["context"]))
        self.assertIn("User rule", result["rules"]["proposal"])
        self.assertIn("User guidance", result["operations"]["apply"]["guidance"])
        self.assertEqual(existing.read_text(), "existing proposal")
        self.assertFalse(self.skills.exists())
        self.assertTrue((self.project / "openspec/schemas/spydell/schema.yaml").is_file())
        before = config.read_bytes()
        self.invoke(*args)
        self.assertEqual(config.read_bytes(), before)

    def test_invalid_config_does_not_partially_install(self):
        config = self.project / "openspec/config.yaml"
        config.parent.mkdir()
        config.write_text("rules: invalid\n", encoding="utf-8")
        self.invoke("--project", self.project, success=False)
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.project / "openspec/schemas").exists())
        self.assertEqual(config.read_text(), "rules: invalid\n")

    def test_failure_restores_existing_files(self):
        spec = importlib.util.spec_from_file_location("spydell_test_installer", ROOT / "install.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        target = self.skills / "spydell"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("custom content", encoding="utf-8")
        original_copytree = installer.shutil.copytree

        def fail_one_copy(source, destination, *args, **kwargs):
            if Path(source) == ROOT / "skills/spydell-ai-agents":
                raise OSError("Simulated write failure")
            return original_copytree(source, destination, *args, **kwargs)

        argv = ["install.py", "--skills-dir", str(self.skills), "--backup-dir", str(self.backups), "--replace"]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(installer.shutil, "copytree", fail_one_copy):
            with self.assertRaises(OSError):
                installer.main()
        self.assertEqual((target / "SKILL.md").read_text(), "custom content")
        self.assertFalse((self.skills / "spydell-ai-agents").exists())



if __name__ == "__main__":
    unittest.main()
