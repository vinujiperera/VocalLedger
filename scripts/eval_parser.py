"""Measure parser accuracy on the labelled test set.

Uses data/test_phrases.csv when present (200+ expanded phrases), otherwise the
hand-written seed in data/example_phrases.csv.

Writes:
  data/parser_evaluation.json  - summary + full failure list
  data/parser_failure_log.csv  - one row per failure (easy to skim)

Run:  py scripts/eval_parser.py
      py scripts/eval_parser.py --regex-only
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_parser import parse_text, parse_with_llm, probe_llm  # noqa: E402
from rule_parser import parse_regex  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA / "test_phrases.csv" if (DATA / "test_phrases.csv").exists() else DATA / "example_phrases.csv"
REPORT_PATH = DATA / "parser_evaluation.json"
FAILURE_CSV_PATH = DATA / "parser_failure_log.csv"


def norm(v):
    return (str(v) if v is not None else "").strip().lower()


def check(parsed, row):
    core = (
        parsed["intent"] == row["intent"]
        and parsed["amount"] is not None
        and float(parsed["amount"]) == float(row["amount"])
        and norm(parsed.get("contact_name")) == norm(row["contact_name"])
    )
    item = core and norm(parsed.get("item")) == norm(row["item"])
    return core, item


def failure_kind(row, parsed, core, item):
    if parsed.get("intent") != row["intent"]:
        return "intent"
    try:
        amount_ok = parsed.get("amount") is not None and float(parsed["amount"]) == float(row["amount"])
    except (TypeError, ValueError):
        amount_ok = False
    if not amount_ok:
        return "amount"
    if norm(parsed.get("contact_name")) != norm(row["contact_name"]):
        return "name"
    if not item:
        return "item"
    return "other"


def run(label, parse):
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    core_ok = item_ok = 0
    intent_counts = defaultdict(lambda: {"total": 0, "core": 0, "item": 0})
    source_counts = defaultdict(int)
    failures = []

    for row in rows:
        parsed = parse(row["phrase"])
        core, item_match = check(parsed, row)
        core_ok += core
        item_ok += core and item_match
        intent_counts[row["intent"]]["total"] += 1
        intent_counts[row["intent"]]["core"] += int(core)
        intent_counts[row["intent"]]["item"] += int(core and item_match)
        source_counts[parsed.get("source") or "unknown"] += 1

        if not (core and item_match):
            failures.append({
                "phrase": row["phrase"],
                "expected_intent": row["intent"],
                "expected_amount": row["amount"],
                "expected_contact_name": row["contact_name"],
                "expected_item": row["item"],
                "actual_intent": parsed.get("intent"),
                "actual_amount": parsed.get("amount"),
                "actual_contact_name": parsed.get("contact_name"),
                "actual_item": parsed.get("item"),
                "source": parsed.get("source"),
                "kind": failure_kind(row, parsed, core, item_match),
                "core_match": core,
                "item_match": item_match,
            })

    n = len(rows)
    print(f"{label}")
    print(f"  dataset: {CSV_PATH.name} ({n} phrases)")
    print(f"  core (intent+amount+name): {core_ok}/{n} ({core_ok / n:.1%})")
    print(f"  full (core+item):          {item_ok}/{n} ({item_ok / n:.1%})")
    print("  per intent:")
    per_intent = {}
    for intent in ("debt", "income", "expense"):
        counts = intent_counts[intent]
        if not counts["total"]:
            continue
        per_intent[intent] = counts
        print(
            f"    {intent:7}  core {counts['core']}/{counts['total']} "
            f"({counts['core'] / counts['total']:.1%})  "
            f"item {counts['item']}/{counts['total']} "
            f"({counts['item'] / counts['total']:.1%})"
        )
    print(f"  sources: {dict(source_counts)}")
    print(f"  failures: {len(failures)}")
    return {
        "label": label,
        "phrase_count": n,
        "core_correct": core_ok,
        "item_correct": item_ok,
        "core_accuracy": round(core_ok / n, 4) if n else 0,
        "item_accuracy": round(item_ok / n, 4) if n else 0,
        "per_intent": per_intent,
        "sources": dict(source_counts),
        "failures": failures,
    }


def write_reports(report):
    DATA.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    fieldnames = [
        "kind", "phrase",
        "expected_intent", "actual_intent",
        "expected_amount", "actual_amount",
        "expected_contact_name", "actual_contact_name",
        "expected_item", "actual_item",
        "source", "core_match", "item_match",
    ]
    with FAILURE_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["failures"])
    print(f"  wrote {REPORT_PATH.relative_to(DATA.parent)}")
    print(f"  wrote {FAILURE_CSV_PATH.relative_to(DATA.parent)}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate VocalLedger parser accuracy")
    parser.add_argument(
        "--regex-only",
        action="store_true",
        help="Evaluate only the rule-based fallback parser",
    )
    parser.add_argument(
        "--llm-only",
        action="store_true",
        help="Evaluate only the LLM path (no regex fallback)",
    )
    args = parser.parse_args()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(CSV_PATH),
        "llm_key_configured": bool(os.getenv("GROQ_API_KEY")),
        "model": os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
    }

    if args.regex_only:
        summary = run("Regex parser", parse_regex)
        report.update(summary)
        write_reports(report)
        return

    if args.llm_only:
        ok, detail = probe_llm()
        report["llm_probe"] = {"ok": ok, "detail": detail}
        if not ok:
            print(f"LLM probe failed: {detail}")
            print("Fix GROQ_API_KEY in D:\\Projects\\VocalLedger\\.env (key should start with gsk_ and be ~56 chars), then re-run.")
            report.update({
                "label": "LLM-only (probe failed)",
                "phrase_count": 0,
                "core_correct": 0,
                "item_correct": 0,
                "per_intent": {},
                "failures": [],
                "error": detail,
            })
            write_reports(report)
            sys.exit(2)

        def llm_only(text):
            result = parse_with_llm(text)
            return result if result is not None else {
                "intent": "unknown", "amount": None, "contact_name": None, "item": None, "source": "llm"
            }

        summary = run("LLM parser (no regex fallback)", llm_only)
        report.update(summary)
        write_reports(report)
        return

    # Default: full pipeline, but require a working LLM so the report measures the AI parser.
    ok, detail = probe_llm()
    report["llm_probe"] = {"ok": ok, "detail": detail}
    if not ok:
        print(f"LLM probe failed: {detail}")
        print("Running regex-only baseline so you still get a failure log.")
        print("After fixing GROQ_API_KEY, re-run: py scripts/eval_parser.py --llm-only")
        summary = run("Regex parser (LLM unavailable)", parse_regex)
        report.update(summary)
        report["note"] = (
            "LLM probe failed, so this report is the regex baseline only. "
            "It does not measure AI-parser accuracy."
        )
        write_reports(report)
        sys.exit(2)

    summary = run("Full pipeline (LLM first, regex fallback)", parse_text)
    report.update(summary)
    write_reports(report)


if __name__ == "__main__":
    main()
