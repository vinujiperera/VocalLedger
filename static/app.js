const messages = document.getElementById("messages");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const micButton = document.getElementById("micButton");
const listeningStatus = document.getElementById("listeningStatus");
const quickPrompts = document.getElementById("quickPrompts");

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

function addUserMessage(text) {
  const row = document.createElement("div");
  row.className = "user-row";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  messages.appendChild(row);
  scrollToBottom();
}

function addAssistantMessage(text) {
  const row = document.createElement("div");
  row.className = "assistant-message";
  row.innerHTML = `
    <span class="assistant-avatar">VL</span>
    <div class="assistant-copy">
      <p>${escapeHtml(text)}</p>
    </div>`;
  messages.appendChild(row);
  scrollToBottom();
}

function formatAmount(amount) {
  return Number(amount).toLocaleString("en-LK", { maximumFractionDigits: 2 });
}

function addConfirmation(result) {
  const card = document.createElement("div");
  card.className = "confirmation-card";
  card.innerHTML = `
    <div class="card-heading">
      <h2>Is this right?</h2>
      <span class="source-label">Read by ${escapeHtml(result.source || "AI")}</span>
    </div>
    <p class="confirmation-note">Nothing is saved until you confirm.</p>
    <div class="card-grid">
      <div class="field">
        <label>Type</label>
        <select name="intent">
          ${["income", "expense", "debt"].map(v => `<option value="${v}" ${v === result.intent ? "selected" : ""}>${v[0].toUpperCase() + v.slice(1)}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label>Amount (Rs.)</label>
        <input name="amount" type="number" min="0.01" step="0.01" value="${result.amount ?? ""}" />
      </div>
      <div class="field full">
        <label>Person</label>
        <input name="contact_name" type="text" value="${escapeHtml(result.contact_name || "")}" placeholder="Required for debts" />
      </div>
      <div class="field full">
        <label>Item</label>
        <input name="item" type="text" value="${escapeHtml(result.item || "")}" placeholder="Optional" />
      </div>
    </div>
    <div class="card-actions">
      <button type="button" class="cancel-button">Cancel</button>
      <button type="button" class="edit-button">Edit</button>
      <button type="button" class="save-button">Confirm</button>
    </div>`;

  const inputs = [...card.querySelectorAll("input, select")];
  inputs.forEach(el => el.disabled = true);
  card.querySelector(".edit-button").addEventListener("click", () => {
    inputs.forEach(el => el.disabled = false);
    card.querySelector(".edit-button").blur();
  });
  card.querySelector(".cancel-button").addEventListener("click", () => {
    card.remove();
  });
  card.querySelector(".save-button").addEventListener("click", async () => {
    const intent = card.querySelector('[name="intent"]').value;
    const amount = Number(card.querySelector('[name="amount"]').value);
    const contactName = card.querySelector('[name="contact_name"]').value.trim();
    const item = card.querySelector('[name="item"]').value.trim();
    if (!amount || amount <= 0 || (intent === "debt" && !contactName)) {
      card.querySelector(".save-button").textContent = "Check fields";
      return;
    }

    const saveButton = card.querySelector(".save-button");
    saveButton.disabled = true;
    saveButton.textContent = "Saving...";
    try {
      const response = await fetch("/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          intent,
          amount,
          item: item || null,
          contact_name: contactName || null,
          due_days: 7
        })
      });
      if (!response.ok) throw new Error("Could not save");
      const saved = await response.json();
      card.innerHTML = `<div class="saved-label">Saved · Rs. ${formatAmount(saved.saved.amount)} · ${escapeHtml(saved.saved.intent)}</div>`;
    } catch (error) {
      saveButton.disabled = false;
      saveButton.textContent = "Try again";
    }
  });
  messages.appendChild(card);
  scrollToBottom();
}

async function addUnknown() {
  const card = document.createElement("div");
  card.className = "confirmation-card unknown-card";
  card.innerHTML = `
    <div class="card-heading"><h2>I didn&apos;t understand</h2></div>
    <p style="margin:0;color:#66776f;line-height:1.5">Try a clear entry like “Maya owes 1500 for cakes”.</p>
    <button type="button" class="save-button recovery-button">Open Recovery Queue</button>`;
  card.querySelector(".recovery-button").addEventListener("click", async () => {
    try {
      const response = await fetch("/debts");
      const debts = await response.json();
      if (!debts.length) {
        addAssistantMessage("The Recovery Queue is empty.");
      } else {
        addAssistantMessage(debts.map(d => `${d.contact_name}: Rs. ${formatAmount(d.amount)} for ${d.item || "goods"}`).join("\n"));
      }
    } catch (error) {
      addAssistantMessage("Could not open the Recovery Queue.");
    }
  });
  messages.appendChild(card);
  scrollToBottom();
}

async function sendMessage(text) {
  const cleanText = text.trim();
  if (!cleanText) return;
  addUserMessage(cleanText);
  input.value = "";
  quickPrompts.style.display = "none";

  const loading = document.createElement("div");
  loading.className = "assistant-message";
  loading.innerHTML = `<span class="assistant-avatar">VL</span><div class="assistant-copy"><p>Reading…</p></div>`;
  messages.appendChild(loading);
  scrollToBottom();

  try {
    const response = await fetch("/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: cleanText })
    });
    if (!response.ok) throw new Error("Parse failed");
    const result = await response.json();
    loading.remove();
    if (result.intent === "unknown") addUnknown();
    else addConfirmation(result);
  } catch (error) {
    loading.remove();
    addAssistantMessage("I couldn't reach the parser. Please try again.");
  }
}

form.addEventListener("submit", event => {
  event.preventDefault();
  sendMessage(input.value);
});

quickPrompts.addEventListener("click", event => {
  const button = event.target.closest("[data-text]");
  if (button) sendMessage(button.dataset.text);
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SpeechRecognition) {
  micButton.title = "Speech recognition is not supported by this browser";
  micButton.addEventListener("click", () => {
    listeningStatus.textContent = "Voice is unavailable; please type below";
  });
} else {
  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.addEventListener("start", () => {
    micButton.classList.add("listening");
    listeningStatus.textContent = "Listening in English...";
  });
  recognition.addEventListener("result", event => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    input.value = transcript;
  });
  recognition.addEventListener("end", () => {
    micButton.classList.remove("listening");
    listeningStatus.textContent = "";
  });
  recognition.addEventListener("error", event => {
    micButton.classList.remove("listening");
    listeningStatus.textContent = event.error === "not-allowed"
      ? "Microphone access was blocked"
      : "Could not hear that; please try again";
  });
  micButton.addEventListener("click", () => recognition.start());
}
