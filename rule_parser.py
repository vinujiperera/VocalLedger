"""Rule-based (regex) parser. Used as the fallback when the LLM is unavailable or returns bad output."""
import re

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
SCALES = {"hundred": 100, "thousand": 1000, "lakh": 100000, "million": 1000000}
NUMBER_WORDS = set(UNITS) | set(SCALES)

NAME = r"[A-Za-z][A-Za-z'.-]*"
NAME2 = rf"{NAME}(?:\s+{NAME})?"
FILLERS = {"so", "and", "then", "today", "also", "ok", "okay", "hey", "note", "that", "yesterday", "please"}
ITEM_LEAD = {"for", "on", "of", "from", "selling", "the", "a", "an", "to", "cash", "only", "today", "at", "i", "we", "my", "some"}
ITEM_TRAIL = {"for", "on", "of", "from", "to", "at", "cash", "only", "today", "credit", "tab", "around", "about"}
CURRENCY = {"rs", "rs.", "rupees", "rupee", "lkr", "/=", "/-"}

DIGIT_RE = re.compile(r"(?<![\w.])((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(\s?[kK])?(?![\w])(\s?/[=-])?")
CREDIT = r"(?:credit|tab|account)"

DEBT_OWES = re.compile(rf"(?P<name>{NAME2})\s+(?:owes|owe|has\s+to\s+pay)(?:\s+me)?\s+(?P<rest>.+)", re.I)
DEBT_TOOK = re.compile(rf"(?P<name>{NAME2})\s+(?:took|got|bought|has\s+taken)\s+(?P<item>.+?)\s+on\s+{CREDIT}\b", re.I)
DEBT_SOLD_TO = re.compile(rf"(?:sold|gave)\s+(?P<item>.+?)\s+to\s+(?P<name>{NAME})\s+on\s+{CREDIT}\b", re.I)
DEBT_GAVE = re.compile(rf"(?:sold|gave)\s+(?P<name>{NAME})\s+(?P<item>.+?)\s+on\s+{CREDIT}\b", re.I)
PAID_BACK_RE = re.compile(r"\bpaid\s+(?:me|back)\b|\b(?:returned|gave\s+back)\b", re.I)
EXPENSE_RE = re.compile(r"\b(paid|spent|bought|purchased)\b", re.I)
INCOME_RE = re.compile(r"\b(sold|sale|sell|earned|received|got|made)\b", re.I)


def words_to_number(words):
    total, current = 0, 0
    for w in words:
        if w in UNITS:
            current += UNITS[w]
        elif w == "hundred":
            current = (current or 1) * 100
        else:
            total += (current or 1) * SCALES[w]
            current = 0
    return total + current


def find_amounts(text):
    """All amounts in the text as (value, start, end). Handles 1,500 / 1.5k / 600/= / fifteen hundred."""
    found = []
    for m in DIGIT_RE.finditer(text):
        value = float(m.group(1).replace(",", ""))
        if m.group(2):
            value *= 1000
        found.append((value, m.start(), m.end()))
    tokens = [(m.group().lower(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z]+", text)]
    i = 0
    while i < len(tokens):
        if tokens[i][0] in NUMBER_WORDS:
            j, words = i, [tokens[i][0]]
            while j + 1 < len(tokens):
                gap = text[tokens[j][2]:tokens[j + 1][1]]
                nxt = tokens[j + 1][0]
                if nxt in NUMBER_WORDS and re.fullmatch(r"[\s-]+", gap):
                    j += 1; words.append(nxt)
                elif nxt == "and" and j + 2 < len(tokens) and tokens[j + 2][0] in NUMBER_WORDS and re.fullmatch(r"\s+", gap):
                    j += 2; words.append(tokens[j][0])
                else:
                    break
            value = words_to_number(words)
            if value > 0:
                found.append((float(value), tokens[i][1], tokens[j][2]))
            i = j + 1
        else:
            i += 1
    return found


def best_amount(text):
    found = find_amounts(text)
    if not found:
        return None, None
    value, start, end = max(found, key=lambda f: f[0])
    return (int(value) if value == int(value) else round(value, 2)), (start, end)


def clean_item(text):
    tokens = [t for t in re.split(r"\s+", text.strip()) if t and t.lower() not in CURRENCY]
    while tokens and tokens[0].lower() in ITEM_LEAD:
        tokens.pop(0)
    while tokens and tokens[-1].lower() in ITEM_TRAIL:
        tokens.pop()
    item = " ".join(tokens).strip(" .,;")
    return item or None


def clean_name(raw):
    words = raw.split()
    while words and words[0].lower() in FILLERS:
        words.pop(0)
    name = " ".join(words).strip(" .,'-")
    return name.title() if name else None


def _remove_span(text, span):
    return (text[:span[0]] + " " + text[span[1]:]) if span else text


def _result(intent, amount, name=None, item=None):
    return {"intent": intent, "amount": amount, "contact_name": name, "item": item,
            "source": "regex", "needs_confirmation": True}


def unknown(text):
    return {"intent": "unknown", "amount": None, "contact_name": None, "item": None,
            "source": "regex", "needs_confirmation": False,
            "message": "Sorry, I didn't understand that. Try something like: Maya owes 1500 for cakes."}


def parse_regex(text):
    text = " ".join((text or "").split())
    if not text:
        return unknown(text)
    amount, span = best_amount(text)
    if amount is None:
        return unknown(text)

    if PAID_BACK_RE.search(text):
        out = unknown(text)
        out["message"] = "That sounds like a customer paying you back. Open the Recovery Queue and tap Mark as Paid."
        return out

    m = DEBT_OWES.search(text)
    if m:
        name = clean_name(m.group("name"))
        rest = m.group("rest")
        a, s = best_amount(rest)
        item = clean_item(_remove_span(rest, s)) if s else clean_item(rest)
        if name:
            return _result("debt", a if a is not None else amount, name, item)

    for pattern in (DEBT_TOOK, DEBT_SOLD_TO, DEBT_GAVE):
        m = pattern.search(text)
        if m:
            name = clean_name(m.group("name"))
            if name:
                return _result("debt", amount, name, clean_item(m.group("item")))

    for regex, intent in ((EXPENSE_RE, "expense"), (INCOME_RE, "income")):
        m = regex.search(text)
        if m:
            working = _remove_span(text, span)
            working = regex.sub(" ", working, count=1)
            return _result(intent, amount, None, clean_item(working))
    return unknown(text)
