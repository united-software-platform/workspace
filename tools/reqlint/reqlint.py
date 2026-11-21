#!/usr/bin/env python3
"""reqlint — линтер формулировок требований; форк Wyzer-it/reqlint 0.1.0.

Проверяет каждую строку файла на неоднозначный/слабый язык: встроенные правила —
паттерны INCOSE/EARS (англоязычные), пользовательские — из YAML-конфига.

Отличия форка (0.2.0):
- флаг --config <yaml>: правила {name, pattern, hint, error} применяются к каждой строке
  наряду со встроенными;
- severity «error» (error: true, блокирующее) и «warn» (error: false);
- в сообщении приводится фрагмент совпадения.

Вызов в операции requirement-add — по значениям полей карточки BR, по строке на поле:
  python3 -I tools/reqlint/reqlint.py --config tools/reqlint/rules.yml <файл полей>
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict

__version__ = "0.2.0"

AMBIGUOUS_WORDS = {
    "appropriate", "adequate", "sufficient", "reasonable", "acceptable",
    "user-friendly", "flexible", "efficient", "robust", "seamless",
    "state-of-the-art", "easy", "fast", "quickly", "significant",
    "various", "clearly", "normal", "typical", "minimal", "maximal",
    "as needed", "as required", "if possible", "if practical",
    "and/or", "etc", "tbd", "to be determined",
}

WEAK_MODALS = {"should", "may", "might", "could", "can"}
STRONG_MODAL = "shall"

VAGUE_PRONOUNS = {"it", "this", "that", "these", "those"}

UNIT_HINT_WORDS = {"fast", "quickly", "slow", "large", "small", "long", "short"}
UNIT_PATTERN = re.compile(r"\d+(\.\d+)?\s*(ms|s|sec|seconds?|minutes?|mb|gb|kb|%|hz|km|m\b)", re.I)


@dataclass
class Finding:
    rule: str
    severity: str
    message: str


@dataclass
class LineReport:
    line_number: int
    text: str
    findings: list = field(default_factory=list)


def check_ambiguous_words(text: str) -> list:
    lowered = text.lower()
    hits = [w for w in AMBIGUOUS_WORDS if re.search(rf"\b{re.escape(w)}\b", lowered)]
    return [
        Finding("ambiguous-word", "medium", f'Ambiguous term "{w}" — replace with a measurable criterion.')
        for w in hits
    ]


def check_modal_strength(text: str) -> list:
    lowered = text.lower()
    findings = []
    for w in WEAK_MODALS:
        if re.search(rf"\b{re.escape(w)}\b", lowered):
            findings.append(Finding(
                "weak-modal", "high",
                f'Uses "{w}" — a binding requirement should use "{STRONG_MODAL}" for testability.'
            ))
    return findings


def check_missing_units(text: str) -> list:
    lowered = text.lower()
    hits = [w for w in UNIT_HINT_WORDS if re.search(rf"\b{re.escape(w)}\b", lowered)]
    if hits and not UNIT_PATTERN.search(text):
        return [Finding(
            "missing-unit", "high",
            f'Uses relative term(s) {hits} with no measurable unit or threshold nearby.'
        )]
    return []


def check_vague_pronoun_lead(text: str) -> list:
    first_word = re.match(r"\s*([A-Za-z']+)", text)
    if first_word and first_word.group(1).lower() in VAGUE_PRONOUNS:
        return [Finding(
            "vague-pronoun", "low",
            f'Starts with vague pronoun "{first_word.group(1)}" — name the actual subject.'
        )]
    return []


BUILTIN_RULES = [check_ambiguous_words, check_modal_strength, check_missing_units, check_vague_pronoun_lead]


def make_config_rule(spec: dict):
    name = spec.get("name", "unnamed")
    hint = spec.get("hint", "")
    blocking = bool(spec.get("error", False))
    try:
        rx = re.compile(spec["pattern"])
    except re.error as e:
        raise ValueError(f"rule '{name}': bad pattern: {e}")

    def rule(text: str) -> list:
        findings = []
        for m in rx.finditer(text):
            snippet = m.group(0)
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            findings.append(Finding(
                name, "error" if blocking else "warn",
                f'{hint} [совпадение: "{snippet}"]'
            ))
        return findings

    rule.__name__ = f"config:{name}"
    return rule


def load_config_rules(path: str) -> list:
    import yaml
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    specs = (cfg or {}).get("rules") or []
    return [make_config_rule(s) for s in specs]


def lint_line(line_number: int, text: str, rules: list) -> LineReport:
    report = LineReport(line_number=line_number, text=text)
    for rule in rules:
        report.findings.extend(rule(text))
    return report


def main():
    parser = argparse.ArgumentParser(description="Lint a requirements text file for ambiguous/weak language.")
    parser.add_argument("file", help="Path to a text file, one requirement per line")
    parser.add_argument("--config", help="YAML-файл пользовательских правил (rules: [{name, pattern, hint, error}])")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human-readable report")
    parser.add_argument("--fail-on", choices=["low", "warn", "medium", "error", "high"], default=None,
                        help="Exit with status 1 if any finding at or above this severity is present")
    parser.add_argument("--version", action="version", version=f"reqlint {__version__}")
    args = parser.parse_args()

    rules = list(BUILTIN_RULES)
    if args.config:
        try:
            rules += load_config_rules(args.config)
        except (OSError, ValueError, KeyError) as e:
            print(f"reqlint: config error: {e}", file=sys.stderr)
            sys.exit(2)

    with open(args.file, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    reports = [lint_line(i + 1, line, rules) for i, line in enumerate(lines)]

    severity_rank = {"low": 0, "warn": 1, "medium": 1, "error": 2, "high": 2}
    worst = -1

    if args.json:
        print(json.dumps([
            {"line_number": r.line_number, "text": r.text,
             "findings": [asdict(f) for f in r.findings]}
            for r in reports
        ], indent=2, ensure_ascii=False))
    else:
        flagged = [r for r in reports if r.findings]
        if not flagged:
            print(f"reqlint: {len(reports)} requirement(s) checked, no issues found.")
        for r in flagged:
            print(f"\nL{r.line_number}: {r.text}")
            for f in r.findings:
                print(f"  [{f.severity:6}] {f.rule}: {f.message}")
        print(f"\n{len(flagged)}/{len(reports)} requirement(s) flagged.")

    for r in reports:
        for f in r.findings:
            worst = max(worst, severity_rank[f.severity])

    if args.fail_on and worst >= severity_rank[args.fail_on]:
        sys.exit(1)


if __name__ == "__main__":
    main()
