# VocalLedger

A hybrid voice-and-text financial tracker that helps female entrepreneurs keep their books and collect unpaid debts, without spreadsheets and without awkward conversations.

## About the project

Vendors speak or type natural shorthand, such as *"Maya owes 1500 for cakes"*. VocalLedger turns it into a structured ledger entry, updates daily cash flow, and sends automated SMS reminders for unpaid debts.

**How it works**

1. **Voice or text input:** a mic button uses speech-to-text, with typed entry as a fallback in noisy places.
2. **AI parser:** a pretrained large language model (LLM), called through an API with a strict JSON prompt, extracts the intent, amount, contact and item. We use a pretrained model and do not train our own.
3. **Confirmation card:** every AI result is shown on a card with Edit and Confirm buttons. Nothing is saved until the user confirms.
4. **Ledger:** the confirmed entry is saved, and debts are tracked as receivables.
5. **Recovery:** a daily script sends formal SMS reminders (Twilio) until the debt is marked as paid.


**Key features**

- **Hybrid input:** voice dictation or typing, with English, Sinhala and Tamil mixes supported
- **AI parsing with safeguards:** JSON validation, one retry, a mandatory confirmation card, and a rule-based fallback if the API is unreachable
- **Automated debt collection:** formal SMS reminders with the amount owed, cancelled automatically when a debt is marked as paid
- **Voice balance inquiries:** ask "How much does Kamala owe?" and hear the answer
- **Cash-in-Hand dashboard:** total sales, liquid cash and a Recovery Queue with a "Mark as Paid" button
- **Monthly PDF reports:** verifiable proof of income for banks and micro-loans

**Tech stack**

| Layer | Technology |
|-------|------------|
| Frontend | Web chat page with browser speech recognition |
| Backend | Python, FastAPI |
| AI parser | Pretrained LLM via API |
| Database | SQLite |
| Messaging | Twilio API (SMS) |
| Voice output | Text-to-Speech |
| Design | Figma |

## Why the project is useful

- Manual bookkeeping is too tedious during busy market hours, so records are often lost or never kept.
- Collecting credit debts from friends and neighbors is culturally awkward, which leads to lost revenue. The app sends the reminders on the vendor's behalf.
- Informal records give no proof of income. Monthly reports help entrepreneurs access bank accounts, micro-loans and financial aid.
- A pretrained AI handles odd phrasing and mixed languages, and the confirmation step keeps the ledger accurate.

**Privacy and safety:** only the spoken or typed phrase is sent to the LLM, never the full ledger, contact list or phone numbers. The API key is stored server-side in environment variables and is never committed to the repository.

**Accuracy:** we evaluate the parser on our own set of 200+ labelled phrases and improve the prompt from the failures we find.

## How to get started

```bash
git clone https://github.com/vinujiperera/VocalLedger.git
cd VocalLedger
pip install -r requirements.txt
```

Create a `.env` file (never commit it):

```env
GROQ_API_KEY=your_groq_api_key
# Optional; defaults to openai/gpt-oss-20b
LLM_MODEL=openai/gpt-oss-20b
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_number
```

Start the server and open the chat page:

```bash
uvicorn main:app --reload
```

Note: Twilio trial accounts can only send SMS to verified numbers.

## Where to get help

- Open an issue in the [GitHub Issues](https://github.com/vinujiperera/VocalLedger/issues) tab for bugs or questions.
- Contact the maintainers at `vinujipp821@gmail.com` or `lithashas@gmail.com`.


## License

MIT

## Demo data attribution

The optional demo ledger is localized from the MIT-licensed project dataset
`data/example_phrases.csv`, created for VocalLedger. Amounts use Sri Lankan rupees
and local items such as loaves, vegetables, rice, and buns. Demo records are only
added to an empty database and never overwrite existing transactions.
