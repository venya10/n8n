// Points at the live deployment by default — most people installing this
// extension aren't also running the backend locally (see background.js,
// which has the same default for when nothing's been saved yet).
const DEFAULT_API_BASE = "https://n8n-copilot-api.onrender.com";

const input = document.getElementById("apiBase");
const useLlmToggle = document.getElementById("useLlm");
const statusEl = document.getElementById("status");
const connection = document.getElementById("connection");
const connectionText = connection.querySelector(".text");

// A trailing slash here would turn `${apiBase}/health` into a double slash
// (".../health" -> ".../"+"/health"), which 404s — easy to type by habit or
// copy-paste, so strip it rather than let it silently break the connection.
function normalizeApiBase(value) {
  return value.trim().replace(/\/+$/, "");
}

chrome.storage.sync.get(["apiBase", "useLlm"], ({ apiBase, useLlm }) => {
  input.value = apiBase || DEFAULT_API_BASE;
  useLlmToggle.checked = Boolean(useLlm);
  checkConnection(input.value);
});

document.getElementById("save").addEventListener("click", () => {
  const apiBase = normalizeApiBase(input.value);
  const useLlm = useLlmToggle.checked;
  input.value = apiBase;
  chrome.storage.sync.set({ apiBase, useLlm }, () => {
    statusEl.textContent = "Saved.";
    setTimeout(() => (statusEl.textContent = ""), 1500);
    checkConnection(apiBase);
  });
});

async function checkConnection(apiBase) {
  connectionText.textContent = "Checking connection…";
  connection.className = "";
  try {
    const res = await fetch(`${apiBase}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const body = await res.json();
    connectionText.textContent = body.model_loaded
      ? "Connected"
      : "Connected (semantic search unavailable)";
    connection.className = "ok";
  } catch {
    connectionText.textContent = "Backend unreachable";
    connection.className = "error";
  }
}
