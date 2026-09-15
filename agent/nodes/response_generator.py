"""
Response Generator: turns the graph's final state into one
customer-facing sentence or two. LLM call, but a plain text one --
no with_structured_output here, because the output we want (a
natural sentence) isn't structured data, it's prose.

The one thing this node gets careful about: classifying *which
situation* we're in before calling the LLM, so the prompt can be
explicit about tense. Without that, a model can easily write "your
refund has been processed" for a request that's actually still
waiting on the customer's confirmation -- which would be actively
misleading, not just unpolished.
"""
from agent.llm import get_llm
from agent.state import AgentState

SYSTEM_PROMPT = """You are a friendly, concise travel customer service agent.
Write a short reply (2-4 sentences) to the customer based only on the facts given below.
Do not invent details that aren't in the facts. Do not use markdown formatting."""


def _classify_situation(state: AgentState) -> str:
    if state.get("intent") == "out_of_scope" or state.get("policy_ok") is False:
        return "declined"
    if state.get("confirmation_required") and not state.get("confirmed"):
        return "needs_confirmation"
    if state.get("error"):
        return "failed"
    return "completed"


def _build_facts(state: AgentState, situation: str) -> str:
    lines = [f"Customer's message: {state.get('message', '')}", f"Intent: {state.get('intent')}"]

    if situation == "declined":
        lines.append(f"This request cannot proceed. Reason: {state.get('policy_reason') or state.get('error')}")
        lines.append("Politely explain why, and suggest what the customer could do instead if applicable.")

    elif situation == "needs_confirmation":
        lines.append(f"Policy check passed: {state.get('policy_reason') or state.get('policy_applied')}")
        lines.append(
            "This action has NOT happened yet -- you must ask the customer to confirm "
            "before it proceeds. Do not say it is done."
        )

    elif situation == "failed":
        lines.append(f"The action was attempted but failed. Reason: {state.get('error')}")
        lines.append("Apologize briefly and explain what went wrong. Do not say it succeeded.")

    else:  # completed
        tools_called = state.get("tools_called") or []
        wrote_to_db = any(t in tools_called for t in ("book_ticket", "request_refund", "cancel_booking"))
        lines.append(f"Tools called: {tools_called}")
        lines.append(f"Results: {state.get('tool_outputs')}")
        if wrote_to_db:
            lines.append("This has already happened -- confirm what was done, using the real details above.")
        else:
            lines.append(
                "IMPORTANT: this was only a search -- nothing was booked, refunded, or cancelled. "
                "Present these as available options and ask the customer which one they'd like, "
                "or what else they need. Do NOT say anything was booked, confirmed, or reserved."
            )

    return "\n".join(lines)


def generate_response(state: AgentState) -> dict:
    situation = _classify_situation(state)
    facts = _build_facts(state, situation)

    llm = get_llm()
    result = llm.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": facts},
        ]
    )
    return {"final_response": result.content}