from typing import Literal, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # input
    customer_id: int
    message: str
    mode: Literal["batch", "interactive"]

    # Intent Classifier output — a list so one message can carry multiple intents
    intents: list[str]  # e.g. ["book"] or ["inquiry", "refund"]

    # Entity Extractor output
    entities: dict

    # Policy Checker output
    intent_policies: list[dict]   # one entry per intent: {intent, policy_ok, policy_applied, policy_reason, confirmation_required}
    policy_applied: str            # combined string ("; "-joined) for error handler / output contract
    policy_ok: bool                # True if at least one intent can proceed
    policy_reason: Optional[str]  # combined failure reasons (None when all pass)

    # Confirmation node
    confirmation_required: bool   # True if any proceeding intent requires it
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
