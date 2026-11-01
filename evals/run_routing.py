#!/usr/bin/env python3
"""Routing eval for Spydell skills through any OpenAI-compatible endpoint (OpenRouter free models by default).

  OPENROUTER_API_KEY=... python3 evals/run_routing.py [--model ID]... [--min 0.8] [--base-url URL]

The model sees every Spydell skill description, the competitor descriptions from routing.json and the project rules
(the AGENTS.md block), then names the one skill for each request or "none". Prints a JSON report; exit code 1 when
accuracy is below --min, 2 when no model answered. Several --model values are tried in order on errors (free models
are rate-limited). Stdlib only.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS = ["google/gemma-4-31b-it:free", "nvidia/nemotron-3.5-lightning:free", "thinkingmachines/inkling:free"]


def descriptions(root=ROOT):
    """Return {skill name: description} from skills/*/SKILL.md front matter (plain or folded `>-`)."""
    found = {}
    for path in sorted(root.glob("skills/*/SKILL.md")):
        front = path.read_text(encoding="utf-8").split("---")[1]
        name = re.search(r"^name:\s*(\S+)", front, re.M).group(1)
        match = re.search(r"^description:\s*(>-?\s*\n((?:[ \t]+.*\n?)+)|(.+))", front, re.M)
        text = match.group(2) or match.group(3) if match else ""
        found[name] = " ".join(line.strip() for line in text.splitlines()).strip()
    return found


def prompt(skills, competitors, rules, request):
    listing = "\n".join(f"- {name}: {text}" for name, text in {**skills, **competitors}.items())
    return (f"Project rules (AGENTS.md):\n{rules}\n\nAvailable skills:\n{listing}\n\n"
            "Pick the single skill that should handle the request below. Answer with the skill name only, "
            "or `none` when a plain code edit needs no skill.\n\n"
            f"Request: {request}")


def parse(answer, names):
    """Return the longest known skill name in the answer, `none`, or `?`."""
    text = answer.strip().strip("`*\"' .").lower()
    for name in sorted(names, key=len, reverse=True):
        if re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", text):
            return name
    return "none" if re.search(r"\bnone\b", text) else "?"


def ask(base_url, key, model, content, timeout=120):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": content}],
                       "temperature": 0, "max_tokens": 400}).encode()
    request = urllib.request.Request(f"{base_url}/chat/completions", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    return data["choices"][0]["message"]["content"] or ""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", action="append", help="model id; repeat for fallbacks")
    parser.add_argument("--min", type=float, default=0.8, help="minimum accuracy (default 0.8)")
    parser.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/routing.json")
    args = parser.parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY is not set")
    spec = json.loads(args.cases.read_text(encoding="utf-8"))
    skills, competitors = descriptions(), spec["competitors"]
    rules = (ROOT / spec["project_rules"]).read_text(encoding="utf-8")
    names = [*skills, *competitors]
    results, models = [], args.model or DEFAULT_MODELS
    for case in spec["cases"]:
        content, got, used, error = prompt(skills, competitors, rules, case["prompt"]), "?", None, ""
        for model in models:
            try:
                got, used = parse(ask(args.base_url, key, model, content), names), model
                break
            except (urllib.error.URLError, KeyError, IndexError, TimeoutError, json.JSONDecodeError) as exc:
                error = f"{model}: {exc}"
                time.sleep(2)
        results.append({"prompt": case["prompt"], "expect": case["expect"], "got": got, "model": used,
                        "ok": got == case["expect"], **({"error": error} if used is None else {})})
    answered = [item for item in results if item["model"]]
    accuracy = sum(item["ok"] for item in results) / len(results)
    print(json.dumps({"accuracy": round(accuracy, 3), "answered": len(answered), "total": len(results),
                      "misses": [item for item in results if not item["ok"]]}, ensure_ascii=False, indent=2))
    sys.exit(2 if not answered else 0 if accuracy >= args.min else 1)


if __name__ == "__main__":
    main()
