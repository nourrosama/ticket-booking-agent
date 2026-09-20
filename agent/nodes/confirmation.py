"""
Confirmation: decides whether the current turn is cleared to proceed.

Batch mode: auto-confirms every destructive action (no human present).

Interactive mode: when confirmation is required, calls LangGraph's
interrupt() — this pauses the graph mid-execution, saves state to the
checkpointer, and hands control back to the CLI. The CLI reads the
interrupt value (a human-readable prompt) and displays it as the
agent's message. When the user replies, Command(resume=<reply>) restarts
execution here; interrupt() returns the reply and we set confirmed.

No LLM call in this node.
"""
from langgraph.types import interrupt

from agent.state import AgentState


def confirm(state: AgentState) -> dict:
    if not state.get("confirmation_required"):
        return {"confirmed": True}  # nothing destructive pending

    if state["mode"] == "batch":
        return {"confirmed": True}  # batch always auto-confirms

    # Build a clear, informative prompt from what we already know
    intents = state.get("intents", [])
    policy_reason = state.get("policy_reason")

    action_parts = []
    if "book" in intents:
        action_parts.append("book a ticket")
    if "refund" in intents:
        action_parts.append("process a refund/cancellation")
    action = " and ".join(action_parts) if action_parts else "proceed with this action"

    prompt = f"I'm about to {action}."
    if policy_reason:
        prompt += f" {policy_reason}"
    prompt += " Reply yes to confirm or no to cancel."

    # Pause here — the CLI will display `prompt` and wait for input.
    # Command(resume=<user reply>) restarts from this line.
    human_response = interrupt(prompt)
    confirmed = str(human_response).strip().lower() in ("yes", "y", "confirm", "ok", "proceed")
    return {"confirmed": confirmed}
