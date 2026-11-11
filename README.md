# VocalLedger

A hybrid voice-and-text financial tracker that helps female entrepreneurs keep their books and collect unpaid debts, without spreadsheets and without awkward conversations.

## About the project

Vendors speak or type natural shorthand, such as *"Maya owes 1500 for cakes"*. VocalLedger extracts the details, updates daily cash flow, and sends automated SMS reminders for unpaid debts.

**Key features**

- **Hybrid input:** speech-to-text dictation, with typing as a fallback in noisy places
- **Regex parsing:** a deterministic engine extracts intent (income, expense or debt), amount and contact name
- **Automated debt collection:** formal SMS reminders via Twilio with the amount owed and bank details
- **Voice balance inquiries:** ask "How much does Kamala owe?" and hear the answer
- **Cash-in-Hand dashboard:** total sales, liquid cash and a Recovery Queue with a "Mark as Paid" button
- **Monthly PDF reports:** verifiable proof of income for banks and micro-loans

**Tech stack:** Flutter / React Native, Python (Regex), PostgreSQL / Firebase, Twilio API, Speech-to-Text and Text-to-Speech.

## Why the project is useful

- Manual bookkeeping is too tedious during busy market hours, so records are often lost or never kept.
- Collecting credit debts from friends and neighbors is culturally awkward, which leads to lost revenue. The app sends the reminders on the vendor's behalf.
- Informal records give no proof of income. Monthly reports help entrepreneurs access bank accounts, micro-loans and financial aid.

## How to get started

```bash
git clone https://github.com/vinujiperera/VocalLedger.git
cd VocalLedger
```

1. Add your database and Twilio credentials to a `.env` file.
2. Install the backend dependencies and start the server.
3. Run the mobile app on an emulator or device.

## Where to get help

- Open an issue in the [GitHub Issues](https://github.com/vinujiperera/VocalLedger/issues) tab for bugs or questions.
- Contact the maintainers at `vinujipp821@gmail.com` or `lithashas@gmail.com`.


## License

MIT
