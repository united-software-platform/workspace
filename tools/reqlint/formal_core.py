#!/usr/bin/env python3
"""Ядро формальной проверки критериев BR; исполняется в контейнере workspace-formal.

Конвейер (change add-formal-validation, design D1–D5): карточка → селектор типов
(temporal / quant / unformalizable) → компиляция канонической формы в LTL (SPOT)
и SMT (Z3) → решатели → отчёт на русском с обратным переводом формул на язык карточки.

Детерминировано: одинаковая карточка — байт-в-байт одинаковый отчёт. Критерий вне
канонической формы возвращается с образцом, а не угадывается (D1). Коды возврата:
0 — отчёт построен; 2 — карточка не найдена или не читается.
"""
import re
import sys

import spot
import z3

CANON_SAMPLE = "[условие] → [субъект] [предикат] [порог + единица]: «когда X, Y» | «после X: всегда Y» | «всегда Y» | «никогда Y» | «субъект <= 5 мин» | «субъект >= другой»"

# --- разбор карточки ---

TABLE_ROW = re.compile(r"^\|\s*Success Criteria\s*\|\s*(.+?)\s*\|$", re.M)


def read_criteria(path):
    """Критерии карточки: артефакт docs/requirements/<ID>.md (таблица полей)
    или беклог прогона (фронтматтер br_card)."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    m = TABLE_ROW.search(text)
    if m:
        return m.group(1)
    m = re.search(r'^\s{2}success_criteria:\s*["\']?(.+?)["\']?\s*$', text, re.M)
    return m.group(1) if m else None


def split_criteria(text):
    return [p.strip(" .") for p in re.split(r"[;；]", text) if p.strip(" .")]


# --- селектор (design D1) ---

NUM_WORDS = {
    "два": 2, "двух": 2, "две": 2, "три": 3, "трёх": 3, "трех": 3,
    "четыре": 4, "четырёх": 4, "четырех": 4, "пять": 5, "пяти": 5,
    "десять": 10, "десяти": 10, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10,
}
_NUM_ALT = "|".join(NUM_WORDS)

TEMPORAL_MARKERS = re.compile(
    r"(?<![\w-])(после|когда|всегда|никогда|пока|не\s+раньше|раньше|затем|в\s+течение|в\s+итоге"
    r"|after|when|always|never|until|before|eventually)(?![\w-])", re.I)
THRESHOLD_MARKERS = re.compile(
    r"(<=|>=|≤|≥|<|>|\bне\s+(более|менее|дольше|быстрее|раньше)\b|\bминимум\b|\bмаксимум\b"
    r"|\bat\s+(most|least)\b|\bno\s+(more|less)\s+than\b|\bwithin\b)", re.I)


def has_num_word(text):
    return re.search(rf"\b({_NUM_ALT})\b", text, re.I) is not None


def select_type(criterion):
    if re.search(r"\d", criterion) or THRESHOLD_MARKERS.search(criterion) or has_num_word(criterion):
        return "quant"
    if TEMPORAL_MARKERS.search(criterion):
        return "temporal"
    return "unformalizable"


# --- компиляция quant → SMT ---

UNIT_SCALES = [
    (re.compile(r"^(с|сек|секунд|seconds?|secs?)$", re.I), 1.0, "с"),
    (re.compile(r"^(мин|минут|minutes?|min)$", re.I), 60.0, "мин"),
    (re.compile(r"^(ч|час|часов|hours?|hrs?|h)$", re.I), 3600.0, "ч"),
    (re.compile(r"^(%|процент)$", re.I), 1.0, "%"),
    (re.compile(r"^(шт|штук|pcs)$", re.I), 1.0, "шт"),
]
OPS = {"<=": "<=", ">=": ">=", "<": "<", ">": ">", "=": "=", "≤": "<=", "≥": ">="}
OP_RU = {"<=": "не более", ">=": "не менее", "<": "менее", ">": "более", "=": "равно"}

THRESHOLD_CANON = re.compile(
    r"^(?P<var>.+?)\s*(?P<op><=|>=|≤|≥|<|>|=)\s*(?P<val>\d+(?:[.,]\d+)?)\s*(?P<unit>\S+)?$")
VAR_CANON = re.compile(
    r"^(?P<a>.+?)\s*(?P<op><=|>=|≤|≥|<|>|=)\s*(?P<b>[a-zа-яё][a-zа-яё\s]*)$", re.I)
COUNT_FACT = re.compile(rf"\b(?:на|on)\s+(?P<n>{_NUM_ALT}|\d+)\b", re.I)


def norm_var(name):
    return re.sub(r"\s+", "_", name.strip().lower().replace("ё", "е"))


def unit_scale(unit):
    if not unit:
        return 1.0, ""
    for rx, scale, label in UNIT_SCALES:
        if rx.match(unit):
            return scale, label
    return None, None  # нераспознанная единица


def compile_quant(criterion):
    """Канон → (z3-выражение, формула-показ, перевод). Вне канона — None."""
    m = THRESHOLD_CANON.match(criterion)
    if m and re.fullmatch(r"[a-zа-яё%]+", m.group("unit") or "", re.I):
        scale, label = unit_scale(m.group("unit"))
        if scale is not None:
            var = norm_var(m.group("var"))
            val = float(m.group("val").replace(",", ".")) * scale
            x = z3.Real(var)
            op = OPS[m.group("op")]
            expr = {"<=": x <= val, ">=": x >= val, "<": x < val, ">": x > val, "=": x == val}[op]
            shown = int(val) if val % 1 == 0 else val
            suffix = {"%": "%", "шт": " шт"}.get(label, " с" if scale != 1.0 else (" с" if label == "с" else ""))
            return (expr,
                    f"{var} {op} {shown}{suffix}".rstrip(),
                    f"{m.group('var').strip()} — {OP_RU[op]} {m.group('val')}" + (f" {m.group('unit')}" if m.group("unit") else ""))
    m = VAR_CANON.match(criterion)
    if m and not re.search(r"\d", m.group("b")):
        a, b = norm_var(m.group("a")), norm_var(m.group("b"))
        op = OPS[m.group("op")]
        expr = {"<=": z3.Real(a) <= z3.Real(b), ">=": z3.Real(a) >= z3.Real(b),
                "<": z3.Real(a) < z3.Real(b), ">": z3.Real(a) > z3.Real(b),
                "=": z3.Real(a) == z3.Real(b)}[op]
        return expr, f"{a} {op} {b}", f"{m.group('a').strip()} — {OP_RU[op]} {m.group('b').strip()}"
    m = COUNT_FACT.search(criterion)
    if m:
        n_raw = m.group("n")
        n = NUM_WORDS.get(n_raw.lower(), None) if not n_raw.isdigit() else int(n_raw)
        if n is None:
            n = NUM_WORDS[n_raw.lower()]
        return z3.Real("выборка") == n, f"выборка = {n}", f"выборка равна {n}"
    return None


# --- компиляция temporal → LTL (AST: один источник для SPOT и свидетеля) ---

_ATOMS = {}


def atom(text):
    key = text.strip().lower()
    if key not in _ATOMS:
        _ATOMS[key] = f"p{len(_ATOMS) + 1}"
    return _ATOMS[key]


def compile_temporal(criterion):
    """Канон → (ast, формула-показ, перевод). Вне канона — None."""
    c = criterion.strip().rstrip(".")
    m = re.match(r"^(?:после|after)\s+(.+?)\s*:\s*(?:всегда|always)\s+(.+)$", c, re.I)
    if m:
        cond, prop = m[1].strip(), m[2].strip()
        ast = ("G", ("->", ("atom", atom(cond)), ("G", ("atom", atom(prop)))))
        return ast, to_spot(ast), f"после «{cond}» всегда «{prop}»"
    m = re.match(r"^(?:когда|when)\s+(.+?)\s*,\s*(.+)$", c, re.I)
    if m:
        cond, prop = m[1].strip(), m[2].strip()
        ast = ("G", ("->", ("atom", atom(cond)), ("atom", atom(prop))))
        return ast, to_spot(ast), f"всегда, когда «{cond}», «{prop}»"
    m = re.match(r"^(?:всегда|always)\s+(.+)$", c, re.I)
    if m:
        prop = m[1].strip()
        ast = ("G", ("atom", atom(prop)))
        return ast, to_spot(ast), f"всегда «{prop}»"
    m = re.match(r"^(?:никогда|never)\s+(.+)$", c, re.I)
    if m:
        prop = m[1].strip()
        ast = ("G", ("not", ("atom", atom(prop))))
        return ast, to_spot(ast), f"никогда «{prop}»"
    m = re.match(r"^(?:в\s+итоге|eventually)\s+(.+)$", c, re.I)
    if m:
        prop = m[1].strip()
        ast = ("F", ("atom", atom(prop)))
        return ast, to_spot(ast), f"в итоге «{prop}»"
    return None


def to_spot(ast):
    kind = ast[0]
    if kind == "atom":
        return ast[1]
    if kind == "not":
        return "!" + to_spot(ast[1])
    if kind == "->":
        return f"({to_spot(ast[1])} -> {to_spot(ast[2])})"
    if kind == "G":
        return f"G({to_spot(ast[1])})"
    if kind == "F":
        return f"F({to_spot(ast[1])})"
    raise ValueError(kind)


def cond_atom(ast):
    """Атом-условие temporal-формулы (для vacuity) либо None."""
    inner = ast[1]
    if inner[0] == "->":
        left = inner[1]
        return left[1] if left[0] == "atom" else None
    return None


# --- решатели ---

def smt_check(items):
    """items: [(имя, z3-выражение)] → sat+свидетель / unsat+ядро."""
    s = z3.Solver()
    for name, expr in items:
        s.assert_and_track(expr, z3.Bool(name))
    r = s.check()
    if r == z3.unsat:
        return "contradiction", sorted(str(b) for b in s.unsat_core()), []
    if r == z3.sat:
        model = s.model()
        witness = sorted(f"{d.name()} = {model[d]}" for d in model.decls()
                         if not re.fullmatch(r"K\d+", d.name()))
        return "consistent", [], witness
    return "unknown", [], []


def spot_empty(formula_str):
    return spot.translate(spot.formula(formula_str)).is_empty()


def ltl_check(items):
    """items: [(имя, ast)] → consistent+vacuous+свидетель / contradiction+ядро."""
    conj = " & ".join(to_spot(ast) for _, ast in items)
    if spot_empty(conj):
        core = list(items)
        changed = True
        while changed:
            changed = False
            for item in list(core):
                rest = [x for x in core if x is not item]
                if rest and spot_empty(" & ".join(to_spot(ast) for _, ast in rest)):
                    core, changed = rest, True
                    break
        return "contradiction", [name for name, _ in core], []
    vacuous = [name for name, ast in items
               if cond_atom(ast) and spot_empty(f"({conj}) & F({cond_atom(ast)})")]
    witness = ltl_witness(items)
    return "consistent", vacuous, witness


def ltl_witness(items):
    """Свидетель: конечное слово, удовлетворяющее всем формулам (z3 по горизонту H)."""
    horizon = len(items) + 2
    steps = {a: [z3.Bool(f"{a}__{t}") for t in range(horizon)] for a in _ATOMS.values()}

    def ev(node, t):
        kind = node[0]
        if kind == "atom":
            return steps[node[1]][t]
        if kind == "not":
            return z3.Not(ev(node[1], t))
        if kind == "->":
            return z3.Implies(ev(node[1], t), ev(node[2], t))
        if kind == "G":
            return z3.And([ev(node[1], u) for u in range(t, horizon)])
        if kind == "F":
            return z3.Or([ev(node[1], u) for u in range(t, horizon)])
        raise ValueError(kind)

    s = z3.Solver()
    for _, ast in items:
        s.add(ev(ast, 0))
    if s.check() != z3.sat:
        return []
    model = s.model()
    ru = {v: k for k, v in _ATOMS.items()}
    word = []
    for t in range(horizon):
        true_atoms = sorted(ru[a] for a in steps if z3.is_true(model[steps[a][t]]))
        word.append(f"шаг {t + 1}: " + ("; ".join(true_atoms) if true_atoms else "—"))
    return word


# --- отчёт ---

def main():
    if len(sys.argv) != 2:
        print("вызов: formal_core.py <карточка>", file=sys.stderr)
        sys.exit(2)
    criteria_text = read_criteria(sys.argv[1])
    if not criteria_text:
        print(f"formal: карточка не читается или поля Success Criteria в ней нет: {sys.argv[1]}", file=sys.stderr)
        sys.exit(2)
    criteria = split_criteria(criteria_text)

    lines = [f"Формальная проверка: {sys.argv[1]}", f"Критериев: {len(criteria)}", ""]
    smt_items, ltl_items = [], []
    verdicts, translations, formulas = {}, {}, {}

    for i, criterion in enumerate(criteria, 1):
        name = f"K{i}"
        kind = select_type(criterion)
        if kind == "unformalizable":
            lines += [f"{name} · skipped (не формализуется)",
                      f"  «{criterion}»",
                      "  причина: нет порогов, единиц и временных маркеров — остаётся на уровнях 0–1", ""]
            continue
        if kind == "quant":
            compiled = compile_quant(criterion)
            if compiled is None:
                lines += [f"{name} · quant, вне канона — возвращён владельцу",
                          f"  «{criterion}»",
                          f"  образец канона: {CANON_SAMPLE}", ""]
                continue
            expr, formula, back = compiled
            smt_items.append((name, expr))
            formulas[name], translations[name] = formula, back
            lines += [f"{name} · quant → SMT", f"  «{criterion}»",
                      f"  формула: {formula}", f"  перевод: {back}", ""]
        else:
            compiled = compile_temporal(criterion)
            if compiled is None:
                lines += [f"{name} · temporal, вне канона — возвращён владельцу",
                          f"  «{criterion}»",
                          f"  образец канона: {CANON_SAMPLE}", ""]
                continue
            ast, formula, back = compiled
            ltl_items.append((name, ast))
            formulas[name], translations[name] = formula, back
            lines += [f"{name} · temporal → LTL", f"  «{criterion}»",
                      f"  формула: {formula}", f"  перевод: {back}", ""]

    if _ATOMS:
        mapping = "; ".join(f"{v} = «{k}»" for k, v in _ATOMS.items())
        lines += [f"Атомы: {mapping}", ""]

    contradiction_core = []
    if smt_items:
        verdict, core, witness = smt_check(smt_items)
        lines.append(f"SMT: {verdict}" + (f" — конфликтуют: {', '.join(core)}" if core else ""))
        if witness:
            lines.append("Свидетель (SMT): " + "; ".join(witness))
        contradiction_core += core
    if ltl_items:
        verdict, vacuous, witness = ltl_check(ltl_items)
        suffix = f" — конфликтуют: {', '.join(vacuous)}" if verdict == "contradiction" else ""
        lines.append(f"LTL: {verdict}{suffix}")
        if verdict == "consistent" and vacuous:
            lines.append("Мёртвые условия (vacuous): " + ", ".join(vacuous))
        if witness:
            lines.append("Свидетель (LTL):")
            lines += [f"  {step}" for step in witness]
        if verdict == "contradiction":
            contradiction_core += vacuous

    lines.append("")
    if contradiction_core:
        lines.append("Вердикт: contradiction — конъюнкция критериев невыполнима: "
                     + ", ".join(sorted(set(contradiction_core))))
    elif smt_items or ltl_items:
        lines.append("Вердикт: consistent — доказана выполнимость (не реализуемость)")
    else:
        lines.append("Вердикт: — (нет формализуемых критериев; карточка остаётся на уровнях 0–1)")
    print("\n".join(lines))
    sys.exit(0)


if __name__ == "__main__":
    main()
