"""
Confirmation: decides whether the current turn is cleared to proceed.

Batch mode: auto-confirms every destructive action (no human present).

Interactive mode: when confirmation is required, calls LangGraph's
interrupt() — this pauses the graph mid-execution, saves state to the
checkpointer, and hands control back to the CLI. The CLI shows the
pending question, then calls graph.invoke(Command(resume=<user reply>))
with the same thread_id. The graph resumes here, interrupt() returns
the reply, and we set confirmed accordingly.

No LLM call in this node.
"""
from langgraph.types import interrupt

from agent.state import AgentState


def confirm(state: AgentState) -> dict:
    if not state.get("confirmation_required"):
        return {"confirmed": True}  # nothing destructive pending

    if state["mode"] == "batch":
        return {"confirmed": True}  # batch always auto-confirms

    # Interactive: pause here — the graph saves state and returns to the CLI.
    # When the user replies, Command(resume=<reply>) restarts from this line.
    human_response = interrupt("Action requires your confirmation. Reply yes to proceed.")
    confirmed = str(human_response).strip().lower() in ("yes", "y", "confirm", "ok", "proceed")
    return {"confirmed": confirmed}
