/**
 * Reads the current n8n workflow state.
 *
 * n8n's frontend state (Pinia store) isn't reliably exposed on `window` in
 * production builds, so instead of poking at Vue internals we hit n8n's own
 * internal REST API — `/rest/workflows/:id` — which the browser already has
 * a session cookie for since we're running on the same origin. This is the
 * most robust option across self-hosted and cloud instances, but the exact
 * path has moved before between n8n versions, so verify it against your
 * instance (open devtools > Network tab while editing a workflow) before
 * relying on it.
 */

const N8nCopilotReader = (() => {
  let lastKnownNodeIds = new Set();

  function getWorkflowIdFromUrl() {
    // n8n URLs look like: https://<host>/workflow/<id>  (or /workflow/new)
    const match = window.location.pathname.match(/\/workflow\/([^/]+)/);
    if (!match || match[1] === "new") return null;
    return match[1];
  }

  async function fetchWorkflow(workflowId) {
    const res = await fetch(`/rest/workflows/${workflowId}`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`n8n REST API returned ${res.status}`);
    }
    const body = await res.json();
    // Self-hosted responses wrap the workflow in `.data`; some versions
    // return it flat. Handle both.
    return body.data ?? body;
  }

  /**
   * Guesses which node the user just added/is focused on: the node present
   * now that wasn't present on the previous poll. Falls back to the last
   * node in the array (n8n appends new nodes to the end) if nothing new is
   * detected, e.g. right after the panel first loads.
   */
  function guessLastNodeId(nodes) {
    const currentIds = new Set(nodes.map((n) => n.id));
    let newNodeId = null;
    for (const id of currentIds) {
      if (!lastKnownNodeIds.has(id)) {
        newNodeId = id;
        break;
      }
    }
    lastKnownNodeIds = currentIds;
    if (newNodeId) return newNodeId;
    return nodes.length ? nodes[nodes.length - 1].id : null;
  }

  async function getCurrentWorkflowContext() {
    const workflowId = getWorkflowIdFromUrl();
    if (!workflowId) return null;

    const workflow = await fetchWorkflow(workflowId);
    const nodes = (workflow.nodes || []).map((n) => ({
      id: n.id,
      type: n.type,
      name: n.name,
      parameters: n.parameters,
    }));

    if (!nodes.length) return null;

    return {
      nodes,
      last_node_id: guessLastNodeId(nodes),
      workflow_name: workflow.name || null,
    };
  }

  return { getCurrentWorkflowContext };
})();
