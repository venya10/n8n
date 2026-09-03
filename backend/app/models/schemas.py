from typing import Optional

from pydantic import BaseModel, Field


class WorkflowNode(BaseModel):
    id: str
    type: str
    name: Optional[str] = None
    parameters: Optional[dict] = None


class WorkflowContext(BaseModel):
    """Minimal slice of the current n8n workflow sent by the extension."""

    nodes: list[WorkflowNode] = Field(default_factory=list)
    last_node_id: Optional[str] = None
    workflow_name: Optional[str] = None


class SuggestRequest(BaseModel):
    context: WorkflowContext
    top_k: int = 5
    use_llm: bool = False


class Suggestion(BaseModel):
    node_type: str
    display_name: str
    description: str
    score: float
    reason: str
    source: str  # "stats" | "semantic" | "both"


class SuggestResponse(BaseModel):
    suggestions: list[Suggestion]
    generated_spec: Optional[str] = None  # the HyDE description, if use_llm was on


class FeedbackRequest(BaseModel):
    workflow_name: Optional[str] = None
    from_node_type: str
    suggested_node_type: str
    accepted: bool
