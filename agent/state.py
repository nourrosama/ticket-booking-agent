from typing import Literal, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # input
    customer_id: int
    message: str
    mode: Literal["batch", "interactive"]

    # Intent Classifier output
    intent: Literal["book", "inquiry", "refund", "out_of_scope"]

    # Entity Extractor output
    entities: dict

    # Policy Checker output
    policy_applied: str
    policy_ok: bool
    policy_reason: Optional[str]

    # Confirmation node
    confirmation_required: bool
    confirmed: bool

    # Tool Executor output
    tools_called: list[str]
    tool_inputs: list[dict]
    tool_outputs: list[dict]

    # Error Handler / repair loop
    retry_count: int
    error: Optional[str]
    retrying: bool

    # Response Generator output
    final_response: str
    confidence: float