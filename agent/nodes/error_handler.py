"""
Error Handler: runs when state["error"] is set. Deterministic
control-flow only, no LLM call -- it decides retry vs. give up, and
if retrying, adjusts the inputs that will be tried again. Crafting
the actual customer-facing explanation is left to Response
Generator, which reads policy_reason/error either way.

Scope note: only one class of error is actually retryable in this
design -- a booking that named a route_code that doesn't exist. In
that case the "adjusted parameter" is dropping the bad route_code so
the next pass falls back to a plain search (see tool_executor.py's
book branch) and offers alternatives instead of repeating the exact
same failing call. Every other error (missing info, already
refunded, out of scope, not found) is not fixable by retrying with
the same input, so those go straight to Response Generator even if
under the retry cap -- retrying them would just burn attempts
without changing the outcome.
"""
from agent.config import MAX_RETRIES
from agent.state import AgentState

RETRYABLE_POLICIES = {"booking_policy::route_not_found"}


def handle_error(state: AgentState) -> dict:
    retry_count = state.get("retry_count", 0) + 1

    is_retryable = state.get("policy_applied") in RETRYABLE_POLICIES
    can_retry = is_retryable and retry_count <= MAX_RETRIES

    if can_retry:
        entities = dict(state.get("entities", {}))
        entities.pop("route_code", None)  # drop the bad code, fall back to search
        return {
            "retry_count": retry_count,
            "entities": entities,
            # clear the prior verdict so Policy Checker/Tool Executor
            # re-evaluate cleanly on the next pass through the graph
            "error": None,
            "policy_ok": None,
            "policy_applied": None,
            "policy_reason": None,
        }

    return {
        "retry_count": retry_count,
        # error/policy_reason are left as-is here (not cleared) so
        # Response Generator has the real reason to explain to the customer
    }