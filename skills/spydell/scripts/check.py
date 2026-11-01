#!/usr/bin/env python3
"""Check Spydell artifacts at gates. Prints {"valid": bool, "issues": [...]} as JSON; exit code 1 when invalid.

Each subcommand takes one or more paths, for example one per repository of a slice.

Subcommands:
  map <map.md>...                       decision codes, required sections, relative links
  roadmap <roadmap.md>... [--map PATH]  no slices, dependency cycles, unknown slices, ready-for-build with open decisions,
                                        «Исполнение» as <class>/<effort>, «Параллельно с» within the wave and not a predecessor
  acceptance <acceptance.md>...         required sections, owner and next step for each "Не выполнено" item
  qa <qa-report.md>...                  status of every case, evidence for passed cases
  trace <change-dir>...                 Requirement -> spec-matrix row; scenario names in qa-plan and spec-matrix exist
  run <set-dir>...                      every launch in run-log.md matches a launch line of the map's «Контракт
                                        прогона» in all options except brief, model, effort, directory, output and
                                        budget; launch tools are claude, codex, start_session and those in ../models.md
"""

import argparse
import json
from pathlib import Path
import re
import shlex
import sys

CODE = re.compile(r"\bR\d+[_.\-:]?Q\d+(?:[_.\-][a-z])?\b")
VALID_CODE = re.compile(r"^R\d+_Q\d+(?:_[a-z])?$")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^(#{2,3})\s+(.*\S)\s*$")
MAP_SECTIONS = ["Назначение", "Состояние", "Принятые решения", "Открытый фронтир"]
ACCEPTANCE_SECTIONS = ["Ревизии", "Тесты", "Ревью", "QA", "Повторившиеся классы", "Не выполнено"]
STATUSES = {"пройден", "не пройден", "заблокирован"}
READY = "ready-for-build"
CLASSES = {"сильная", "средняя", "лёгкая", "легкая"}
EFFORTS = {"низкий", "средний", "высокий", "максимальный"}


def issue(issues, code, message, location=""):
    issues.append({"code": code, "message": message, "location": location})


def sections(text, level=2):
    """Map heading text to its body for headings of the given level."""
    result, current, body = {}, None, []
    for line in text.splitlines():
        match = HEADING.match(line)
        if match and len(match.group(1)) <= level:
            if current is not None:
                result[current] = "\n".join(body)
            current, body = (match.group(2) if len(match.group(1)) == level else None), []
        elif current is not None:
            body.append(line)
    if current is not None:
        result[current] = "\n".join(body)
    return result


def find_section(found, name):
    return next((body for heading, body in found.items() if name.lower() in heading.lower()), None)


def table_rows(text):
    """Return markdown table rows as dicts keyed by lower-cased header cells.

    A header is a row followed by a separator row. Rows after a blank line or prose without their own header
    continue the last table when the column count matches; otherwise they are keyed by position.
    """
    lines = [line.strip() for line in text.splitlines()]
    split = lambda line: [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
    is_separator = lambda line: line.startswith("|") and all(set(cell) <= set("-: ") for cell in split(line))
    rows, header, index = [], None, 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("|") and not is_separator(line):
            cells = split(line)
            if index + 1 < len(lines) and is_separator(lines[index + 1]):
                header, index = [cell.lower() for cell in cells], index + 2
                continue
            if header and len(header) != len(cells):
                rows.append({**dict(zip(header, cells)), "_mismatch": line})
            else:
                rows.append(dict(zip(header or [str(i) for i in range(len(cells))], cells)))
        index += 1
    return rows


def column(row, *names):
    return next((value for key, value in row.items() if key != "_mismatch" and any(name in key for name in names)), None)


def check_map(path, issues):
    text = path.read_text(encoding="utf-8")
    found = sections(text)
    for name in MAP_SECTIONS:
        if find_section(found, name) is None:
            issue(issues, "map.section", f"Нет раздела «{name}»", str(path))
    for token in sorted(set(CODE.findall(text))):
        if not VALID_CODE.match(token):
            issue(issues, "map.code", f"Код «{token}» не в формате R<n>_Q<n> или R<n>_Q<n>_<буква>", str(path))
    decisions = find_section(found, "Принятые решения") or ""
    seen = {}
    for row in table_rows(decisions):
        code = next(iter(row.values()), "")
        if VALID_CODE.match(code):
            if code in seen:
                issue(issues, "map.duplicate", f"Код {code} записан в решениях дважды", str(path))
            seen[code] = True
    for target in LINK.findall(text):
        if re.match(r"^[a-z]+://|^mailto:|^#", target):
            continue
        local = target.split("#", 1)[0]
        if local and not (path.parent / local).exists():
            issue(issues, "map.link", f"Ссылка ведёт на несуществующий путь: {target}", str(path))


FIELD = re.compile(r"^\s*[-*]?\s*\**([^:*|]+?)\**\s*:\s*(.*)$")
NO_DEPS = {"", "нет", "none", "—", "-"}


def split_ids(value):
    return [item.strip(" `") for item in re.split(r"[,;]", value or "") if item.strip(" `").lower() not in NO_DEPS]


def parse_roadmap(text):
    """Return slices by ID from the «Срезы» table and from '### <ID> — title' cards; table fields win.

    Each slice: id, title, wave, state, deps, change, repo, body (card lines), heading.
    """
    slices, current = {}, None

    def blank(ident):
        return {"id": ident, "title": "", "wave": "", "state": "", "deps": [], "change": "", "repo": "",
                "execution": "", "parallel": [], "body": [], "heading": ""}

    for line in text.splitlines():
        match = HEADING.match(line)
        if match and len(match.group(1)) == 3:
            heading = match.group(2)
            ident = heading.split()[0].rstrip(".:—-")
            current = slices.setdefault(ident, blank(ident))
            current["heading"] = heading
            title = re.sub(r"^\S+\s*[—–-]?\s*", "", heading).replace("**", "")
            current["title"] = re.sub(r"\s*\(.*?\)\s*$", "", title).strip(" *—-")
            continue
        if match:
            current = None
            continue
        if current is None:
            continue
        current["body"].append(line)
        field = FIELD.match(line)
        if not field:
            continue
        label, value = field.group(1).strip().lower(), field.group(2).strip()
        if label in ("предшественник", "предшественники", "зависит от"):
            current["deps"] += split_ids(value)
        elif label == "состояние":
            current["state"] = value.strip(" `")
        elif label == "волна":
            current["wave"] = (value.strip(" `").split() or [""])[0]
        elif label in ("change", "openspec change"):
            current["change"] = (re.findall(r"`([^`]+)`", value) or value.split() or [""])[0].strip("`")
        elif label in ("репозиторий", "repo"):
            current["repo"] = value.strip(" `")
        elif label == "исполнение":
            current["execution"] = value.strip(" `")
        elif label == "параллельно с":
            current["parallel"] += split_ids(value)
    table = find_section(sections(text), "Срезы") or ""
    ordered = {}
    for row in table_rows(table):
        ident = (column(row, "id") or "").strip(" `")
        if not ident:
            continue
        if ident in ordered:
            ordered[ident]["duplicate"] = True
            continue
        slice_ = slices.get(ident) or blank(ident)
        slice_["title"] = (column(row, "срез", "название") or slice_["title"] or ident).strip()
        slice_["wave"] = (column(row, "волна") or slice_["wave"]).strip(" `")
        slice_["state"] = (column(row, "состояние") or slice_["state"]).strip(" `")
        slice_["deps"] = split_ids(column(row, "предшеств", "зависит")) or slice_["deps"]
        slice_["change"] = (column(row, "change") or slice_["change"]).strip(" `")
        slice_["repo"] = (column(row, "репозитор") or slice_["repo"]).strip(" `")
        execution, parallel = column(row, "исполнение"), column(row, "параллельно")
        if execution is not None:
            slice_["execution"] = "" if execution.strip(" `").lower() in NO_DEPS else execution.strip(" `")
        if parallel is not None:
            slice_["parallel"] = split_ids(parallel)
        slice_["body"] = slice_["body"] + [" | ".join(value for key, value in row.items() if key != "_mismatch")]
        ordered[ident] = slice_
    for ident, slice_ in slices.items():
        ordered.setdefault(ident, slice_)
    for slice_ in ordered.values():
        slice_["title"] = slice_["title"] or slice_["id"]
        if not slice_["wave"]:
            wave = re.match(r"^[Ww](\d+)", slice_["id"])
            slice_["wave"] = wave.group(1) if wave else ""
    return ordered


def check_roadmap(path, map_path, issues):
    slices = parse_roadmap(path.read_text(encoding="utf-8"))

    def ancestors(name, seen=None):
        seen = set() if seen is None else seen
        for dep in slices.get(name, {}).get("deps", []):
            if dep not in seen:
                seen.add(dep)
                ancestors(dep, seen)
        return seen

    if not slices:
        issue(issues, "roadmap.empty", "Срезов нет: ни таблицы «Срезы», ни карточек «### <ID> — название»", str(path))
    for name, slice_ in slices.items():
        if slice_.get("duplicate"):
            issue(issues, "roadmap.duplicate", f"Срез {name} записан в таблице «Срезы» дважды", str(path))
        for dep in slice_["deps"]:
            if dep not in slices:
                issue(issues, "roadmap.unknown", f"{name} зависит от неизвестного среза {dep}", str(path))
        if slice_["execution"]:
            parts = [part.strip().lower() for part in slice_["execution"].split("/")]
            if len(parts) != 2 or parts[0] not in CLASSES or parts[1] not in EFFORTS:
                issue(issues, "roadmap.execution",
                      f"{name}: «Исполнение: {slice_['execution']}» — нужно <класс>/<effort>: "
                      "сильная|средняя|лёгкая / низкий|средний|высокий|максимальный", str(path))
        for other in slice_["parallel"]:
            peer = slices.get(other)
            if peer is None:
                issue(issues, "roadmap.parallel", f"{name} параллелен неизвестному срезу {other}", str(path))
            elif other == name:
                issue(issues, "roadmap.parallel", f"{name} указан параллельным самому себе", str(path))
            elif other in ancestors(name) or name in ancestors(other):
                issue(issues, "roadmap.parallel", f"{name} и {other} связаны цепочкой «предшественник» и не могут идти параллельно",
                      str(path))
            elif peer["wave"] != slice_["wave"]:
                issue(issues, "roadmap.parallel", f"{name} (волна {slice_['wave']}) параллелен {other} из волны {peer['wave']}",
                      str(path))
    state, stack = {}, []

    def visit(name):
        state[name] = "open"
        stack.append(name)
        for dep in slices[name]["deps"]:
            if dep not in slices:
                continue
            if state.get(dep) == "open":
                cycle = stack[stack.index(dep):] + [dep]
                issue(issues, "roadmap.cycle", "Цикл зависимостей: " + " -> ".join(cycle), str(path))
            elif dep not in state:
                visit(dep)
        stack.pop()
        state[name] = "done"

    for name in slices:
        if name not in state:
            visit(name)
    map_path = map_path or path.parent / "map.md"
    if map_path.exists():
        frontier = find_section(sections(map_path.read_text(encoding="utf-8")), "Открытый фронтир") or ""
        open_codes = set(CODE.findall(frontier))
        for name, slice_ in slices.items():
            if slice_["state"] == READY:
                pending = open_codes & set(CODE.findall("\n".join(slice_["body"])))
                if pending:
                    issue(issues, "roadmap.ready",
                          f"{name} в {READY}, но ссылается на открытые решения: {', '.join(sorted(pending))}", str(path))


def check_acceptance(path, issues):
    found = sections(path.read_text(encoding="utf-8"))
    for name in ACCEPTANCE_SECTIONS:
        if find_section(found, name) is None:
            issue(issues, "acceptance.section", f"Нет раздела «{name}»", str(path))
    for line in (find_section(found, "Не выполнено") or "").splitlines():
        item = line.strip()
        if item.startswith(("-", "*")) and item.lstrip("-* ").lower() not in ("нет", "нет."):
            if "владелец:" not in item.lower() or "следующий шаг:" not in item.lower():
                issue(issues, "acceptance.open", f"Пункт без «владелец:» и «следующий шаг:»: {item[:80]}", str(path))


def check_qa(path, issues):
    rows = [row for row in table_rows(path.read_text(encoding="utf-8")) if column(row, "статус", "status") is not None]
    if not rows:
        issue(issues, "qa.table", "Нет таблицы кейсов со столбцом «Статус»", str(path))
    for row in rows:
        if "_mismatch" in row:
            issue(issues, "qa.row", f"Число ячеек не совпадает с заголовком (экранируй | как \\|): {row['_mismatch'][:80]}",
                  str(path))
            continue
        case = next(iter(row.values()), "?")
        status = (column(row, "статус", "status") or "").strip().lower()
        if status not in STATUSES:
            issue(issues, "qa.status", f"Кейс {case}: статус «{status}» не из {sorted(STATUSES)}", str(path))
        elif status == "пройден" and not (column(row, "доказательств", "evidence") or "").strip(" -—"):
            issue(issues, "qa.evidence", f"Кейс {case} пройден без доказательства", str(path))


def check_trace(change, issues):
    requirements, scenarios = set(), set()
    for spec in sorted((change / "specs").rglob("*.md")):
        removed = False
        for line in spec.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                removed = "REMOVED" in line.upper()
            elif line.startswith("### Requirement:") and not removed:
                requirements.add(line.split(":", 1)[1].strip())
            elif line.startswith("#### Scenario:") and not removed:
                scenarios.add(line.split(":", 1)[1].strip())
    matrix_path = change / "acceptance/spec-matrix.md"
    if not matrix_path.exists():
        issue(issues, "trace.matrix", "Нет acceptance/spec-matrix.md", str(change))
        matrix = []
    else:
        matrix = table_rows(matrix_path.read_text(encoding="utf-8"))
    covered = {column(row, "requirement", "требование") for row in matrix}
    for name in sorted(requirements - covered):
        issue(issues, "trace.uncovered", f"Requirement «{name}» нет в spec-matrix", str(matrix_path))
    for row in matrix:
        if "_mismatch" in row:
            issue(issues, "trace.row", f"Число ячеек не совпадает с заголовком: {row['_mismatch'][:80]}", str(matrix_path))
            continue
        name = column(row, "requirement", "требование")
        if name and name not in requirements:
            issue(issues, "trace.unknown", f"spec-matrix ссылается на неизвестный Requirement «{name}»", str(matrix_path))
    plan_path = change / "acceptance/qa-plan.md"
    sources = [(matrix_path, matrix)]
    if plan_path.exists():
        sources.append((plan_path, table_rows(plan_path.read_text(encoding="utf-8"))))
    for source, rows in sources:
        for row in rows:
            name = column(row, "scenario", "сценарий")
            if name and name not in scenarios:
                issue(issues, "trace.scenario", f"Неизвестный Scenario «{name}»", str(source))


CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
LAUNCH_TOOLS = {"claude", "codex", "start_session"}
# Options that vary between launches of one contract line; every other option and its values must match exactly.
# Per tool: `-p` is the brief flag of claude but the settings profile of codex.
VARIABLE = {"claude": {"-p", "--print", "--model", "--fallback-model", "--effort", "--output-format", "--max-budget-usd",
                       "--session-id"},
            "codex": {"-m", "--model", "-C", "--cd", "-o", "--output-last-message", "--output-schema"},
            "start_session": {"model", "name", "effort"}}
# Tools found only in the project's models.md: model and effort vary, every other option must match.
GENERIC_VARIABLE = {"-m", "--model", "--effort"}
VARIABLE_CONFIG = re.compile(r"^model_reasoning_effort=")  # codex -c value that carries effort
BRIEF = {"<бриф>", "<brief>", "<prompt>"}  # brief placeholder; must not land in an option's values
WRAPPERS = {"npx", "uvx", "pipx", "bunx", "pnpm", "yarn", "node", "python", "python3"}  # the package names the tool
SHELL = re.compile(r"\$[({]|`|\\\n")
VARIABLE_ENV = {"CLAUDE_CODE_TMPDIR"}
SUBCOMMANDS = {"exec", "e", "review", "resume"}


def shell_operators(command):
    """True when the line holds shell operators or substitutions that could run a second command."""
    if SHELL.search(command):
        return True
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return any(token and set(token) <= set("();<>|&") for token in lexer)
    except ValueError:
        return True


def first_word(command):
    try:
        words = [word for word in shlex.split(command) if word != "env" and not re.match(r"^[A-Za-z_]\w*=", word)]
    except ValueError:
        return ""
    return Path(words[0]).name if words and not words[0].startswith("-") else ""


def launch(command, tools=frozenset(LAUNCH_TOOLS)):
    """Return (tool, signature) of a session launch line, or None for any other code.

    The signature holds environment variables, subcommands and every option with all its values, except
    the VARIABLE ones (brief, model, directory, output, budget). Positional arguments other than subcommands
    are the brief and are ignored.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    signature = []
    while tokens and (tokens[0] == "env" or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0])):
        name, _, value = tokens.pop(0).partition("=")
        if name != "env" and name not in VARIABLE_ENV:
            signature.append(("env", name, value))
    if not tokens or Path(tokens[0]).name not in tools:
        return None
    tool, option, values, rest = Path(tokens[0]).name, None, [], tokens[1:]
    if tool in WRAPPERS:
        package = next((index for index, token in enumerate(rest) if not token.startswith("-")), None)
        if package is None:
            return None
        tool, rest = f"{tool} {rest[package]}", rest[:package] + rest[package + 1:]
    variable = VARIABLE.get(tool.split()[0], GENERIC_VARIABLE)

    def flush():
        if option is None or option in variable:
            return
        if option in ("-c", "--config") and values and VARIABLE_CONFIG.match(values[0]):
            return
        signature.append((option, *values))

    index = 0
    while index < len(rest):
        token = rest[index]
        keyed = tool == "start_session" and "=" in token
        if (token.startswith("-") and len(token) > 1) or keyed:
            flush()
            name, has_value, value = token.partition("=") if token.startswith("--") or keyed else (token, "", "")
            option, values = name, [value] if has_value else []
            if name in variable and not has_value and index + 1 < len(rest) and not rest[index + 1].startswith("-"):
                index += 1
            if name in variable or keyed:
                flush()
                option = None
        elif option is not None:
            values.append(token)
        elif token in SUBCOMMANDS and not any(item[0].startswith("-") for item in signature):
            signature.append(("sub", token))
        index += 1
    flush()
    return tool, tuple(signature)


def check_run(set_dir, issues):
    log_path, map_path = set_dir / "run-log.md", set_dir / "map.md"
    if not log_path.exists():
        issue(issues, "run.log", "Нет run-log.md", str(set_dir))
        return
    contract = find_section(sections(map_path.read_text(encoding="utf-8")), "Контракт прогона") if map_path.exists() else None
    if contract is None:
        issue(issues, "run.contract", "Журнал прогона есть, а раздела «Контракт прогона» в map.md нет", str(map_path))
        return
    tools = set(LAUNCH_TOOLS)
    models = set_dir.parent / "models.md"
    if models.exists():
        for row in table_rows(models.read_text(encoding="utf-8")):
            tools.update(filter(None, map(first_word, CODE_SPAN.findall(column(row, "запуск") or ""))))
    fenced = [line for block in FENCE.findall(contract) for line in block.splitlines() if line.strip()]
    tools.update(filter(None, map(first_word, fenced)))  # a contract code block holds launch lines only
    mention = re.compile(r"(?<![\w.-])(" + "|".join(map(re.escape, sorted(tools))) + r")(?![\w.-])")
    lines = [line for block in FENCE.findall(contract) for line in block.splitlines()]
    allowed = {}
    for line in lines + CODE_SPAN.findall(FENCE.sub("", contract)):
        found = launch(line, tools)
        if found is None:
            continue
        if any(value in BRIEF for item in found[1] for value in item[1:]):
            issue(issues, "run.brief", f"В строке контракта бриф стоит за флагом со значениями — поставь его сразу "
                  f"за флагом брифа или модели либо перед флагами: {line[:80]}", str(map_path))
            continue
        allowed.setdefault(found[0], set()).add(found[1])
    for row in table_rows(log_path.read_text(encoding="utf-8")):
        if "_mismatch" in row:
            issue(issues, "run.row", f"Число ячеек не совпадает с заголовком: {row['_mismatch'][:80]}", str(log_path))
            continue
        launches = 0
        for span in CODE_SPAN.findall(" ".join(value for key, value in row.items())):
            found = launch(span, tools)
            if found is None:
                if mention.search(span):
                    issue(issues, "run.unparsed", f"Запуск не распознан — пиши строку как в контракте: {span[:80]}",
                          str(log_path))
                continue
            launches += 1
            if shell_operators(span):
                issue(issues, "run.shell", f"В строке запуска подстановка или цепочка команд оболочки: {span[:80]}",
                      str(log_path))
                continue
            tool, signature = found
            if tool not in allowed:
                issue(issues, "run.launch", f"Запуск «{tool}» без строки запуска в контракте: {span[:80]}", str(log_path))
            elif signature not in allowed[tool]:
                issue(issues, "run.permissions", f"Флаги запуска расходятся с контрактом: {span[:80]}", str(log_path))
        if not launches and (column(row, "что") or "").strip().lower().startswith("запуск"):
            issue(issues, "run.evidence", f"Строка «запуск» без строки запуска кодом: {(column(row, 'что') or '')[:80]}",
                  str(log_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("map", "acceptance", "qa", "trace", "run"):
        sub.add_parser(name).add_argument("paths", type=Path, nargs="+")
    roadmap = sub.add_parser("roadmap")
    roadmap.add_argument("paths", type=Path, nargs="+")
    roadmap.add_argument("--map", type=Path)
    args = parser.parse_args()
    issues = []
    for path in args.paths:
        if not path.exists():
            issue(issues, "path", f"Нет пути {path}", str(path))
        elif args.command == "map":
            check_map(path, issues)
        elif args.command == "roadmap":
            check_roadmap(path, args.map, issues)
        elif args.command == "acceptance":
            check_acceptance(path, issues)
        elif args.command == "qa":
            check_qa(path, issues)
        elif args.command == "run":
            check_run(path, issues)
        else:
            check_trace(path, issues)
    print(json.dumps({"valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
