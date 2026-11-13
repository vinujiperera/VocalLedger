"""LLM parser: spoken/typed text -> JSON. Falls back to the regex parser on any problem."""
import json
import os
import re

from dotenv import load_dotenv

from rule_parser import parse_regex, unknown

load_dotenv()

VALID_INTENTS = {"income", "expense", "debt"}

SYSTEM_PROMPT = """You extract bookkeeping data from short messages written or spoken by small vendors in Sri Lanka.
Reply with ONE JSON object and nothing else. Keys:
  "intent": "income" (money received from a sale), "expense" (money spent), "debt" (a customer owes the vendor / sold on credit), or "unknown"
  "amount": number in rupees (convert spoken numbers: "fifteen hundred" = 1500, "1.5k" = 1500, "600/=" = 600)
  "contact_name": the customer's name for a debt, otherwise null
  "item": what was sold or bought, otherwise null
If the message is not a bookkeeping entry, or the amount is missing or unclear, use intent "unknown" and amount null.
Never guess a name or an amount that is not in the message.
Examples:
"Maya owes me fifteen hundred for cakes" -> {"intent":"debt","amount":1500,"contact_name":"Maya","item":"cakes"}
"sold 3 loaves 600" -> {"intent":"income","amount":600,"contact_name":null,"item":"3 loaves"}
"paid rent 5000/=" -> {"intent":"expense","amount":5000,"contact_name":null,"item":"rent"}"""


def default_llm_call(text):
    """Calls the Groq API."""
    from groq import Groq

    client = Groq()
    completion = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
        max_completion_tokens=200,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    return completion.choices[0].message.content


def _validate(data):
    if not isinstance(data, dict) or data.get("intent") not in VALID_INTENTS | {"unknown"}:
        return None
    if data["intent"] == "unknown":
        return None
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    name = (data.get("contact_name") or None)
    if data["intent"] == "debt" and not name:
        return None
    return {
        "intent": data["intent"],
        "amount": int(amount) if amount == int(amount) else round(amount, 2),
        "contact_name": name.strip().title() if name else None,
        "item": (data.get("item") or None),
        "source": "llm",
        "needs_confirmation": True,
    }


def parse_with_llm(text, llm_call=None):
    """Returns a validated dict, or None if the LLM is unavailable or its answer is unusable."""
    if llm_call is None:
        if not os.getenv("GROQ_API_KEY"):
            return None
        llm_call = default_llm_call
    try:
        raw = llm_call(text)
        match = re.search(r"\{.*\}", raw, re.S)
        return _validate(json.loads(match.group())) if match else None
    except Exception:
        return None


def parse_text(text, llm_call=None):
    """Main entry point used by the API: try the LLM first, then the regex parser."""
    text = (text or "").strip()
    if not text:
        return unknown(text)
    return parse_with_llm(text, llm_call) or parse_regex(text)
