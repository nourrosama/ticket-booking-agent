"""
Policy Checker: deterministic business-rule enforcement — no LLM call.
Runs after Entity Extractor and checks every intent in the message,
collecting a per-intent result. The combined output tells the graph
whether execution can proceed and whether confirmation is needed.

For 'book', a full seat/payment check only happens when a specific route
can be resolved; otherwise the booking falls through to book_ticket's own
internal guard, which is the hard backstop either way.
"""
from agent.db import get_connection
from agent.policy import calculate_refund
from agent.route_resolver import resolve_route
from agent.state import AgentState


# ---------------------------------------------------------------------------
# Per-intent checkers
# ---------------------------------------------------------------------------

def _check_book(entities: dict) -> dict:
    resolution = resolve_route(entities)

    if resolution["status"] == "no_criteria":
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
        return {
            "policy_ok": True,
            "policy_applied": "booking_policy::multiple_matches",
            "policy_reason": None,
            "confirmation_required": False,
        }

    # Resolved to exactly one route
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


def _check_inquiry(_entities: dict) -> dict:
    return {
        "policy_ok": True,
        "policy_applied": "inquiry_policy::no_restrictions",
        "policy_reason": None,
        "confirmation_required": False,
    }


def _check_refund(entities: dict) -> dict:
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


def _check_out_of_scope(_entities: dict) -> dict:
    return {
        "policy_ok": False,
        "policy_applied": "scope_policy::out_of_scope",
        "policy_reason": (
            "This request is outside what I can help with (e.g. financial "
            "advice, competitor comparisons, or medical travel advice)."
        ),
        "confirmation_required": False,
    }


_CHECKERS = {
    "book": _check_book,
    "inquiry": _check_inquiry,
    "refund": _check_refund,
    "out_of_scope": _check_out_of_scope,
}


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

def check_policy(state: AgentState) -> dict:
    intents = state.get("intents", [])
    entities = state.get("entities", {})

    if not intents:
        return {
            "intent_policies": [],
            "policy_ok": False,
            "policy_applied": "unknown_intent",
            "policy_reason": "Could not determine how to handle this request.",
            "confirmation_required": False,
        }

    # Run the appropriate checker for each intent
    results = []
    for intent in intents:
        checker = _CHECKERS.get(intent, _check_out_of_scope)
        result = checker(entities)
        results.append({"intent": intent, **result})

    # Combine: overall policy_ok = True if at least one intent can proceed
    any_ok = any(r["policy_ok"] for r in results)
    any_confirm = any(r["confirmation_required"] for r in results if r["policy_ok"])
    failed_reasons = [r["policy_reason"] for r in results if not r["policy_ok"] and r["policy_reason"]]
    combined_policies = "; ".join(r["policy_applied"] for r in results)

    return {
        "intent_policies": results,
        "policy_ok": any_ok,
        "policy_applied": combined_policies,
        "policy_reason": "; ".join(failed_reasons) if failed_reasons else None,
        "confirmation_required": any_confirm and any_ok,
    }
