"""VocalLedger API.  Run:  uvicorn main:app --reload   then open http://127.0.0.1:8000/docs"""
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()  # reads the API key from the .env file (never commit that file)

import database  # noqa: E402
import llm_parser  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="VocalLedger", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class TransactionIn(BaseModel):
    intent: Literal["income", "expense", "debt"]
    amount: float = Field(gt=0)
    item: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    due_days: int = Field(7, ge=0, le=365)


@app.get("/")
def root():
    return {"status": "VocalLedger is running"}


@app.post("/parse")
def parse(req: ParseRequest):
    """Text in, JSON out. Nothing is saved: the app shows this as a confirmation card first."""
    return llm_parser.parse_text(req.text)


@app.post("/transactions")
def create_transaction(tx: TransactionIn):
    """Save a confirmed transaction. Debts also appear in the Recovery Queue."""
    try:
        saved = database.add_transaction(
            tx.intent, tx.amount, tx.item, tx.contact_name, tx.phone, tx.due_days
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return {"saved": saved, "cash_in_hand": database.cash_in_hand()}


@app.get("/debts")
def debts(status: Literal["open", "paid"] = "open"):
    return database.list_debts(status)


@app.post("/debts/{receivable_id}/paid")
def pay_debt(receivable_id: int):
    try:
        result = database.mark_paid(receivable_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return {**result, "cash_in_hand": database.cash_in_hand()}


@app.get("/balance/{name}")
def balance(name: str):
    try:
        return database.get_balance(name)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@app.get("/cash-in-hand")
def cash_in_hand(on_date: Optional[date] = None):
    return database.cash_in_hand(on_date)
