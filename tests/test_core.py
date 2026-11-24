import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import llm_parser
from rule_parser import parse_regex


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Path(self.dir.name) / "test.db"
        database.init_db(self.db)
        self.now = datetime(2026, 11, 12, 10, 0, 0)

    def tearDown(self):
        self.dir.cleanup()

    def test_demo_seed_is_localized_and_idempotent(self):
        database.init_db(self.db, seed_demo=True)
        database.init_db(self.db, seed_demo=True)
        debts = database.list_debts(db_path=self.db)
        self.assertGreaterEqual(len(debts), 2)
        self.assertEqual(database.cash_in_hand(db_path=self.db)["liquid_cash"], 2250)

    def test_debt_creates_open_receivable_with_due_date(self):
        r = database.add_transaction("debt", 1500, "cakes", "Maya", now=self.now, db_path=self.db)
        self.assertEqual(r["due_date"], "2026-11-19")
        debts = database.list_debts(db_path=self.db)
        self.assertEqual(len(debts), 1)
        self.assertEqual(debts[0]["contact_name"], "Maya")
        self.assertEqual(debts[0]["amount"], 1500)

    def test_balance_is_case_insensitive_and_sums_open_debts(self):
        database.add_transaction("debt", 800, "veg", "Kamala", now=self.now, db_path=self.db)
        database.add_transaction("debt", 200, "rice", "kamala", now=self.now, db_path=self.db)
        b = database.get_balance("KAMALA", db_path=self.db)
        self.assertEqual(b["owed"], 1000)
        self.assertEqual(len(b["open_items"]), 2)

    def test_balance_unknown_contact(self):
        with self.assertRaises(LookupError):
            database.get_balance("Nobody", db_path=self.db)

    def test_mark_paid_clears_debt_and_counts_as_cash(self):
        r = database.add_transaction("debt", 1500, "cakes", "Maya", now=self.now, db_path=self.db)
        database.mark_paid(r["receivable_id"], now=self.now, db_path=self.db)
        self.assertEqual(database.list_debts(db_path=self.db), [])
        self.assertEqual(database.get_balance("Maya", db_path=self.db)["owed"], 0)
        cash = database.cash_in_hand(self.now.date(), db_path=self.db)
        self.assertEqual(cash["liquid_cash"], 1500)
        self.assertEqual(cash["outstanding_credit"], 0)

    def test_mark_paid_twice_or_missing(self):
        r = database.add_transaction("debt", 100, None, "Sam", now=self.now, db_path=self.db)
        database.mark_paid(r["receivable_id"], now=self.now, db_path=self.db)
        with self.assertRaises(ValueError):
            database.mark_paid(r["receivable_id"], now=self.now, db_path=self.db)
        with self.assertRaises(LookupError):
            database.mark_paid(999, now=self.now, db_path=self.db)

    def test_cash_in_hand_total_sales_vs_liquid_cash(self):
        database.add_transaction("income", 600, "loaves", now=self.now, db_path=self.db)
        database.add_transaction("debt", 1500, "cakes", "Maya", now=self.now, db_path=self.db)
        database.add_transaction("expense", 400, "gas", now=self.now, db_path=self.db)
        c = database.cash_in_hand(self.now.date(), db_path=self.db)
        self.assertEqual(c["total_sales"], 2100)
        self.assertEqual(c["liquid_cash"], 600)
        self.assertEqual(c["expenses"], 400)
        self.assertEqual(c["outstanding_credit"], 1500)

    def test_other_days_do_not_count(self):
        database.add_transaction("income", 600, None, now=self.now - timedelta(days=1), db_path=self.db)
        self.assertEqual(database.cash_in_hand(self.now.date(), db_path=self.db)["total_sales"], 0)

    def test_validation(self):
        with self.assertRaises(ValueError):
            database.add_transaction("debt", 100, None, None, db_path=self.db)  # debt needs a name
        with self.assertRaises(ValueError):
            database.add_transaction("income", -5, None, db_path=self.db)
        with self.assertRaises(ValueError):
            database.add_transaction("gift", 5, None, db_path=self.db)


class ParserTests(unittest.TestCase):
    def test_core_phrases(self):
        r = parse_regex("Maya owes 1500 for cakes")
        self.assertEqual((r["intent"], r["amount"], r["contact_name"], r["item"]), ("debt", 1500, "Maya", "cakes"))
        r = parse_regex("Maya owes me fifteen hundred for cakes")
        self.assertEqual((r["intent"], r["amount"]), ("debt", 1500))
        r = parse_regex("sold 3 loaves 600")
        self.assertEqual((r["intent"], r["amount"], r["item"]), ("income", 600, "3 loaves"))
        r = parse_regex("paid rent 5000/=")
        self.assertEqual((r["intent"], r["amount"], r["item"]), ("expense", 5000, "rent"))
        r = parse_regex("bought flour 2500")
        self.assertEqual((r["intent"], r["amount"], r["item"]), ("expense", 2500, "flour"))

    def test_unclear_input_is_unknown_with_a_message(self):
        for text in ("hello", "sold cakes", ""):
            r = parse_regex(text)
            self.assertEqual(r["intent"], "unknown")
            self.assertTrue(r["message"])

    def test_customer_paying_back_is_not_an_expense(self):
        self.assertEqual(parse_regex("Maya paid me 1500")["intent"], "unknown")


class LlmParserTests(unittest.TestCase):
    def test_default_llm_call_uses_groq_model(self):
        response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))]
        )
        create = Mock(return_value=response)
        groq_module = types.ModuleType("groq")
        groq_module.Groq = Mock(
            return_value=types.SimpleNamespace(
                chat=types.SimpleNamespace(
                    completions=types.SimpleNamespace(create=create)
                )
            )
        )

        with patch.dict(sys.modules, {"groq": groq_module}), patch.dict(
            "os.environ", {"GROQ_API_KEY": "test-key"}, clear=True
        ):
            result = llm_parser.default_llm_call("hello")

        self.assertEqual(result, "{}")
        self.assertEqual(create.call_args.kwargs["model"], "openai/gpt-oss-20b")
        self.assertEqual(create.call_args.kwargs["temperature"], 0)

    def test_uses_llm_answer_when_valid(self):
        fake = lambda text: '```json\n{"intent":"debt","amount":1500,"contact_name":"maya","item":"cakes"}\n```'
        r = llm_parser.parse_text("whatever", llm_call=fake)
        self.assertEqual((r["source"], r["contact_name"], r["amount"]), ("llm", "Maya", 1500))

    def test_retries_invalid_output_then_accepts_valid_output(self):
        calls = []
        responses = iter([
            '{"intent":"debt","amount":"many","contact_name":"Maya","item":"cakes"}',
            '{"intent":"debt","amount":1500,"contact_name":"Maya","item":"cakes"}',
        ])

        def fake(text):
            calls.append(text)
            return next(responses)

        r = llm_parser.parse_text("Maya owes 1500 for cakes", llm_call=fake)
        self.assertEqual(r["intent"], "debt")
        self.assertEqual(r["amount"], 1500)
        self.assertEqual(len(calls), 2)

    def test_falls_back_to_regex_when_api_fails(self):
        broken_calls = []

        def broken(text):
            broken_calls.append(text)
            raise RuntimeError("API down")

        r = llm_parser.parse_text("Maya owes 1500 for cakes", llm_call=broken)
        self.assertEqual(r["intent"], "debt")
        self.assertEqual(r["amount"], 1500)
        self.assertEqual(r["source"], "regex")
        self.assertEqual(len(broken_calls), 2)

    def test_retries_then_unknown_for_invalid_llm_output(self):
        junk = lambda text: "I think this is a debt"
        self.assertEqual(llm_parser.parse_text("hello there", llm_call=junk)["intent"], "unknown")

        bad = lambda text: '{"intent":"debt","amount":-5,"contact_name":"Maya","item":null}'
        # Invalid after retry -> unknown (confirmation/typed fallback is the safety net)
        self.assertEqual(
            llm_parser.parse_text("Maya owes 1500 for cakes", llm_call=bad)["intent"],
            "unknown",
        )

    def test_llm_unknown_is_kept_without_regex_override(self):
        fake = lambda text: '{"intent":"unknown","amount":null,"contact_name":null,"item":null}'
        self.assertEqual(llm_parser.parse_text("hello", llm_call=fake)["intent"], "unknown")
        owes_text = "Maya owes 1500 for cakes"
        self.assertEqual(llm_parser.parse_text(owes_text, llm_call=fake)["intent"], "unknown")

    def test_accepts_string_amounts_from_llm(self):
        fake = lambda text: '{"intent":"debt","amount":"1500","contact_name":"Maya","item":"cakes"}'
        r = llm_parser.parse_text("whatever", llm_call=fake)
        self.assertEqual(r["amount"], 1500)
        self.assertEqual(r["source"], "llm")

    def test_seven_fifty_spoken_form(self):
        r = parse_regex("Mala owes seven fifty for sweets")
        self.assertEqual((r["intent"], r["amount"], r["contact_name"], r["item"]), ("debt", 750, "Mala", "sweets"))



if __name__ == "__main__":
    unittest.main()
