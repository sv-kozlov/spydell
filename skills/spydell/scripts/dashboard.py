#!/usr/bin/env python3
"""Build the Spydell dashboard: collect initiative status into JSON and render it into a static HTML page.

Usage:
  dashboard.py <spydell-set-dir> [--root DIR]... [--out FILE] [--json FILE] [--no-openspec]

<spydell-set-dir> is the initiative folder with map.md and roadmap.md (for example docs/.spydell/<slug>).
--root is a project root that contains openspec/changes; repeat it for several repositories. Without it the script
walks up from the set folder to the first directory with openspec/changes.
Writes <set>/dashboard.html and dashboard.json next to it unless --out / --json say otherwise.
Prints {"html": ..., "json": ..., "slices": n, "waves": n} as JSON.
The JSON format is described in ../assets/dashboard-data.md.
"""

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "dashboard.html"
PLACEHOLDER = '"__SPYDELL_DATA__"'
FORMAT_VERSION = 1

_spec = importlib.util.spec_from_file_location("spydell_check", HERE / "check.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

BACKTICK = re.compile(r"`([A-Za-z0-9][A-Za-z0-9._-]+)`")
CHECKBOX = re.compile(r"^\s*-\s*\[(.)\]", re.M)
DROPPED = re.compile(r"поглощ|отмен|заменён|исключ|dropped|cancel", re.I)
PLANNING = ("proposal", "specs", "design", "tasks")
GATES = (("proposal", "proposal"), ("specs", "specs"), ("qaPlan", "qa-plan"), ("design", "design"), ("tasks", "tasks"))
STAGE = {"planned": 0, "candidate": 0, "needs-decision": 0, "ready-for-spec": 0, "specifying": 1,
         "ready-for-build": 2, "in-progress": 3, "implemented": 3, "accepted": 4, "archived": 5, "dropped": -1}
CLOSED = {"accepted", "archived", "dropped"}
ACTIVE = {"specifying", "ready-for-build", "in-progress", "implemented"}


def read(path):
    return path.read_text(encoding="utf-8") if path and path.exists() else ""


def first_lines(text, limit=400):
    text = "\n".join(line for line in text.strip().splitlines() if not line.startswith("<"))
    return text[:limit].strip()


def pct(part, total):
    return round(part * 100 / total) if total else 0


def find_roots(set_dir, roots):
    if roots:
        return [Path(root).expanduser().resolve() for root in roots]
    for parent in [set_dir, *set_dir.parents]:
        if (parent / "openspec" / "changes").is_dir():
            return [parent]
    return []


def locate_change(name, roots):
    for root in roots:
        changes = root / "openspec" / "changes"
        if (changes / name).is_dir():
            return root, changes / name, False
        archived = sorted((changes / "archive").glob(f"*-{name}")) if (changes / "archive").is_dir() else []
        if archived:
            return root, archived[-1], True
    return None, None, False


def openspec_json(root, *args):
    if not shutil.which("openspec"):
        return None
    env = {**os.environ, "OPENSPEC_TELEMETRY": "0", "DO_NOT_TRACK": "1"}
    try:
        result = subprocess.run(["openspec", *args, "--json"], cwd=root, env=env, capture_output=True, text=True,
                                timeout=60)
        return json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip().startswith("{") else None
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None


def change_status(name, roots, use_cli):
    root, path, archived = locate_change(name, roots)
    if not path:
        return {"name": name, "found": False, "archived": False, "path": "", "artifacts": {}, "tasks": None}
    info = {"name": name, "found": True, "archived": archived, "path": str(path), "artifacts": {}, "tasks": None}
    status = openspec_json(root, "status", "--change", name) if use_cli and not archived else None
    if status:
        info["artifacts"] = {item["id"]: item.get("status", "") for item in status.get("artifacts", [])}
        progress = (openspec_json(root, "instructions", "apply", "--change", name) or {}).get("progress") or {}
        if progress:
            info["tasks"] = {"total": progress.get("total", 0), "complete": progress.get("complete", 0)}
    else:
        for artifact in PLANNING:
            exists = any(path.glob("specs/**/*.md")) if artifact == "specs" else (path / f"{artifact}.md").exists()
            info["artifacts"][artifact] = "done" if exists else "missing"
        if (path / "acceptance" / "qa-plan.md").exists():
            info["artifacts"]["qa-plan"] = "done"
        boxes = CHECKBOX.findall(read(path / "tasks.md"))
        if boxes:
            info["tasks"] = {"total": len(boxes), "complete": sum(box.strip().lower() == "x" for box in boxes)}
    acceptance = path / "acceptance.md"
    if acceptance.exists():
        issues = []
        check.check_acceptance(acceptance, issues)
        info["acceptance"] = {"path": str(acceptance), "issues": [item["message"] for item in issues]}
    qa_report = path / "acceptance" / "qa-report.md"
    if qa_report.exists():
        counts = {"passed": 0, "failed": 0, "blocked": 0}
        for row in check.table_rows(read(qa_report)):
            cell = (check.column(row, "статус", "результат") or "").lower()
            key = "failed" if "не пройден" in cell else "blocked" if "заблокирован" in cell else \
                "passed" if "пройден" in cell else None
            if key:
                counts[key] += 1
        info["qa"] = counts
    return info


def derived_status(slice_, change):
    if DROPPED.search(slice_["state"]) or DROPPED.search(slice_["heading"]):
        return "dropped"
    if change and change["found"]:
        if change["archived"]:
            return "archived"
        if "acceptance" in change and not change["acceptance"]["issues"]:
            return "accepted"
        tasks = change["tasks"] or {}
        if tasks.get("total") and tasks.get("complete") == tasks.get("total"):
            return "implemented"
        if tasks.get("complete"):
            return "in-progress"
        artifacts = change["artifacts"]
        if artifacts and all(artifacts.get(name) == "done" for name in PLANNING if name in artifacts):
            return "ready-for-build"
        return "specifying"
    state = slice_["state"].lower()
    return next((known for known in ("ready-for-build", "ready-for-spec", "needs-decision", "candidate")
                 if known in state), "planned")


def section_items(text):
    """Bullets and table rows of a section as {code, text}."""
    items = []
    for row in check.table_rows(text):
        values = [value for key, value in row.items() if key != "_mismatch" and value]
        if values:
            joined = " · ".join(values)
            codes = check.CODE.findall(joined)
            items.append({"code": codes[0] if codes else "", "text": joined})
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            body = stripped[2:].strip()
            codes = check.CODE.findall(body)
            items.append({"code": codes[0] if codes else "", "text": body})
    return items


def table_section(found, name):
    body = check.find_section(found, name) or ""
    return [{key: value for key, value in row.items() if key != "_mismatch"} for row in check.table_rows(body)]


def slice_record(slice_, change, open_codes, dependents):
    status = derived_status(slice_, change)
    body = "\n".join(slice_["body"])
    tasks = change["tasks"] if change else None
    record = {
        "id": slice_["id"], "title": slice_["title"], "wave": slice_["wave"] or "—", "status": status,
        "stage": STAGE[status], "planState": slice_["state"], "deps": slice_["deps"], "dependents": dependents,
        "repo": slice_["repo"], "openDecisions": sorted(open_codes & set(check.CODE.findall(body))),
        "summary": first_lines("\n".join(line for line in slice_["body"] if " | " not in line), 600),
        "tasks": {**tasks, "pct": pct(tasks["complete"], tasks["total"])} if tasks else None,
        "gates": {key: (change["artifacts"].get(name, "") if change else "") for key, name in GATES},
        "acceptance": ("issues" if change["acceptance"]["issues"] else "ok") if change and "acceptance" in change
        else "none",
        "qa": change.get("qa") if change else None,
        "change": None,
    }
    if change:
        record["change"] = {"name": change["name"], "found": change["found"], "archived": change["archived"],
                            "path": change["path"],
                            "acceptanceIssues": change.get("acceptance", {}).get("issues", [])}
    return record


def collect(set_dir, roots, use_cli):
    map_path, roadmap_path = set_dir / "map.md", set_dir / "roadmap.md"
    map_text, roadmap_text = read(map_path), read(roadmap_path)
    found = check.sections(map_text)
    title = next((line[2:].strip() for line in map_text.splitlines() if line.startswith("# ")), set_dir.name)
    slices = list(check.parse_roadmap(roadmap_text).values())
    for slice_ in slices:
        if not slice_["change"]:
            for name in BACKTICK.findall(slice_["heading"] + "\n" + "\n".join(slice_["body"][:6])):
                if locate_change(name, roots)[1]:
                    slice_["change"] = name
                    break
    frontier_text = check.find_section(found, "Открытый фронтир") or ""
    open_codes = set(check.CODE.findall(frontier_text))
    records = []
    for slice_ in slices:
        change = change_status(slice_["change"], roots, use_cli) if slice_["change"] else None
        dependents = [other["id"] for other in slices if slice_["id"] in other["deps"]]
        records.append(slice_record(slice_, change, open_codes, dependents))

    waves = []
    for record in records:
        wave = next((item for item in waves if item["id"] == record["wave"]), None)
        if not wave:
            wave = {"id": record["wave"], "slices": []}
            waves.append(wave)
        wave["slices"].append(record["id"])
    by_id = {record["id"]: record for record in records}
    for wave in waves:
        members = [by_id[ident] for ident in wave["slices"]]
        counts = {}
        for record in members:
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        closed = sum(record["status"] in CLOSED for record in members)
        wave.update({
            "title": "Без волны" if wave["id"] == "—" else f"Волна {wave['id']}",
            "status": "done" if closed == len(members) else "active" if any(r["status"] in ACTIVE for r in members)
            else "upcoming",
            "closed": closed, "total": len(members), "progressPct": pct(closed, len(members)), "counts": counts,
        })
    waves.sort(key=lambda w: (w["id"] == "—", int(w["id"]) if w["id"].isdigit() else 10**6, w["id"]))

    issues = []
    if map_text:
        check.check_map(map_path, issues)
    if roadmap_text:
        check.check_roadmap(roadmap_path, map_path if map_text else None, issues)
    decisions = section_items(check.find_section(found, "Принятые решения") or check.find_section(found, "решения") or "")
    frontier = section_items(frontier_text)
    live = [record for record in records if record["status"] != "dropped" and record["tasks"]]
    tasks_total = sum(record["tasks"]["total"] for record in live)
    tasks_complete = sum(record["tasks"]["complete"] for record in live)
    status_counts = {}
    for record in records:
        status_counts[record["status"]] = status_counts.get(record["status"], 0) + 1
    return {
        "format": "spydell-dashboard", "version": FORMAT_VERSION,
        "generated": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "initiative": title, "set": str(set_dir),
        "summary": {
            "state": first_lines(check.find_section(found, "Состояние") or ""),
            "next": first_lines(check.find_section(found, "Следующий шаг") or ""),
            "verdict": first_lines(check.find_section(found, "Общий вердикт") or "", 300),
            "contract": first_lines(check.find_section(found, "Контракт прогона") or "", 600),
        },
        "kpis": {
            "slices": len(records),
            "accepted": sum(record["status"] in ("accepted", "archived") for record in records),
            "wavesTotal": len(waves), "wavesDone": sum(wave["status"] == "done" for wave in waves),
            "tasksTotal": tasks_total, "tasksComplete": tasks_complete, "tasksPct": pct(tasks_complete, tasks_total),
            "frontier": len(frontier), "decisions": len(decisions), "issues": len(issues),
        },
        "statusCounts": status_counts,
        "waves": waves,
        "slices": records,
        "frontier": frontier,
        "recentDecisions": decisions[-8:],
        "team": table_section(found, "Команда"),
        "sessions": table_section(found, "Сессии"),
        "runLog": table_section({"log": read(set_dir / "run-log.md")}, "log")[-40:],
        "issues": issues,
        "openspec": {"roots": [str(root) for root in roots], "cli": bool(use_cli and shutil.which("openspec"))},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("set_dir", type=Path)
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--no-openspec", action="store_true", help="Do not call the OpenSpec CLI; read files only")
    args = parser.parse_args()
    set_dir = args.set_dir.expanduser().resolve()
    if not (set_dir / "map.md").exists() and not (set_dir / "roadmap.md").exists():
        parser.error(f"{set_dir} has neither map.md nor roadmap.md")
    data = collect(set_dir, find_roots(set_dir, args.root), not args.no_openspec)
    out = (args.out or set_dir / "dashboard.html").expanduser().resolve()
    json_path = (args.json or out.with_suffix(".json")).expanduser().resolve()
    payload = json.dumps(data, ensure_ascii=False, indent=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(payload + "\n", encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise SystemExit(f"Template has no {PLACEHOLDER} placeholder: {TEMPLATE}")
    out.write_text(template.replace(PLACEHOLDER, payload.replace("</", "<\\/")), encoding="utf-8")
    print(json.dumps({"html": str(out), "json": str(json_path), "slices": len(data["slices"]),
                      "waves": len(data["waves"])}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
