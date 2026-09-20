"""
Response Generator: turns the graph's final state into a customer-facing
reply. One LLM call, plain text output (not structured).

Before calling the LLM, the situation is classified in plain Python so
the prompt can be explicit about tense — preventing the model from
writing "your flight has been booked" when the action is still awaiting
confirmation, or "we couldn't process your request" when some intents
succeeded and others didn't.
"""
from agent.llm import get_llm
from agent.state import AgentState

SYSTEM_PROMPT = """You are a friendly, concise travel customer service agent for a
platform operating in Egypt. All monetary values are in EGP -- always state amounts
as "X EGP", never with a dollar sign or other currency symbol.
Write a short reply (2-4 sentences) to the customer based only on the facts given below.
Do not invent details that aren't in the facts. Do not use markdown formatting.
Describe timing naturally (e.g. "more than 2 days before departure") rather than stating raw hour counts.
If the customer describes something incorrectly (e.g. calls a bus a "flight"), use the correct
term from the facts rather than repeating the customer's wording."""


def _classify_situation(state: AgentState) -> str:
    if state.get("policy_ok") is False:
        return "declined"
    if state.get("confirmation_required") and not state.get("confirmed"):
        return "needs_confirmation"
    if state.get("error"):
        return "failed"
    return "completed"


def _build_facts(state: AgentState, situation: str) -> str:
    intents = state.get("intents", [])
    lines = [
        f"Customer's message: {state.get('message', '')}",
        f"Intents: {', '.join(intents) if intents else 'unknown'}",
    ]

    if situation == "declined":
        lines.append(f"This request cannot proceed. Reason: {state.get('policy_reason') or state.get('error')}")
        lines.append("Politely explain why, and suggest what the customer could do instead if applicable.")

    elif situation == "needs_confirmation":
        lines.append(f"Policy check passed: {state.get('policy_applied')}")
        if state.get("policy_reason"):
            lines.append(f"Note on what will happen: {state.get('policy_reason')}")
        lines.append(
            "This action has NOT happened yet — you must ask the customer to confirm "
            "before it proceeds. Do not say it is done."
        )

    elif situation == "failed":
        lines.append(f"The action was attempted but failed. Reason: {state.get('error')}")
        if state.get("tool_outputs"):
            lines.append(f"Partial results (if any): {state.get('tool_outputs')}")
        lines.append("Apologize briefly and explain what went wrong. Do not say it succeeded.")

    else:  # completed
        tools_called = state.get("tools_called") or []
        wrote_to_db = any(t in tools_called for t in ("book_ticket", "request_refund", "cancel_booking"))
        lines.append(f"Tools called: {tools_called}")
        lines.append(f"Results: {state.get('tool_outputs')}")
        # Mention any intents that were blocked (partial failure)
        if state.get("policy_reason"):
            lines.append(f"Note: some parts of the request could not be processed: {state.get('policy_reason')}")
        if wrote_to_db:
            lines.append("This has already happened — confirm what was done, using the real details above.")
        else:
            lines.append(
                "IMPORTANT: this was only a search — nothing was booked, refunded, or cancelled. "
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
