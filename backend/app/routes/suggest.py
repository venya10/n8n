from fastapi import APIRouter, HTTPException

from app.models.schemas import FeedbackRequest, SuggestRequest, SuggestResponse
from app.services import llm, rerank, retrieval, stats

router = APIRouter()


@router.post("/suggest", response_model=SuggestResponse)
async def suggest(req: SuggestRequest) -> SuggestResponse:
    ctx = req.context
    if not ctx.nodes:
        raise HTTPException(400, "context.nodes must contain at least one node")

    last_node = next(
        (n for n in ctx.nodes if n.id == ctx.last_node_id), ctx.nodes[-1]
    )
    last_meta = retrieval.NODE_BY_TYPE.get(last_node.type)
    last_node_name = last_meta["display_name"] if last_meta else last_node.type

    already_present = {n.type for n in ctx.nodes}

    stats_candidates = [
        c for c in stats.get_common_next_nodes(last_node.type, limit=req.top_k)
        if c["to"] not in already_present
    ]

    generated_spec = None
    if req.use_llm:
        common_next_names = [
            retrieval.NODE_BY_TYPE[c["to"]]["display_name"]
            for c in stats_candidates
            if c["to"] in retrieval.NODE_BY_TYPE
        ]
        # A snapshot of the rest of the workflow, not just the last node —
        # gives the LLM more than "you're on a Webhook" to reason about.
        other_node_names = list(
            dict.fromkeys(
                retrieval.NODE_BY_TYPE[n.type]["display_name"]
                if n.type in retrieval.NODE_BY_TYPE
                else n.type
                for n in ctx.nodes
                if n.id != last_node.id
            )
        )
        generated_spec = await llm.generate_next_node_spec(
            last_node_name, ctx.workflow_name, common_next_names, other_node_names
        )
        query = generated_spec
    else:
        query = f"a node that follows {last_node_name} in an n8n workflow"

    semantic_candidates = retrieval.semantic_search(
        query, top_k=req.top_k, exclude=already_present
    )

    suggestions = rerank.merge_and_rank(stats_candidates, semantic_candidates, req.top_k)

    return SuggestResponse(suggestions=suggestions, generated_spec=generated_spec)


@router.post("/feedback")
async def feedback(req: FeedbackRequest) -> dict:
    stats.record_feedback(req.from_node_type, req.suggested_node_type, req.accepted)
    return {"ok": True}
