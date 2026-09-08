const DEFAULT_API_BASE = "http://localhost:8000";

async function getSettings() {
  const { apiBase, useLlm } = await chrome.storage.sync.get(["apiBase", "useLlm"]);
  // Strip any trailing slash — `${apiBase}/suggest` on a value saved with
  // one would double up (".../"+"/suggest") and 404. popup.js normalizes
  // on save, but this guards against a value stored before that existed.
  return {
    apiBase: (apiBase || DEFAULT_API_BASE).replace(/\/+$/, ""),
    useLlm: Boolean(useLlm),
  };
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
    const { apiBase, useLlm } = await getSettings();
    const res = await fetch(`${apiBase}/suggest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context, top_k: 5, use_llm: useLlm }),
    });
    if (!res.ok) throw new Error(`API returned ${res.status}`);
    return await res.json();
  } catch (err) {
    return { error: String(err) };
  }
}

async function handleFeedback(payload) {
  try {
    const { apiBase } = await getSettings();
    await fetch(`${apiBase}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // best-effort; feedback loss isn't critical
  }
}
