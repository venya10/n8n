const input = document.getElementById("apiBase");
const statusEl = document.getElementById("status");
const connection = document.getElementById("connection");

// A trailing slash here would turn `${apiBase}/health` into a double slash
// (".../health" -> ".../"+"/health"), which 404s — easy to type by habit or
// copy-paste, so strip it rather than let it silently break the connection.
function normalizeApiBase(value) {
  return value.trim().replace(/\/+$/, "");
}

chrome.storage.sync.get("apiBase", ({ apiBase }) => {
  input.value = apiBase || "http://localhost:8000";
  checkConnection(input.value);
});

document.getElementById("save").addEventListener("click", () => {
  const apiBase = normalizeApiBase(input.value);
  input.value = apiBase;
  chrome.storage.sync.set({ apiBase }, () => {
    statusEl.textContent = "Saved.";
    setTimeout(() => (statusEl.textContent = ""), 1500);
    checkConnection(apiBase);
  });
});

async function checkConnection(apiBase) {
  connection.textContent = "Checking connection…";
  connection.className = "";
  try {
    const res = await fetch(`${apiBase}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const body = await res.json();
    connection.textContent = body.model_loaded
      ? "Connected"
      : "Connected (semantic search unavailable)";
    connection.className = "ok";
  } catch {
    connection.textContent = "Backend unreachable";
    connection.className = "error";
  }
}
