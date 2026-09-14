"""
Tool Executor: the only node that actually calls the five DB tools.
No LLM call here either -- this is dispatch logic, deciding *which*
tool(s) to call based on intent + entities, then recording what
happened for the Response Generator (and Error Handler, if it fails).

Guard note: this node also re-checks policy_ok/confirmed itself, as
a defensive second layer -- the primary control flow (skip this node
entirely when policy failed or confirmation is still pending) lives
in graph.py's conditional edges, but a node should never assume it's
unreachable just because the graph *usually* routes around it.
"""
from agent.state import AgentState
from agent.tools.book_ticket import book_ticket
from agent.tools.cancel_booking import cancel_booking
from agent.tools.get_booking_status import get_booking_status
from agent.tools.request_refund import request_refund
from agent.tools.search_routes import search_routes


def _no_call(reason: str) -> dict:
    return {"tools_called": [], "tool_inputs": [], "tool_outputs": [], "error": reason}


def execute_tools(state: AgentState) -> dict:
    if not state.get("policy_ok", False):
        return _no_call(state.get("policy_reason") or "Policy check did not pass.")
    if state.get("confirmation_required") and not state.get("confirmed", False):
        return _no_call("Waiting on customer confirmation.")

    intent = state["intent"]
    entities = state.get("entities", {})

    if intent == "book":
        if entities.get("route_code"):
            if not entities.get("payment_method"):
                return _no_call("Missing payment_method -- ask the customer how they'd like to pay.")

            found = search_routes(route_code=entities["route_code"])
            if not found["routes"]:
                return _no_call(f"Route {entities['route_code']} not found.")
            route_id = found["routes"][0]["route_id"]

            inputs = {
                "customer_id": state["customer_id"],
                "route_id": route_id,
                "payment_method": entities["payment_method"],
            }
            output = book_ticket(**inputs)
            return {
                "tools_called": ["book_ticket"],
                "tool_inputs": [inputs],
                "tool_outputs": [output],
                "error": None if output["success"] else output.get("error"),
            }
        else:
            # no specific route chosen yet -- search and let the
            # Response Generator present options instead of booking
            inputs = {k: entities[k] for k in ("origin", "destination", "transport_type") if k in entities}
            output = search_routes(**inputs)
            return {
                "tools_called": ["search_routes"],
                "tool_inputs": [inputs],
                "tool_outputs": [output],
                "error": None,
            }

    if intent == "inquiry":
        if entities.get("booking_ref"):
            inputs = {"booking_ref": entities["booking_ref"]}
            output = get_booking_status(**inputs)
            return {
                "tools_called": ["get_booking_status"],
                "tool_inputs": [inputs],
                "tool_outputs": [output],
                "error": None if output["success"] else output.get("error"),
            }
        elif any(k in entities for k in ("origin", "destination", "route_code")):
            inputs = {k: entities[k] for k in ("origin", "destination", "transport_type", "route_code") if k in entities}
            output = search_routes(**inputs)
            return {
                "tools_called": ["search_routes"],
                "tool_inputs": [inputs],
                "tool_outputs": [output],
                "error": None,
            }
        return _no_call("Not enough information to look anything up -- ask for a booking reference or route details.")

    if intent == "refund":
        booking_ref = entities.get("booking_ref")
        lookup = get_booking_status(booking_ref=booking_ref)
        if not lookup["success"]:
            return _no_call(lookup["error"])

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

    return _no_call("out_of_scope intent -- no tool call needed.")