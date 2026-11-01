#!/usr/bin/env python3
"""Watch an autonomous run for liveness and exit when the run lead has to look. Prints one JSON object.

The script owns mechanical liveness; the lead owns meaning. Run it in the background: its exit wakes the lead,
which reads the event, acts and starts the watcher again.

  python3 watch.py <set-dir> [--worktree PATH]... [--stuck-after MIN] [--max-runtime MIN] [--interval SEC]

Sources of activity: each --worktree (HEAD, status, staged and unstaged diff, untracked files' size and mtime),
or run-log.md when no worktree is given. Each source has its own idle timer, kept in a state file in the system
temporary directory (one per set), so a restart does not reset it.
Exit codes:
  0  event "log"      new rows in run-log.md (listed in "new_rows")
  2  event "stuck"    a source had no activity for --stuck-after minutes (listed in "stuck")
  3  event "restart"  --max-runtime reached; check the run and start the watcher again
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from check import table_rows


def log_rows(path):
    return table_rows(path.read_text(encoding="utf-8")) if path.exists() else []


def fingerprint(path):
    if path.is_file() or not path.exists():
        stat = path.stat() if path.exists() else None
        return str(stat and (stat.st_mtime_ns, stat.st_size))
    run = lambda *args: subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True).stdout
    untracked = []
    for name in filter(None, run("ls-files", "-z", "--others", "--exclude-standard").split("\0")):
        stat = (path / name).stat() if (path / name).exists() else None
        untracked.append(f"{name}:{stat and (stat.st_mtime_ns, stat.st_size)}")
    parts = [run("rev-parse", "HEAD"), run("status", "--porcelain"), run("diff"), run("diff", "--cached"), *untracked]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("set_dir", type=Path)
    parser.add_argument("--worktree", type=Path, action="append", default=[])
    parser.add_argument("--stuck-after", type=float, default=45, help="minutes without activity (default 45)")
    parser.add_argument("--max-runtime", type=float, default=60, help="minutes before a planned restart (default 60)")
    parser.add_argument("--interval", type=float, default=30, help="seconds between checks (default 30)")
    args = parser.parse_args()
    log = args.set_dir / "run-log.md"
    key = hashlib.sha256(str(args.set_dir.resolve()).encode()).hexdigest()[:16]
    state_path = Path(tempfile.gettempdir()) / f"spydell-watch-{key}.json"
    sources = [path.resolve() for path in args.worktree] or [log.resolve()]
    saved = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    start, rows, state = time.time(), len(log_rows(log)), {}
    for source in sources:
        current, old = fingerprint(source), saved.get(str(source), {})
        state[str(source)] = {"fingerprint": current, "last": old["last"] if old.get("fingerprint") == current else start}
    log_mark = fingerprint(log)

    def finish(code, event, **detail):
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        idle = {source: round((time.time() - item["last"]) / 60, 1) for source, item in state.items()}
        print(json.dumps({"event": event, "idle_minutes": idle, **detail}, ensure_ascii=False, indent=2))
        sys.exit(code)

    while True:
        time.sleep(args.interval)
        now = time.time()
        for source, item in state.items():
            current = fingerprint(Path(source))
            if current != item["fingerprint"]:
                item.update(fingerprint=current, last=now)
        if fingerprint(log) != log_mark:
            log_mark, new = fingerprint(log), log_rows(log)
            if len(new) > rows:
                finish(0, "log", new_rows=[{k: v for k, v in row.items() if k != "_mismatch"} for row in new[rows:]])
            rows = len(new)
        stuck = [source for source, item in state.items() if now - item["last"] >= args.stuck_after * 60]
        if stuck:
            finish(2, "stuck", stuck=stuck)
        if now - start >= args.max_runtime * 60:
            finish(3, "restart")


if __name__ == "__main__":
    main()
