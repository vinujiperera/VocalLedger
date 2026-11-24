"""Expand Vinuji's hand-written phrases into 200+ labelled test phrases.

Reads data/example_phrases.csv and writes data/test_phrases.csv with the same
columns: phrase, intent, amount, contact_name, item.

Includes spoken amounts ("fifteen hundred"), currency slang (1.5k, 600/=, rs),
phrasing variants, and light Sinhala/Tamil-flavoured mixes.

Run:  python scripts/expand_phrases.py
"""
from __future__ import annotations

import csv
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = ROOT / "data" / "example_phrases.csv"
OUT_PATH = ROOT / "data" / "test_phrases.csv"

RNG = random.Random(42)

NAMES = [
    "Maya", "Kamala", "Nimal", "Sunil", "Priya", "Ruwan", "Dilani", "Chamari",
    "Kasun", "Nadeeka", "Mala", "Ajith", "Thilini", "Kumari", "Aunty Silva",
    "Saman", "Nishani", "Lakshmi", "Ravi", "Sanduni",
]

DEBT_ITEMS = [
    "cakes", "vegetables", "rice", "string hoppers", "wedding cake",
    "2 kg rice", "biscuits", "tailoring", "sweets", "lunch packets",
    "short eats", "kiribath", "hoppers", "samosas",
]

INCOME_ITEMS = [
    "3 loaves", "10 samosas", "vegetables", "2 kg rice", "4 short eats",
    "sewing", "birthday cake", "cookies", "string hoppers", "kiribath",
]

EXPENSE_ITEMS = [
    "rent", "gas", "flour", "electricity bill", "ingredients", "transport",
    "packaging", "helper", "eggs", "phone reload", "market stall fee", "oil",
]

# Prefer forms that stress spoken wording and local slang.
AMOUNT_FORMS = {
    250: ["250", "two hundred and fifty", "250/="],
    300: ["300", "three hundred", "300/="],
    360: ["360", "three hundred and sixty", "360/="],
    450: ["450", "four hundred and fifty", "rs 450"],
    500: ["500", "five hundred", "0.5k", "500/="],
    600: ["600", "six hundred", "600/=", "rs 600"],
    750: ["750", "seven hundred and fifty", "seven fifty"],
    760: ["760", "seven hundred and sixty"],
    800: ["800", "eight hundred", "rs 800"],
    900: ["900", "nine hundred", "900/="],
    1000: ["1000", "one thousand", "a thousand", "1k"],
    1200: ["1200", "twelve hundred", "1.2k", "rs 1200"],
    1500: ["1500", "fifteen hundred", "one thousand five hundred", "1.5k", "1500/="],
    1800: ["1800", "eighteen hundred", "1.8k"],
    2000: ["2000", "two thousand", "2k", "2000/="],
    2200: ["2200", "twenty two hundred", "2.2k"],
    2500: ["2500", "two thousand five hundred", "twenty five hundred", "2.5k"],
    3000: ["3000", "three thousand", "3k"],
    3200: ["3200", "thirty two hundred", "3200/="],
    3500: ["3500", "thirty five hundred", "3.5k"],
    4000: ["4000", "four thousand", "4k"],
    5000: ["5000", "five thousand", "5k", "5000/="],
    8000: ["8000", "eight thousand", "8k"],
}


def load_seed() -> list[dict]:
    with SEED_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["amount"] = float(row["amount"]) if row["amount"] else None
        row["contact_name"] = (row.get("contact_name") or "").strip()
        row["item"] = (row.get("item") or "").strip()
    return rows


def amount_forms(amount: float) -> list[str]:
    n = int(amount) if float(amount) == int(float(amount)) else amount
    forms = list(AMOUNT_FORMS.get(int(amount), []))
    if not forms:
        forms = [str(n), f"rs {n}", f"{n}/="]
    return forms


def digits_only(amount: float) -> str:
    return str(int(amount) if float(amount) == int(float(amount)) else amount)


def strip_article(item: str) -> str:
    return re.sub(r"^(the|a|an)\s+", "", item.strip(), flags=re.I)


def make_row(phrase: str, intent: str, amount, contact_name: str = "", item: str = "") -> dict:
    amount_out = ""
    if amount is not None and amount != "":
        amount_out = digits_only(amount)
    return {
        "phrase": " ".join(phrase.split()),
        "intent": intent,
        "amount": amount_out,
        "contact_name": contact_name or "",
        "item": item or "",
    }


def replace_amount_in_phrase(phrase: str, old_amount: float, new_text: str) -> str | None:
    """Swap the first amount expression in a seed phrase for another written form.

    Matches the widest amount span first (e.g. '600/=' or 'rs 1500', not bare '600')
    so rewrites never leave stray '/=', 'rs', or doubled currency markers.
    """
    n = digits_only(old_amount)
    candidates: list[str] = []
    for form in amount_forms(old_amount):
        candidates.append(form)
    candidates.extend(
        [
            f"rs {n}",
            f"rs. {n}",
            f"rupees {n}",
            f"{n}/=",
            f"{n}/-",
            n,
        ]
    )
    # Longest first so '600/=' wins over '600'
    candidates = sorted(set(candidates), key=len, reverse=True)

    for form in candidates:
        pat = re.compile(re.escape(form), re.I)
        match = pat.search(phrase)
        if not match:
            continue
        rewritten = phrase[: match.start()] + new_text + phrase[match.end() :]
        # Drop a currency suffix left behind when the seed had digits+/ = and we
        # matched only a longer spoken form elsewhere (should not happen now).
        rewritten = re.sub(r"(/[=-]){2,}", "/=", rewritten)
        rewritten = re.sub(r"\b(rs\.?|rupees)\s+(rs\.?|rupees)\s+", r"\1 ", rewritten, flags=re.I)
        return rewritten
    return None



class PhraseSet:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.seen: set[str] = set()

    def add(self, row: dict) -> bool:
        key = row["phrase"].lower()
        if not row["phrase"] or key in self.seen:
            return False
        self.seen.add(key)
        self.rows.append(row)
        return True


def expand_seed_amount_forms(seed: list[dict], out: PhraseSet) -> None:
    """Keep each seed phrase and rewrite its amount in other spoken/slang forms."""
    for row in seed:
        out.add(make_row(row["phrase"], row["intent"], row["amount"], row["contact_name"], row["item"]))
        for form in amount_forms(row["amount"]):
            rewritten = replace_amount_in_phrase(row["phrase"], row["amount"], form)
            if rewritten and rewritten.lower() != row["phrase"].lower():
                out.add(make_row(rewritten, row["intent"], row["amount"], row["contact_name"], row["item"]))


def add_debt_templates(out: PhraseSet) -> None:
    templates = [
        "{name} owes {amount} for {item}",
        "{name} owes me {amount} for {item}",
        "{name} owes {amount} for the {item}",
        "{name} has to pay me {amount} for {item}",
        "{name} took {item} on credit {amount}",
        "{name} took {item} on tab {amount}",
        "sold {item} to {name} on credit {amount}",
        "gave {name} {item} on tab {amount}",
        "{name} owes me rupees {amount} for {item}",
        "note {name} owes {amount} for {item}",
        # light local mixes / slang
        "machan {name} owes {amount} for {item}",
        "{name} owes {amount} for {item} aiyo",
        "{name} akka owes {amount} for {item}",
    ]
    combos = [
        ("Maya", 1500, "cakes"),
        ("Kamala", 800, "vegetables"),
        ("Nimal", 450, "biscuits"),
        ("Sunil", 2500, "rice"),
        ("Priya", 1500, "wedding cake"),
        ("Ruwan", 900, "2 kg rice"),
        ("Dilani", 600, "string hoppers"),
        ("Kasun", 300, "2 loaves"),
        ("Nadeeka", 1200, "tailoring"),
        ("Mala", 750, "sweets"),
        ("Ajith", 2000, "curtains"),
        ("Thilini", 1800, "cake"),
        ("Kumari", 3000, "lunch packets"),
        ("Chamari", 250, "5 buns"),
        ("Saman", 1000, "hoppers"),
        ("Lakshmi", 500, "samosas"),
        ("Ravi", 2000, "kiribath"),
        ("Sanduni", 1200, "short eats"),
    ]
    for name, amount, item in combos:
        forms = amount_forms(amount)
        # digits + one spoken + one slang when available
        chosen = [forms[0]]
        spoken = [f for f in forms if any(c.isalpha() for c in f)]
        slang = [f for f in forms if f != forms[0] and f not in spoken]
        if spoken:
            chosen.append(spoken[0])
        if slang:
            chosen.append(slang[0])
        for form in chosen:
            tmpl = RNG.choice(templates)
            item_use = strip_article(item) if "the {item}" in tmpl else item
            amount_use = digits_only(amount) if "rupees {amount}" in tmpl else form
            phrase = tmpl.format(name=name, amount=amount_use, item=item_use)
            out.add(make_row(phrase, "debt", amount, name, item_use))


def add_income_templates(out: PhraseSet) -> None:
    templates = [
        "sold {item} {amount}",
        "sold {item} for {amount}",
        "sold {item} {amount} cash",
        "sold {item} rs {amount}",
        "received {amount} for the {item}",
        "got {amount} for a {item}",
        "earned {amount} from {item}",
        "made {amount} selling {item}",
        "sold {item} {amount}/=",
        "today sold {item} {amount}",
        "sold {item} {amount} cash only",
    ]
    combos = [
        ("3 loaves", 600),
        ("10 samosas", 500),
        ("vegetables", 1200),
        ("2 kg rice", 760),
        ("4 short eats", 1000),
        ("sewing", 2000),
        ("birthday cake", 900),
        ("cookies", 1500),
        ("string hoppers", 600),
        ("kiribath", 1500),
        ("dress", 8000),
        ("catering order", 3500),
        ("6 bottles of water", 360),
    ]
    for item, amount in combos:
        forms = amount_forms(amount)
        chosen = [forms[0]]
        spoken = [f for f in forms if any(c.isalpha() for c in f)]
        slang = [f for f in forms if ("k" in f.lower() or "/=" in f or f.lower().startswith("rs")) and f not in chosen]
        if spoken:
            chosen.append(spoken[0])
        if slang:
            chosen.append(slang[0])
        for form in chosen:
            tmpl = RNG.choice(templates)
            item_use = strip_article(item)
            if "rs {amount}" in tmpl:
                amount_use = form[3:] if form.lower().startswith("rs ") else digits_only(amount)
            elif "{amount}/=" in tmpl:
                # Template already adds /= — only plug in bare digits
                amount_use = digits_only(amount)
            else:
                amount_use = form
            phrase = tmpl.format(item=item_use, amount=amount_use)
            out.add(make_row(phrase, "income", amount, "", item_use))

    # Bare sale totals (empty item) — common market shorthand
    for amount, form in [
        (5000, "5000"),
        (5000, "five thousand"),
        (5000, "5k"),
        (2000, "two thousand"),
        (1000, "1k"),
        (1500, "fifteen hundred"),
    ]:
        out.add(make_row(f"sale {form} today", "income", amount, "", ""))
        out.add(make_row(f"sale {form}", "income", amount, "", ""))


def add_expense_templates(out: PhraseSet) -> None:
    templates = [
        "paid {item} {amount}",
        "paid {amount} for {item}",
        "spent {amount} on {item}",
        "bought {item} {amount}",
        "bought {item} for {amount}",
        "bought {item} rs {amount}",
        "paid {item} {amount}/=",
        "spent {amount} on {item} today",
        "paid the {item} {amount}",
    ]
    combos = [
        ("rent", 5000),
        ("gas", 800),
        ("flour", 2500),
        ("electricity bill", 3200),
        ("ingredients", 2000),
        ("transport", 450),
        ("packaging", 1200),
        ("helper", 1500),
        ("eggs", 1800),
        ("phone reload", 600),
        ("market stall fee", 1000),
        ("oil", 900),
        ("10 kg sugar", 2200),
    ]
    for item, amount in combos:
        forms = amount_forms(amount)
        chosen = [forms[0]]
        spoken = [f for f in forms if any(c.isalpha() for c in f)]
        slang = [f for f in forms if ("k" in f.lower() or "/=" in f or f.lower().startswith("rs")) and f not in chosen]
        if spoken:
            chosen.append(spoken[0])
        if slang:
            chosen.append(slang[0])
        for form in chosen:
            tmpl = RNG.choice(templates)
            item_use = item
            if "rs {amount}" in tmpl:
                amount_use = form[3:] if form.lower().startswith("rs ") else digits_only(amount)
            elif "{amount}/=" in tmpl:
                amount_use = digits_only(amount)
            else:
                amount_use = form
            phrase = tmpl.format(item=item_use, amount=amount_use)
            out.add(make_row(phrase, "expense", amount, "", item_use))


def add_spoken_and_mix_extras(out: PhraseSet) -> None:
    """Guarantee plenty of spoken-number and mixed-language examples."""
    extras = [
        make_row("Maya owes me fifteen hundred for cakes", "debt", 1500, "Maya", "cakes"),
        make_row("Sunil owes two thousand five hundred for rice", "debt", 2500, "Sunil", "rice"),
        make_row("Mala owes seven hundred and fifty for sweets", "debt", 750, "Mala", "sweets"),
        make_row("Priya owes me one thousand five hundred for the wedding cake", "debt", 1500, "Priya", "wedding cake"),
        make_row("Kumari owes three thousand for lunch packets", "debt", 3000, "Kumari", "lunch packets"),
        make_row("Ajith has to pay me two thousand for the curtains", "debt", 2000, "Ajith", "curtains"),
        make_row("machan Ravi owes 1.5k for kiribath", "debt", 1500, "Ravi", "kiribath"),
        make_row("Sanduni akka owes eight hundred for hoppers", "debt", 800, "Sanduni", "hoppers"),
        make_row("Nimal took biscuits on credit four hundred and fifty", "debt", 450, "Nimal", "biscuits"),
        make_row("sold samosas to Lakshmi on credit five hundred", "debt", 500, "Lakshmi", "samosas"),
        make_row("sold two cakes for four thousand", "income", 4000, "", "two cakes"),
        make_row("made fifteen hundred selling cookies", "income", 1500, "", "cookies"),
        make_row("earned two thousand from sewing", "income", 2000, "", "sewing"),
        make_row("got nine hundred for a birthday cake", "income", 900, "", "birthday cake"),
        make_row("sold vegetables rs twelve hundred", "income", 1200, "", "vegetables"),
        make_row("sale five thousand today", "income", 5000, "", ""),
        make_row("spent two thousand on ingredients", "expense", 2000, "", "ingredients"),
        make_row("paid the helper fifteen hundred", "expense", 1500, "", "helper"),
        make_row("bought flour two thousand five hundred", "expense", 2500, "", "flour"),
        make_row("paid rent five thousand", "expense", 5000, "", "rent"),
        make_row("spent 1.2k on packaging", "expense", 1200, "", "packaging"),
        make_row("paid electricity bill thirty two hundred", "expense", 3200, "", "electricity bill"),
        # more name swaps with spoken amounts
        make_row("Nishani owes fifteen hundred for tailoring", "debt", 1500, "Nishani", "tailoring"),
        make_row("Aunty Silva owes two thousand for cake", "debt", 2000, "Aunty Silva", "cake"),
        make_row("Saman owes me 2.5k for rice", "debt", 2500, "Saman", "rice"),
        make_row("Farook owes six hundred for string hoppers", "debt", 600, "Farook", "string hoppers"),
        make_row("Amara took 2 kg rice on tab nine hundred", "debt", 900, "Amara", "2 kg rice"),
        make_row("today sold short eats one thousand", "income", 1000, "", "short eats"),
        make_row("sold kiribath for fifteen hundred cash", "income", 1500, "", "kiribath"),
        make_row("bought oil for nine hundred", "expense", 900, "", "oil"),
        make_row("paid market stall fee a thousand", "expense", 1000, "", "market stall fee"),
        make_row("spent eight hundred on gas today", "expense", 800, "", "gas"),
    ]
    # Fill remaining slots with systematic spoken variants until we clearly clear 200
    more_debt = []
    for name in NAMES:
        for amount, item in [(1500, "cakes"), (2000, "rice"), (1000, "hoppers"), (750, "sweets")]:
            for form in amount_forms(amount):
                if not any(c.isalpha() for c in form) and "k" not in form.lower() and "/=" not in form:
                    continue
                more_debt.append(make_row(f"{name} owes {form} for {item}", "debt", amount, name, item))
                more_debt.append(make_row(f"{name} owes me {form} for {item}", "debt", amount, name, item))
    RNG.shuffle(more_debt)

    for row in extras + more_debt:
        out.add(row)
        if len(out.rows) >= 280:
            break


def write_csv(rows: list[dict]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["phrase", "intent", "amount", "contact_name", "item"]
    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict]) -> None:
    by_intent: dict[str, int] = {}
    for r in rows:
        by_intent[r["intent"]] = by_intent.get(r["intent"], 0) + 1

    spoken_words = (
        "hundred", "thousand", "fifteen", "twenty", "thirty", "fifty",
        "seventy", "eighty", "ninety", "twelve", "eighteen", "seven fifty",
        "a thousand", "one thousand", "two thousand", "three thousand",
        "four thousand", "five thousand", "eight thousand",
    )
    spoken = sum(1 for r in rows if any(w in r["phrase"].lower() for w in spoken_words))
    slang = sum(
        1 for r in rows
        if any(s in r["phrase"].lower() for s in ("k", "/=", "rs ", "tab", "machan", "aiyo", "akka"))
    )
    print(f"Wrote {len(rows)} labelled phrases -> {OUT_PATH.relative_to(ROOT)}")
    print(f"  by intent: {by_intent}")
    print(f"  with spoken-number wording: {spoken}")
    print(f"  with slang / local markers: {slang}")


def main() -> None:
    seed = load_seed()
    out = PhraseSet()

    expand_seed_amount_forms(seed, out)
    add_debt_templates(out)
    add_income_templates(out)
    add_expense_templates(out)
    add_spoken_and_mix_extras(out)

    intent_order = {"debt": 0, "income": 1, "expense": 2}
    rows = sorted(out.rows, key=lambda r: (intent_order.get(r["intent"], 9), r["phrase"].lower()))
    write_csv(rows)

    print(f"Seed phrases: {len(seed)}")
    summarize(rows)
    if len(rows) < 200:
        raise SystemExit(f"Need at least 200 phrases, got {len(rows)}")


if __name__ == "__main__":
    main()
