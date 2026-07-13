/**
 * Advatech Chatbot Widget
 *
 * Usage: add this single line to any Advatech website, right before </body>:
 *
 *   <script src="https://YOUR-DEPLOYED-URL.com/widget.js"
 *           data-site="stationery"
 *           data-api-url="https://YOUR-API-URL.com"></script>
 *
 * data-site      -- which site's knowledge base to search (e.g. "stationery", "advaiot")
 * data-api-url   -- where your FastAPI backend is running
 *                    (defaults to http://localhost:8000 for local testing)
 */

(function () {
  // ---- Read config from the <script> tag itself ----
  const currentScript = document.currentScript;
  const SITE = currentScript.getAttribute("data-site") || "";
  const API_URL = currentScript.getAttribute("data-api-url") || "http://localhost:8000";

  // ---- Styles (scoped with unique class prefixes to avoid clashing with host site CSS) ----
  const style = document.createElement("style");
  style.textContent = `
    .advabot-bubble {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: #1a56db;
      color: white;
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(0,0,0,0.25);
      font-size: 26px;
      z-index: 999999;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.15s ease;
    }
    .advabot-bubble:hover { transform: scale(1.06); }

    .advabot-panel {
      position: fixed;
      bottom: 96px;
      right: 24px;
      width: 340px;
      max-width: calc(100vw - 32px);
      height: 460px;
      max-height: calc(100vh - 140px);
      background: #ffffff;
      border-radius: 14px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.25);
      display: none;
      flex-direction: column;
      overflow: hidden;
      z-index: 999999;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .advabot-panel.open { display: flex; }

    .advabot-header {
      background: #1a56db;
      color: white;
      padding: 14px 16px;
      font-weight: 600;
      font-size: 15px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .advabot-header button {
      background: none;
      border: none;
      color: white;
      font-size: 20px;
      cursor: pointer;
      line-height: 1;
    }

    .advabot-messages {
      flex: 1;
      overflow-y: auto;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: #f7f8fa;
    }

    .advabot-msg {
      max-width: 85%;
      padding: 9px 12px;
      border-radius: 12px;
      font-size: 13.5px;
      line-height: 1.4;
      white-space: pre-wrap;
    }
    .advabot-msg.bot {
      background: #ffffff;
      border: 1px solid #e5e7eb;
      align-self: flex-start;
      color: #1f2937;
    }
    .advabot-msg.user {
      background: #1a56db;
      color: white;
      align-self: flex-end;
    }
    .advabot-msg.loading {
      background: #ffffff;
      border: 1px solid #e5e7eb;
      align-self: flex-start;
      color: #9ca3af;
      font-style: italic;
    }

    .advabot-input-row {
      display: flex;
      border-top: 1px solid #e5e7eb;
      padding: 10px;
      gap: 8px;
      background: white;
    }
    .advabot-input-row input {
      flex: 1;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 13.5px;
      outline: none;
    }
    .advabot-input-row input:focus { border-color: #1a56db; }
    .advabot-input-row button {
      background: #1a56db;
      color: white;
      border: none;
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 13.5px;
      cursor: pointer;
    }
    .advabot-input-row button:disabled {
      background: #9ca3af;
      cursor: not-allowed;
    }
  `;
  document.head.appendChild(style);

  // ---- Build the DOM elements ----
  const bubble = document.createElement("button");
  bubble.className = "advabot-bubble";
  bubble.innerHTML = "💬";
  bubble.setAttribute("aria-label", "Open chat");

  const panel = document.createElement("div");
  panel.className = "advabot-panel";
  panel.innerHTML = `
    <div class="advabot-header">
      <span>Advatech Assistant</span>
      <button class="advabot-close" aria-label="Close chat">&times;</button>
    </div>
    <div class="advabot-messages"></div>
    <div class="advabot-input-row">
      <input type="text" placeholder="Ask a question..." />
      <button class="advabot-send">Send</button>
    </div>
  `;

  document.body.appendChild(bubble);
  document.body.appendChild(panel);

  const messagesEl = panel.querySelector(".advabot-messages");
  const inputEl = panel.querySelector("input");
  const sendBtn = panel.querySelector(".advabot-send");
  const closeBtn = panel.querySelector(".advabot-close");

  // ---- Greeting shown on first open ----
  let hasOpenedBefore = false;
  function addMessage(text, sender) {
    const msg = document.createElement("div");
    msg.className = `advabot-msg ${sender}`;
    msg.textContent = text;
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return msg;
  }

  bubble.addEventListener("click", () => {
    panel.classList.toggle("open");
    if (panel.classList.contains("open") && !hasOpenedBefore) {
      hasOpenedBefore = true;
      addMessage("Hi! Ask me anything about our products and services.", "bot");
      inputEl.focus();
    }
  });

  closeBtn.addEventListener("click", () => panel.classList.remove("open"));

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text) return;

    addMessage(text, "user");
    inputEl.value = "";
    sendBtn.disabled = true;
    inputEl.disabled = true;

    const loadingMsg = addMessage("Thinking...", "loading");

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, site: SITE }),
      });

      if (!response.ok) throw new Error(`Request failed: ${response.status}`);

      const data = await response.json();
      loadingMsg.remove();
      addMessage(data.answer, "bot");
    } catch (err) {
      loadingMsg.remove();
      addMessage(
        "Sorry, something went wrong reaching our assistant. Please try again in a moment.",
        "bot"
      );
      console.error("Advatech widget error:", err);
    } finally {
      sendBtn.disabled = false;
      inputEl.disabled = false;
      inputEl.focus();
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });
})();
