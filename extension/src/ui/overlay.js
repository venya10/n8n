/**
 * Floating suggestion panel injected into the n8n page.
 *
 * MVP interaction: clicking a suggestion doesn't auto-insert the node (n8n
 * doesn't expose a stable public API for programmatic node creation), it
 * copies the node's display name to the clipboard and highlights it so the
 * user can quickly find it in n8n's own "add node" search panel.
 */
const N8nCopilotOverlay = (() => {
  let panelEl = null;

  function ensurePanel() {
    if (panelEl) return panelEl;

    panelEl = document.createElement("div");
    panelEl.id = "n8n-copilot-panel";
    panelEl.hidden = true;
    panelEl.innerHTML = `
      <div class="n8nc-header">
        <span>Suggested next node</span>
        <button class="n8nc-close" title="Hide">✕</button>
      </div>
      <div class="n8nc-body"></div>
    `;
    panelEl.querySelector(".n8nc-close").addEventListener("click", () => {
      panelEl.hidden = true;
    });
    document.body.appendChild(panelEl);
    return panelEl;
  }

  function render(suggestions, onPick) {
    const panel = ensurePanel();
    const body = panel.querySelector(".n8nc-body");
    body.innerHTML = "";

    if (!suggestions || suggestions.length === 0) {
      body.innerHTML = `<div class="n8nc-empty">No suggestions yet.</div>`;
    } else {
      for (const s of suggestions) {
        const card = document.createElement("div");
        card.className = "n8nc-card";
        // `score` is a blended heuristic (0.6 * normalized transition
        // frequency + 0.4 * cosine similarity), not a calibrated
        // probability — rendering it as "73%" would invite reading it as
        // "73% likely correct". A relative-length bar shows ranking without
        // implying a confidence level the number doesn't actually carry.
        const meterWidth = Math.max(0, Math.min(100, Math.round(s.score * 100)));
        card.innerHTML = `
          <div class="n8nc-card-title">
            <span>${s.display_name}</span>
          </div>
          <div class="n8nc-meter" title="Relative match strength">
            <div class="n8nc-meter-fill" style="width: ${meterWidth}%"></div>
          </div>
          <div class="n8nc-card-desc">${s.description}</div>
        `;
        card.addEventListener("click", () => onPick(s));
        body.appendChild(card);
      }
    }

    panel.hidden = false;
  }

  function renderError(message) {
    const panel = ensurePanel();
    const body = panel.querySelector(".n8nc-body");
    body.innerHTML = `<div class="n8nc-error">${message}</div>`;
    panel.hidden = false;
  }

  function hide() {
    if (panelEl) panelEl.hidden = true;
  }

  return { render, renderError, hide };
})();
