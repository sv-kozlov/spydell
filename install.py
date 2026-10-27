#!/usr/bin/env python3
"""Install Spydell skills without a plugin manager and add the Spydell schema to an OpenSpec project."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid


ROOT = Path(__file__).resolve().parent

# Wording that a later Spydell revision replaced, matched against entries already in a project config.
# A matching entry is dropped when the incoming config no longer carries that wording, so reinstalling
# never leaves the superseded rule beside the current one. Each marker must be absent from the new text.
SUPERSEDED_MARKERS = (
    "Fix every confirmed finding and rerun checks",
    "Re-review until all findings are resolved",
    "Do not cap review rounds or treat deferral as a fix",
    "rechecked; refuted findings need evidence",
    "reconciliation. Check the shared wave acceptance report",
)


def tree_hashes(path):
    """Return file hashes without accepting symbolic links."""
    if path.is_symlink():
        raise ValueError(f"Symbolic link is not an install target: {path}")
    if path.is_file():
        return {"": hashlib.sha256(path.read_bytes()).hexdigest()}
    if not path.is_dir():
        return None
    result = {}
    for entry in sorted(path.rglob("*")):
        if entry.is_symlink():
            raise ValueError(f"Symbolic link inside install target: {entry}")
        if entry.is_file():
            result[entry.relative_to(path).as_posix()] = hashlib.sha256(entry.read_bytes()).hexdigest()
    return result



def merge_config(path):
    """Add Spydell guidance while retaining the project's existing settings."""
    try:
        import yaml
    except ImportError as error:
        raise ValueError("Project setup needs PyYAML: python -m pip install -r requirements.txt") from error
    base = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    incoming = yaml.safe_load((ROOT / "openspec/config.example.yaml").read_text(encoding="utf-8"))
    if base is None:
        base = {}
    if not isinstance(base, dict):
        raise ValueError(f"Project config must be a mapping: {path}")
    base.setdefault("schema", incoming["schema"])
    context = base.get("context", "")
    if not isinstance(context, str):
        raise ValueError("Existing context must be a string")
    addition = incoming["context"].strip()
    if addition not in context:
        base["context"] = "\n\n".join(part for part in [context.strip(), addition] if part) + "\n"
    rules = base.setdefault("rules", {})
    operations = base.setdefault("operations", {})
    if not isinstance(rules, dict) or not isinstance(operations, dict):
        raise ValueError("Existing rules and operations must be mappings")
    dropped = []
    for name, additions in incoming["rules"].items():
        dropped += [(f"rules.{name}", item) for item in merge_list(rules, name, additions)]
    for name, additions in incoming["operations"].items():
        operation = operations.setdefault(name, {})
        if not isinstance(operation, dict):
            raise ValueError(f"Existing operation {name} must be a mapping")
        dropped += [
            (f"operations.{name}.guidance", item)
            for item in merge_list(operation, "guidance", additions["guidance"])
        ]
    for location, item in dropped:
        print(f"Superseded entry removed from {location}: {' '.join(item.split())[:72]}...")
    return yaml.safe_dump(base, allow_unicode=True, sort_keys=False, width=110).encode("utf-8")


def merge_list(mapping, key, additions):
    """Append unique guidance, drop superseded wording and keep user-defined rules."""
    values = mapping.setdefault(key, [])
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError(f"Existing {key} must be a list of strings")
    dropped = [item for item in values if is_superseded(item, additions)]
    for item in dropped:
        values.remove(item)
    values.extend(item for item in additions if item not in values)
    return dropped


def is_superseded(item, additions):
    """Report an existing entry whose wording the incoming config has replaced."""
    if item in additions:
        return False
    text = " ".join(item.split())
    current = [" ".join(addition.split()) for addition in additions]
    return any(
        marker in text and not any(marker in addition for addition in current)
        for marker in SUPERSEDED_MARKERS
    )


def remove_target(path):
    """Remove only a target already selected and backed up by the installer."""
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def main():
    """Build an install plan, back up changed targets, and apply it."""
    parser = argparse.ArgumentParser(description=__doc__)
    default_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    parser.add_argument("--skills-dir", type=Path, default=default_home / "skills")
    parser.add_argument("--project", type=Path, help="Existing project; copy schema and merge OpenSpec config")
    parser.add_argument("--project-only", action="store_true", help="Do not install global Spydell skills")
    parser.add_argument("--replace", action="store_true", help="Back up and replace differing skill/schema directories")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup-dir", type=Path, default=Path.home() / ".spydell-backups")
    args = parser.parse_args()
    if args.project_only and not args.project:
        parser.error("--project-only requires --project")
    candidates = []
    if not args.project_only:
        for source in sorted((ROOT / "skills").iterdir()):
            candidates.append((source, args.skills_dir.expanduser().absolute() / source.name, f"skills/{source.name}"))
    if args.project:
        project = args.project.expanduser().resolve()
        if not project.is_dir():
            parser.error("--project must name an existing directory")
        candidates.append((ROOT / "openspec/schemas/spydell", project / "openspec/schemas/spydell", "schema"))
        config = project / "openspec/config.yaml"
        if (project / "openspec/config.yml").exists():
            if config.exists():
                raise ValueError("Both config.yaml and config.yml exist; resolve the ambiguity first")
            config = project / "openspec/config.yml"
        if config.is_symlink():
            raise ValueError(f"Config is a symbolic link: {config}")
        candidates.append((merge_config(config), config, "config"))
    plan = []
    for source, target, label in candidates:
        resolved_target = target.resolve()
        if resolved_target.is_relative_to(ROOT) or ROOT.is_relative_to(resolved_target):
            raise ValueError(f"Install target overlaps the distribution: {target}")
        current = tree_hashes(target)
        expected = {"": hashlib.sha256(source).hexdigest()} if isinstance(source, bytes) else tree_hashes(source)
        if current == expected:
            continue
        if current is not None and not isinstance(source, bytes) and not args.replace:
            raise ValueError(f"Existing files differ: {target}; use --replace to back up and replace them")
        plan.append((source, target, label))
    if not plan:
        print("Already installed; no changes")
        return
    for _, target, _ in plan:
        print(f"{'Would write' if args.dry_run else 'Install'}: {target}")
    if args.dry_run:
        return
    backup = args.backup_dir.expanduser().resolve() / uuid.uuid4().hex
    for _, target, _ in plan:
        if backup.is_relative_to(target):
            raise ValueError("Backup directory must be outside all installation targets")
    backup.mkdir(parents=True)
    original = []
    for _, target, label in plan:
        saved = backup / label
        original.append({"target": str(target), "backup": label if target.exists() else None})
        if target.exists():
            saved.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                shutil.copytree(target, saved)
            else:
                shutil.copy2(target, saved)
    (backup / "restore-map.json").write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
    touched = []
    try:
        for source, target, label in plan:
            touched.append((target, backup / label))
            target.parent.mkdir(parents=True, exist_ok=True)
            remove_target(target)
            if isinstance(source, bytes):
                target.write_bytes(source)
            else:
                shutil.copytree(source, target)
    except BaseException:
        for target, saved in reversed(touched):
            remove_target(target)
            if saved.is_dir():
                shutil.copytree(saved, target)
            elif saved.is_file():
                shutil.copy2(saved, target)
        raise
    print(f"Installed {len(plan)} targets. Backup and restore map: {backup}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
