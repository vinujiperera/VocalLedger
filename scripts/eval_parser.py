"""Measure parser accuracy on data/example_phrases.csv.  Run:  python scripts/eval_parser.py"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_parser import parse_text  # uses Groq if GROQ_API_KEY is set, otherwise the regex parser
from rule_parser import parse_regex

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "example_phrases.csv"


def norm(v):
    return (str(v) if v is not None else "").strip().lower()


def check(parsed, row):
    core = (
        parsed["intent"] == row["intent"]
        and parsed["amount"] is not None and float(parsed["amount"]) == float(row["amount"])
        and norm(parsed["contact_name"]) == norm(row["contact_name"])
    )
    item = norm(parsed["item"]) == norm(row["item"])
    return core, item


def run(label, parse):
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    core_ok = item_ok = 0
    for row in rows:
        parsed = parse(row["phrase"])
        core, item = check(parsed, row)
        core_ok += core
        item_ok += core and item
        if not (core and item):
            print(f"  MISS  {row['phrase']!r} -> {parsed}")
    n = len(rows)
    print(f"{label}: intent+amount+name {core_ok}/{n} ({core_ok / n:.0%}), item also correct {item_ok}/{n} ({item_ok / n:.0%})")


if __name__ == "__main__":
    run("Regex parser", parse_regex)
    run("Full pipeline (LLM first, regex fallback)", parse_text)
