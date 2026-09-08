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

  const POSITION_STORAGE_KEY = "n8nCopilotPanelPosition";

  function loadSavedPosition() {
    try {
      const raw = localStorage.getItem(POSITION_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null; // corrupt/blocked storage — just fall back to the default position
    }
  }

  function savePosition(left, top) {
    try {
      localStorage.setItem(POSITION_STORAGE_KEY, JSON.stringify({ left, top }));
    } catch {
      // best-effort; losing the remembered position isn't worth surfacing an error
    }
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function applyPosition(panel, left, top) {
    // The panel defaults to `bottom`/`right` positioning (see overlay.css);
    // once dragged, switch to explicit `left`/`top` so it stays wherever the
    // user put it instead of re-anchoring to a corner.
    const maxLeft = window.innerWidth - panel.offsetWidth;
    const maxTop = window.innerHeight - panel.offsetHeight;
    const clampedLeft = clamp(left, 0, Math.max(0, maxLeft));
    const clampedTop = clamp(top, 0, Math.max(0, maxTop));
    panel.style.left = `${clampedLeft}px`;
    panel.style.top = `${clampedTop}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    return { left: clampedLeft, top: clampedTop };
  }

  function makeDraggable(panel, header) {
    let dragOffsetX = 0;
    let dragOffsetY = 0;

    function onMouseMove(event) {
      const { left, top } = applyPosition(
        panel,
        event.clientX - dragOffsetX,
        event.clientY - dragOffsetY
      );
      savePosition(left, top);
    }

    function onMouseUp() {
      document.removeEventListener("mousemove", onMouseMove, true);
      document.removeEventListener("mouseup", onMouseUp, true);
      panel.classList.remove("n8nc-dragging");
    }

    // n8n's own canvas has its own global drag-to-pan handling, almost
    // certainly attached to `document` for capturing mousedown so it can
    // intercept drags anywhere on the page — if it calls stopPropagation()
    // there, a listener on `header` itself (deeper in the tree) would never
    // even see the event. Listening on `document` in the capture phase
    // puts this at the same level, so stopPropagation() elsewhere can't
    // silently swallow it (only stopImmediatePropagation on this exact
    // node could, which is far less commonly used).
    document.addEventListener(
      "mousedown",
      (event) => {
        if (!header.contains(event.target)) return;
        if (event.target.closest(".n8nc-close")) return; // don't drag from the close button
        const rect = panel.getBoundingClientRect();
        dragOffsetX = event.clientX - rect.left;
        dragOffsetY = event.clientY - rect.top;
        panel.classList.add("n8nc-dragging");
        document.addEventListener("mousemove", onMouseMove, true);
        document.addEventListener("mouseup", onMouseUp, true);
        event.preventDefault();
        event.stopPropagation();
      },
      true
    );
  }

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

    const saved = loadSavedPosition();
    if (saved) applyPosition(panelEl, saved.left, saved.top);

    makeDraggable(panelEl, panelEl.querySelector(".n8nc-header"));

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
        const badgeLabel = { stats: "Stats", semantic: "Semantic", both: "Both" }[s.source] || s.source;
        card.innerHTML = `
          <div class="n8nc-card-title">
            <span>${s.display_name}</span>
            <span class="n8nc-badge" title="${s.reason}">${badgeLabel}</span>
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
