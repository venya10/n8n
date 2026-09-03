const input = document.getElementById("apiBase");
const status = document.getElementById("status");

chrome.storage.sync.get("apiBase", ({ apiBase }) => {
  input.value = apiBase || "http://localhost:8000";
});

document.getElementById("save").addEventListener("click", () => {
  chrome.storage.sync.set({ apiBase: input.value.trim() }, () => {
    status.textContent = "Saved.";
    setTimeout(() => (status.textContent = ""), 1500);
  });
});
