const DEFAULT_API_BASE = "http://localhost:8000";

async function getApiBase() {
  const { apiBase } = await chrome.storage.sync.get("apiBase");
  return apiBase || DEFAULT_API_BASE;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "SUGGEST") {
    handleSuggest(message.context).then(sendResponse);
    return true; // keep the message channel open for the async response
  }
  if (message.type === "FEEDBACK") {
    handleFeedback(message.payload);
    return false;
  }
});

async function handleSuggest(context) {
  try {
    const apiBase = await getApiBase();
    const res = await fetch(`${apiBase}/suggest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context, top_k: 5, use_llm: false }),
    });
    if (!res.ok) throw new Error(`API returned ${res.status}`);
    return await res.json();
  } catch (err) {
    return { error: String(err) };
  }
}

async function handleFeedback(payload) {
  try {
    const apiBase = await getApiBase();
    await fetch(`${apiBase}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // best-effort; feedback loss isn't critical
  }
}
