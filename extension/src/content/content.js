/**
 * Orchestrates polling the workflow state, debouncing, calling the
 * background service worker for suggestions, and rendering them.
 */
(() => {
  const POLL_INTERVAL_MS = 4000;
  let lastNodeSignature = null;
  let lastSuggestedForNodeId = null;

  function nodeSignature(context) {
    return context.nodes.map((n) => n.id).join(",") + "|" + context.last_node_id;
  }

  async function poll() {
    let context;
    try {
      context = await N8nCopilotReader.getCurrentWorkflowContext();
    } catch (err) {
      // Likely not on a workflow page, or the REST path differs for this
      // n8n version/instance — fail quiet rather than spamming the console.
      return;
    }

    if (!context) {
      N8nCopilotOverlay.hide();
      return;
    }

    const signature = nodeSignature(context);
    if (signature === lastNodeSignature) return; // nothing changed
    lastNodeSignature = signature;

    if (context.last_node_id === lastSuggestedForNodeId) return;

    chrome.runtime.sendMessage(
      { type: "SUGGEST", context },
      (response) => {
        if (chrome.runtime.lastError || !response || response.error) {
          return;
        }
        lastSuggestedForNodeId = context.last_node_id;
        N8nCopilotOverlay.render(response.suggestions, (suggestion) => {
          navigator.clipboard?.writeText(suggestion.display_name).catch(() => {});

          chrome.runtime.sendMessage({
            type: "FEEDBACK",
            payload: {
              workflow_name: context.workflow_name,
              from_node_type: context.nodes.find((n) => n.id === context.last_node_id)?.type,
              suggested_node_type: suggestion.node_type,
              accepted: true,
            },
          });
        });
      }
    );
  }

  setInterval(poll, POLL_INTERVAL_MS);
  poll();
})();
