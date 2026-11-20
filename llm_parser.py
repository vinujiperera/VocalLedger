"""LLM parser: spoken/typed text -> JSON. Falls back to the regex parser if the API fails."""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from rule_parser import parse_regex, unknown as regex_unknown

# Prefer the project .env, then the parent folder .env used for local secrets.
_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT.parent / ".env")

VALID_INTENTS = {"income", "expense", "debt"}

SYSTEM_PROMPT = """You extract bookkeeping data from short messages written or spoken by small vendors in Sri Lanka.
Reply with exactly ONE valid JSON object and no Markdown, explanation, or extra text.

JSON format:
{"intent":"income|expense|debt|unknown","amount":number|null,"contact_name":"name"|null,"item":"item"|null}

Intent rules:
- income: money received for a sale or service. contact_name must be null. Put the sold goods or service in item (null only for bare totals like "sale 5000 today").
- expense: money spent on goods or business costs. contact_name must be null.
- debt: a customer took goods/services on credit and owes the vendor. contact_name is the customer. item is what they took.
- unknown: not a bookkeeping entry, amount missing/unclear, or a customer paying an existing debt back ("Maya paid me 1500").

Amount rules:
- Output amount as a JSON number in rupees, never a string.
- Spoken forms: "fifteen hundred"=1500, "one thousand five hundred"=1500, "two thousand five hundred"=2500, "seven hundred and fifty"=750, "seven fifty"=750, "a thousand"=1000, "eight thousand"=8000.
- Slang/currency: "1.5k"=1500, "2.5k"=2500, "3k"=3000, "600/="=600, "rs 1200"=1200, "rupees 1200"=1200.

Name and filler rules:
- "machan", "aiyo", "note", "today", "please" are fillers — never put them in contact_name or item.
- Honorific AFTER a name ("Sanduni akka", "Saman aiya") is a title: keep only the personal name in contact_name ("Sanduni", "Saman").
- Honorific BEFORE a name stays with the name ("Aunty Silva", "Akka Nila").

Item rules:
- Keep quantities and units ("2 kg rice", "10 samosas", "3 loaves").
- Do not append fillers like "aiyo", "cash", "only", "today" to item unless they are part of the product name.
- For "sale 5000 today" / "sale 5k", intent=income, item=null.

Examples:
"Ajith owes me 2000 for curtains" -> {"intent":"debt","amount":2000,"contact_name":"Ajith","item":"curtains"}
"Amara took 2 kg rice on tab nine hundred" -> {"intent":"debt","amount":900,"contact_name":"Amara","item":"2 kg rice"}
"Maya owes fifteen hundred for cakes" -> {"intent":"debt","amount":1500,"contact_name":"Maya","item":"cakes"}
"Mala owes seven fifty for sweets" -> {"intent":"debt","amount":750,"contact_name":"Mala","item":"sweets"}
"machan Ravi owes 1.5k for kiribath" -> {"intent":"debt","amount":1500,"contact_name":"Ravi","item":"kiribath"}
"Sanduni akka owes eight hundred for hoppers" -> {"intent":"debt","amount":800,"contact_name":"Sanduni","item":"hoppers"}
"Kamala owes 800 for vegetables aiyo" -> {"intent":"debt","amount":800,"contact_name":"Kamala","item":"vegetables"}
"sold 3 loaves 600" -> {"intent":"income","amount":600,"contact_name":null,"item":"3 loaves"}
"Sold 4 short eats for a thousand" -> {"intent":"income","amount":1000,"contact_name":null,"item":"4 short eats"}
"sale five thousand today" -> {"intent":"income","amount":5000,"contact_name":null,"item":null}
"paid rent 5000/=" -> {"intent":"expense","amount":5000,"contact_name":null,"item":"rent"}
"Bought flour 2.5k" -> {"intent":"expense","amount":2500,"contact_name":null,"item":"flour"}
"Paid market stall fee a thousand" -> {"intent":"expense","amount":1000,"contact_name":null,"item":"market stall fee"}
"Maya paid me 1500" -> {"intent":"unknown","amount":null,"contact_name":null,"item":null}
"""


def default_llm_call(text):
    """Calls the Groq API."""
    from groq import Groq

    client = Groq()
    completion = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
        max_completion_tokens=200,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    return completion.choices[0].message.content


def _coerce_amount(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().lower().replace(",", "").replace("rs", "").replace("rupees", "")
        cleaned = cleaned.replace("/=", "").replace("/-", "").strip()
        if cleaned.endswith("k") and cleaned[:-1].replace(".", "", 1).isdigit():
            return float(cleaned[:-1]) * 1000
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _validate(data):
    if not isinstance(data, dict):
        return None
    if "intent" not in data:
        return None

    intent = data.get("intent")
    if intent not in VALID_INTENTS | {"unknown"}:
        return None

    amount_raw = data.get("amount")
    name = data.get("contact_name", None)
    item = data.get("item", None)

    if intent == "unknown":
        # Accept unknown even if the model left leftover null-ish fields.
        return unknown_result(source="llm")

    amount = _coerce_amount(amount_raw)
    if amount is None or amount <= 0:
        return None

    if name is not None and not isinstance(name, str):
        return None
    if item is not None and not isinstance(item, str):
        return None

    name = (name or "").strip() or None
    item = (item or "").strip() or None

    if intent == "debt":
        if not name:
            return None
    else:
        name = None

    return {
        "intent": intent,
        "amount": int(amount) if amount == int(amount) else round(amount, 2),
        "contact_name": name.title() if name else None,
        "item": item,
        "source": "llm",
        "needs_confirmation": True,
    }


def unknown_result(source="llm"):
    return {
        "intent": "unknown",
        "amount": None,
        "contact_name": None,
        "item": None,
        "source": source,
        "needs_confirmation": False,
        "message": "Sorry, I didn't understand that. Rephrase it or type a message like: Maya owes 1500 for cakes.",
    }


def _parse_json(raw):
    if not isinstance(raw, str):
        return None
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except (json.JSONDecodeError, TypeError):
        return None


def probe_llm(llm_call=None):
    """Return (ok, detail). Used by the eval script before spending 200+ calls."""
    if llm_call is None:
        if not os.getenv("GROQ_API_KEY"):
            return False, "GROQ_API_KEY is not set"
        llm_call = default_llm_call
    try:
        raw = llm_call("Maya owes 1500 for cakes")
        parsed = _validate(_parse_json(raw))
        if parsed and parsed.get("intent") == "debt" and parsed.get("amount") == 1500:
            return True, "llm ok"
        return False, f"unexpected probe result: {raw!r} -> {parsed!r}"
    except Exception as err:
        return False, f"{type(err).__name__}: {err}"


def parse_with_llm(text, llm_call=None):
    """Returns a validated LLM result, retrying once.

    Returns:
      dict result on success (including intentional unknown),
      None if the API failed or output stayed invalid after retry.
    """
    if llm_call is None:
        if not os.getenv("GROQ_API_KEY"):
            return None
        llm_call = default_llm_call

    saw_api_error = False
    for _ in range(2):
        try:
            result = _validate(_parse_json(llm_call(text)))
            if result is not None:
                return result
        except Exception:
            saw_api_error = True
    return None if saw_api_error else unknown_result(source="llm")


def parse_text(text, llm_call=None):
    """Main API entry: LLM first, regex fallback if the model is unreachable/unusable."""
    text = (text or "").strip()
    if not text:
        return unknown_result(source="llm")

    result = parse_with_llm(text, llm_call=llm_call)
    if result is not None:
        return result

    fallback = parse_regex(text)
    if fallback.get("intent") == "unknown":
        # Keep a consistent unknown shape; mark that regex also failed.
        out = regex_unknown(text)
        out["source"] = "regex"
        return out
    return fallback
