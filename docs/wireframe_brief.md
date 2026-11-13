# Wireframe brief (V6): chat screen and dashboard

## Chat screen
- Top: app name, language toggle (EN / SI / TA).
- Message list: the vendor's message appears as a bubble (voice text or typed).
- AI confirmation card appears under each message (nothing is saved yet):
  - Title: "Is this right?"
  - Fields: Type (Debt / Income / Expense), Amount (Rs.), Person, Item.
  - Buttons: Save (primary), Edit, Cancel.
  - Small label: "Read by AI" or "Read by rules" (the API returns source: llm / regex).
- "I didn't understand" error state (API returns intent: unknown with a message):
  - Bubble: "Sorry, I didn't understand that. Try: Maya owes 1500 for cakes."
  - Two example chips the user can tap to fill the box.
  - If the message says it was a payment, show a button "Open Recovery Queue".
- Bottom: big mic button (listening animation), text box, Send. Typed input must always work.

## Dashboard
- Two big numbers: Total Sales (today) and Liquid Cash (money received today).
- Smaller row: Expenses today, Still owed to you.
- Button: "Recovery Queue" with a count badge.
- Quick actions: "How much does ___ owe?" (mic), "Monthly report".
