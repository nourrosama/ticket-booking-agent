"""
Tool Executor: the only node that actually calls the five DB tools.
No LLM call — this is pure dispatch logic, iterating over the per-intent
policy results and calling the right tool(s) for each intent that passed.
Tools are accumulated across all intents in one pass.

Guard note: this node checks policy_ok/confirmed itself as a defensive
second layer — primary control lives in graph.py's conditional edges,
but a node should never assume it's unreachable just because the graph
usually routes around it.
"""
from agent.route_resolver import resolve_route
from agent.state import AgentState
from agent.tools.book_ticket import book_ticket
from agent.tools.cancel_booking import cancel_booking
from agent.tools.get_booking_status import get_booking_status
from agent.tools.request_refund import request_refund
from agent.tools.search_routes import search_routes


# ---------------------------------------------------------------------------
# Per-intent executors
# ---------------------------------------------------------------------------

def _exec_book(entities: dict, state: AgentState) -> dict:
    resolution = resolve_route(entities)

    if resolution["status"] in ("no_criteria", "not_found"):
        return {"tools_called": [], "tool_inputs": [], "tool_outputs": [], "error": "Not enough information to search or book."}

    if resolution["status"] == "ambiguous":
        output = {"success": True, "count": len(resolution["matches"]), "routes": resolution["matches"]}
        inputs = {k: entities[k] for k in ("origin", "destination", "transport_type") if k in entities}
        return {"tools_called": ["search_routes"], "tool_inputs": [inputs], "tool_outputs": [output], "error": None}

    route = resolution["route"]
    inputs = {
        "customer_id": state["customer_id"],
        "route_id": route["route_id"],
        "payment_method": entities["payment_method"],
    }
    output = book_ticket(**inputs)
    return {
        "tools_called": ["book_ticket"],
        "tool_inputs": [inputs],
        "tool_outputs": [output],
        "error": None if output["success"] else output.get("error"),
    }


def _exec_inquiry(entities: dict, _state: AgentState) -> dict:
    if entities.get("booking_ref"):
        inputs = {"booking_ref": entities["booking_ref"]}
        output = get_booking_status(**inputs)
        return {
            "tools_called": ["get_booking_status"],
            "tool_inputs": [inputs],
            "tool_outputs": [output],
            "error": None if output["success"] else output.get("error"),
        }
    if any(k in entities for k in ("origin", "destination", "route_code")):
        inputs = {k: entities[k] for k in ("origin", "destination", "transport_type", "route_code") if k in entities}
        output = search_routes(**inputs)
        return {"tools_called": ["search_routes"], "tool_inputs": [inputs], "tool_outputs": [output], "error": None}
    return {
        "tools_called": [],
        "tool_inputs": [],
        "tool_outputs": [],
        "error": "Not enough information to look anything up — ask for a booking reference or route details.",
    }


def _exec_refund(entities: dict, _state: AgentState) -> dict:
    booking_ref = entities.get("booking_ref")
    lookup = get_booking_status(booking_ref=booking_ref)
    if not lookup["success"]:
        return {"tools_called": [], "tool_inputs": [], "tool_outputs": [], "error": lookup["error"]}

    inputs = {
        "booking_id": lookup["booking"]["booking_id"],
        "reason": entities.get("reason", "Customer requested"),
    }
    output = request_refund(**inputs)
    return {
        "tools_called": ["get_booking_status", "request_refund"],
        "tool_inputs": [{"booking_ref": booking_ref}, inputs],
        "tool_outputs": [lookup, output],
        "error": None if output["success"] else output.get("error"),
    }


_EXECUTORS = {
    "book": _exec_book,
    "inquiry": _exec_inquiry,
    "refund": _exec_refund,
}


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

def execute_tools(state: AgentState) -> dict:
    if not state.get("policy_ok", False):
        reason = state.get("policy_reason") or "Policy check did not pass."
        return {"tools_called": [], "tool_inputs": [], "tool_outputs": [], "error": reason}

    confirmed = state.get("confirmed", False)
    intent_policies = state.get("intent_policies", [])
    entities = state.get("entities", {})

    all_tools_called: list[str] = []
    all_tool_inputs: list[dict] = []
    all_tool_outputs: list[dict] = []
    first_error = None

    for ip in intent_policies:
        if not ip.get("policy_ok"):
            continue  # this intent was blocked — skip it, reason already in policy_reason

        if ip.get("confirmation_required") and not confirmed:
            continue  # waiting on customer confirmation for this intent

        intent = ip["intent"]
        executor = _EXECUTORS.get(intent)
        if executor is None:
            continue  # out_of_scope — nothing to execute

        result = executor(entities, state)
        all_tools_called.extend(result.get("tools_called", []))
        all_tool_inputs.extend(result.get("tool_inputs", []))
        all_tool_outputs.extend(result.get("tool_outputs", []))

        if result.get("error") and first_error is None:
            first_error = result["error"]
            break  # stop on first error; Error Handler will decide whether to retry

    return {
        "tools_called": all_tools_called,
        "tool_inputs": all_tool_inputs,
        "tool_outputs": all_tool_outputs,
        "error": first_error,
    }
