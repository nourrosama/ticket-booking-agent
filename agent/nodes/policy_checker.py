"""
Policy Checker: no LLM call here at all -- this is deterministic
business-rule enforcement, same reasoning as calculate_refund()
being plain Python. It runs after Entity Extractor and decides
whether the request is allowed to proceed, and sets whether
confirmation is required before anything gets written to the DB.

Scope note: for 'book', a full check only happens when a specific
route_code was extracted (checks seat availability up front, so the
customer gets a clear policy-level reason if it's sold out). If the
customer hasn't specified a route yet, this node passes through --
book_ticket's own internal seat check (see tools/book_ticket.py)
is still the final safety net either way.
"""
from agent.db import get_connection
from agent.policy import calculate_refund
from agent.route_resolver import resolve_route
from agent.state import AgentState


def check_policy(state: AgentState) -> dict:
    intent = state["intent"]
    entities = state.get("entities", {})

    if intent == "out_of_scope":
        return {
            "policy_ok": False,
            "policy_applied": "scope_policy::out_of_scope",
            "policy_reason": (
                "This request is outside what I can help with (e.g. financial "
                "advice, competitor comparisons, or medical travel advice)."
            ),
            "confirmation_required": False,
        }

    if intent == "inquiry":
        return {
            "policy_ok": True,
            "policy_applied": "inquiry_policy::no_restrictions",
            "policy_reason": None,
            "confirmation_required": False,
        }

    if intent == "book":
        resolution = resolve_route(entities)

        if resolution["status"] == "no_criteria":
            # nothing to search on yet -- ask for more details, no DB hit needed
            return {
                "policy_ok": True,
                "policy_applied": "booking_policy::deferred_no_criteria",
                "policy_reason": None,
                "confirmation_required": False,
            }

        if resolution["status"] == "not_found":
            return {
                "policy_ok": False,
                "policy_applied": "booking_policy::route_not_found",
                "policy_reason": "No route found matching those details.",
                "confirmation_required": False,
            }

        if resolution["status"] == "ambiguous":
            # multiple matches -- presenting options isn't destructive, no confirmation needed
            return {
                "policy_ok": True,
                "policy_applied": "booking_policy::multiple_matches",
                "policy_reason": None,
                "confirmation_required": False,
            }

        # resolved to exactly one route
        route = resolution["route"]
        if not entities.get("payment_method"):
            return {
                "policy_ok": False,
                "policy_applied": "booking_policy::missing_payment_method",
                "policy_reason": "I need to know how you'd like to pay before booking.",
                "confirmation_required": False,
            }
        if route["available_seats"] <= 0:
            return {
                "policy_ok": False,
                "policy_applied": "booking_policy::no_overbooking",
                "policy_reason": f"Route {route['route_code']} has no seats available.",
                "confirmation_required": False,
            }
        return {
            "policy_ok": True,
            "policy_applied": "booking_policy::no_overbooking",
            "policy_reason": None,
            "confirmation_required": True,
        }

    if intent == "refund":
        booking_ref = entities.get("booking_ref")
        if not booking_ref:
            return {
                "policy_ok": False,
                "policy_applied": "refund_policy::missing_booking_ref",
                "policy_reason": "I need a booking reference to check refund eligibility.",
                "confirmation_required": False,
            }

        conn = get_connection()
        row = conn.execute(
            """SELECT b.status, b.payment_amount, c.loyalty_tier, r.departure_time
               FROM bookings b
               JOIN customers c ON b.customer_id = c.customer_id
               JOIN routes r ON b.route_id = r.route_id
               WHERE b.booking_ref = ?""",
            (booking_ref,),
        ).fetchone()
        conn.close()

        if row is None:
            return {
                "policy_ok": False,
                "policy_applied": "refund_policy::booking_not_found",
                "policy_reason": f"No booking found matching '{booking_ref}'.",
                "confirmation_required": False,
            }
        if row["status"] in ("cancelled", "refunded"):
            return {
                "policy_ok": False,
                "policy_applied": "refund_policy::already_finalized",
                "policy_reason": f"That booking is already {row['status']}.",
                "confirmation_required": False,
            }

        refund = calculate_refund(
            departure_time=row["departure_time"],
            loyalty_tier=row["loyalty_tier"],
            payment_amount=row["payment_amount"],
        )
        return {
            "policy_ok": True,
            "policy_applied": refund["policy_applied"],
            "policy_reason": refund["reason"],
            "confirmation_required": True,
        }

    # should be unreachable given the Literal type on state["intent"]
    return {
        "policy_ok": False,
        "policy_applied": "unknown_intent",
        "policy_reason": "Could not determine how to handle this request.",
        "confirmation_required": False,
    }