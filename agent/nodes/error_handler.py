"""
Error Handler: runs when state["error"] is set. Deterministic
control-flow only, no LLM call — decides retry vs. give up, and if
retrying, adjusts the inputs for the next attempt.

Only one class of error is retryable: a booking that named a route_code
that doesn't exist. The fix is to drop the bad code so the next pass
falls back to a plain origin/destination search instead of repeating
the same failing call. Every other error is terminal within this turn.

Works with both single and multi-intent: policy_applied may be a
"; "-joined string when multiple intents ran, so we split and check
each component.
"""
from agent.config import MAX_RETRIES
from agent.state import AgentState

RETRYABLE_POLICIES = {"booking_policy::route_not_found"}


def handle_error(state: AgentState) -> dict:
    retry_count = state.get("retry_count", 0) + 1

    # policy_applied may be a combined "; "-joined string for multi-intent turns
    policy_applied_raw = state.get("policy_applied") or ""
    applied_set = {p.strip() for p in policy_applied_raw.split(";") if p.strip()}
    is_retryable = bool(applied_set & RETRYABLE_POLICIES)
    can_retry = is_retryable and retry_count <= MAX_RETRIES

    if can_retry:
        entities = dict(state.get("entities", {}))
        entities.pop("route_code", None)  # drop the bad code, fall back to search
        return {
            "retry_count": retry_count,
            "entities": entities,
            "retrying": True,
            # clear prior verdicts so Policy Checker / Tool Executor re-evaluate cleanly
            "error": None,
            "policy_ok": None,
            "policy_applied": None,
            "policy_reason": None,
            "intent_policies": [],
        }

    return {
        "retry_count": retry_count,
        "retrying": False,
        # error/policy_reason left as-is so Response Generator can explain to the customer
    }
