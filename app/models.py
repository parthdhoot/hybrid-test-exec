from typing import Literal

from pydantic import BaseModel

ActionType = Literal["goto", "click", "fill", "assert_text", "done"]


class AgentAction(BaseModel):
    """The single shared decision shape produced by the LLM, both during
    capture-time exploration and runtime recovery."""

    action: ActionType
    selector: str | None = None
    value: str | None = None
    expected_text: str | None = None
    reasoning: str


class CreateTestRequest(BaseModel):
    intent: str
    name: str | None = None


class RunTestRequest(BaseModel):
    test_id: str


class PromotionDecisionRequest(BaseModel):
    pass  # candidate id comes from the URL path
