"""
Confirmation: acts on the mode flag we agreed on at the start --
batch mode auto-confirms, interactive mode does not. No LLM call.

Scope note: this node only decides the *effective* confirmed value
for this pass through the graph -- it doesn't itself pause and wait
for a reply. In interactive mode, if confirmation is still pending,
the graph routes to Response Generator to ask the question and this
turn ends there; actually holding "we're waiting on booking X" and
matching the customer's next "yes" back to it is run_agent.py's job
(the interactive loop), not this node's.
"""
from agent.state import AgentState


def confirm(state: AgentState) -> dict:
    if not state.get("confirmation_required"):
        return {"confirmed": True}  # nothing destructive pending, so nothing to confirm

    if state["mode"] == "batch":
        return {"confirmed": True}

    # interactive: only true if a prior turn already set it (customer said yes)
    return {"confirmed": bool(state.get("confirmed"))}