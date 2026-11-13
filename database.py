"""SQLite ledger for VocalLedger: contacts, transactions and receivables (debts)."""
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "vocalledger.db"
INTENTS = ("income", "expense", "debt")

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE COLLATE NOCASE,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT NOT NULL CHECK (type IN ('income', 'expense', 'debt')),
    amount     REAL NOT NULL CHECK (amount > 0),
    item       TEXT,
    contact_id INTEGER REFERENCES contacts(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receivables (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id     INTEGER NOT NULL REFERENCES contacts(id),
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    amount         REAL NOT NULL,
    due_date       TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'paid')),
    paid_at        TEXT,
    reminders_sent INTEGER NOT NULL DEFAULT 0
);
"""


def _connect(db_path=DB_PATH):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=DB_PATH):
    """Create the three tables if they do not exist yet."""
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def _get_or_create_contact(conn, name, phone=None):
    row = conn.execute("SELECT id, phone FROM contacts WHERE name = ?", (name,)).fetchone()
    if row:
        if phone and not row["phone"]:
            conn.execute("UPDATE contacts SET phone = ? WHERE id = ?", (phone, row["id"]))
        return row["id"]
    cur = conn.execute("INSERT INTO contacts (name, phone) VALUES (?, ?)", (name, phone))
    return cur.lastrowid


def add_transaction(intent, amount, item=None, contact_name=None, phone=None,
                    due_days=7, now=None, db_path=DB_PATH):
    """Save income, expense or debt. A debt also creates an open receivable."""
    if intent not in INTENTS:
        raise ValueError(f"intent must be one of {INTENTS}")
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValueError("amount must be a number")
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    contact_name = (contact_name or "").strip() or None
    if intent == "debt" and not contact_name:
        raise ValueError("a debt needs a contact name")

    now = now or datetime.now()
    with _connect(db_path) as conn:
        contact_id = _get_or_create_contact(conn, contact_name, phone) if contact_name else None
        cur = conn.execute(
            "INSERT INTO transactions (type, amount, item, contact_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (intent, amount, item, contact_id, now.isoformat(timespec="seconds")),
        )
        transaction_id = cur.lastrowid
        receivable_id = None
        due_date = None
        if intent == "debt":
            due_date = (now.date() + timedelta(days=due_days)).isoformat()
            cur = conn.execute(
                "INSERT INTO receivables (contact_id, transaction_id, amount, due_date) VALUES (?, ?, ?, ?)",
                (contact_id, transaction_id, amount, due_date),
            )
            receivable_id = cur.lastrowid
    return {
        "transaction_id": transaction_id,
        "receivable_id": receivable_id,
        "intent": intent,
        "amount": amount,
        "item": item,
        "contact_name": contact_name,
        "due_date": due_date,
    }


def list_debts(status="open", db_path=DB_PATH):
    """Recovery Queue: debts, soonest due date first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT r.id AS receivable_id, c.name AS contact_name, c.phone, r.amount,
                      t.item, r.due_date, r.status, r.paid_at, t.created_at
               FROM receivables r
               JOIN contacts c ON c.id = r.contact_id
               JOIN transactions t ON t.id = r.transaction_id
               WHERE r.status = ?
               ORDER BY r.due_date, r.id""",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_paid(receivable_id, now=None, db_path=DB_PATH):
    """'Mark as Paid': clears the debt so no more reminders are sent."""
    now = now or datetime.now()
    with _connect(db_path) as conn:
        row = conn.execute("SELECT status FROM receivables WHERE id = ?", (receivable_id,)).fetchone()
        if row is None:
            raise LookupError("debt not found")
        if row["status"] == "paid":
            raise ValueError("debt is already marked as paid")
        conn.execute(
            "UPDATE receivables SET status = 'paid', paid_at = ? WHERE id = ?",
            (now.isoformat(timespec="seconds"), receivable_id),
        )
    return {"receivable_id": receivable_id, "status": "paid"}


def get_balance(name, db_path=DB_PATH):
    """'How much does Kamala owe?' Exact name first, then a partial match."""
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    with _connect(db_path) as conn:
        contact = conn.execute("SELECT id, name FROM contacts WHERE name = ?", (name,)).fetchone()
        if contact is None:
            contact = conn.execute(
                "SELECT id, name FROM contacts WHERE name LIKE ? ORDER BY name LIMIT 1", (f"%{name}%",)
            ).fetchone()
        if contact is None:
            raise LookupError(f"no contact named {name}")
        rows = conn.execute(
            """SELECT r.id AS receivable_id, r.amount, t.item, r.due_date
               FROM receivables r JOIN transactions t ON t.id = r.transaction_id
               WHERE r.contact_id = ? AND r.status = 'open' ORDER BY r.due_date""",
            (contact["id"],),
        ).fetchall()
    items = [dict(r) for r in rows]
    return {
        "contact_name": contact["name"],
        "owed": round(sum(i["amount"] for i in items), 2),
        "open_items": items,
    }


def cash_in_hand(on_date=None, db_path=DB_PATH):
    """Dashboard numbers for one day.

    total_sales  = cash sales + credit sales made that day
    liquid_cash  = cash sales + debts collected that day (money actually received)
    outstanding  = everything still owed to the vendor (all days)
    """
    day = (on_date or date.today()).isoformat()
    with _connect(db_path) as conn:
        def total(sql, *params):
            return round(conn.execute(sql, params).fetchone()[0] or 0, 2)

        cash_sales = total("SELECT SUM(amount) FROM transactions WHERE type='income' AND substr(created_at,1,10)=?", day)
        credit_sales = total("SELECT SUM(amount) FROM transactions WHERE type='debt' AND substr(created_at,1,10)=?", day)
        expenses = total("SELECT SUM(amount) FROM transactions WHERE type='expense' AND substr(created_at,1,10)=?", day)
        collected = total("SELECT SUM(amount) FROM receivables WHERE status='paid' AND substr(paid_at,1,10)=?", day)
        outstanding = total("SELECT SUM(amount) FROM receivables WHERE status='open'")
    return {
        "date": day,
        "total_sales": round(cash_sales + credit_sales, 2),
        "liquid_cash": round(cash_sales + collected, 2),
        "expenses": expenses,
        "debts_collected": collected,
        "outstanding_credit": outstanding,
    }
