"""
Smoke test covering every piece built so far: policy math, all 5 DB
tools, all 6 graph nodes, and the compiled graph itself in batch
mode. Run with:

    python tests/smoke_test.py

Resets the DB to a clean seed before and after running, since several
tests write to it. Each check prints PASS/FAIL against an expected
value -- read any FAIL output carefully, it tells you exactly what
was expected vs. what actually came back.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PASS = 0
FAIL = 0


def check(label, actual, expected):
    global PASS, FAIL
    ok = actual == expected
    PASS += ok
    FAIL += not ok
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}")
    if not ok:
        print(f"       expected: {expected!r}")
        print(f"       actual:   {actual!r}")


def check_true(label, condition, detail=""):
    global PASS, FAIL
    PASS += bool(condition)
    FAIL += not bool(condition)
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail and not condition else ""))


def reseed():
    subprocess.run([sys.executable, "data/seed.py"], cwd=Path(__file__).parent.parent,
                    capture_output=True, check=True)


print("=" * 60)
print("SECTION 1: Policy math (no LLM, no DB)")
print("=" * 60)
from agent.policy import calculate_refund

r = calculate_refund("2025-09-15T08:00:00", "gold", 150.0)  # 56h out, gold
check("48hr+gold -> 100% (capped)", r["percentage"], 100)

r = calculate_refund("2025-09-13T20:00:00", "platinum", 1000.0)  # 20h out, platinum
check("12-24hr+platinum -> 60%", r["percentage"], 60)

r = calculate_refund("2025-09-13T06:00:00", "standard", 200.0)  # 6h out, standard
check("under 12hr+standard -> 0%", r["percentage"], 0)

print()
print("=" * 60)
print("SECTION 2: DB tools (writes -- DB reset after)")
print("=" * 60)
reseed()
from agent.tools.search_routes import search_routes
from agent.tools.book_ticket import book_ticket
from agent.tools.get_booking_status import get_booking_status
from agent.tools.request_refund import request_refund
from agent.tools.cancel_booking import cancel_booking

result = search_routes(origin="Cairo", transport_type="flight")
check_true("search_routes finds Cairo flights", result["success"] and result["count"] > 0)

result = book_ticket(customer_id=3, route_id=6, payment_method="credit_card")
check_true("book_ticket succeeds", result["success"])
check_true("book_ticket returns a booking_ref", result.get("booking_ref", "").startswith("BK-"))

result = get_booking_status(booking_ref="BK-20250901-001")
check_true("get_booking_status finds existing booking", result["success"])
check("get_booking_status returns correct customer", result["booking"]["customer_name"], "Ahmed Hassan")

result = get_booking_status(booking_ref="NOT-REAL")
check_true("get_booking_status fails gracefully on bad ref", not result["success"])

result = request_refund(booking_id=1, reason="test")
check_true("request_refund succeeds", result["success"])
check("request_refund on 56h-out gold booking -> 100%", result["percentage"], 100)

result = request_refund(booking_id=1, reason="test again")
check_true("request_refund blocks double-refund", not result["success"])

result = cancel_booking(booking_id=6)
check_true("cancel_booking succeeds", result["success"])

result = cancel_booking(booking_id=6)
check_true("cancel_booking blocks double-cancel", not result["success"])

reseed()

print()
print("=" * 60)
print("SECTION 3: Policy Checker + Error Handler + Confirmation (no LLM)")
print("=" * 60)
from agent.nodes.policy_checker import check_policy
from agent.nodes.error_handler import handle_error
from agent.nodes.confirmation import confirm

result = check_policy({"intent": "refund", "entities": {"booking_ref": "BK-20250901-001"}})
check_true("policy: eligible refund passes", result["policy_ok"])
check("policy: eligible refund requires confirmation", result["confirmation_required"], True)

result = check_policy({"intent": "refund", "entities": {}})
check_true("policy: refund with no booking_ref is rejected", not result["policy_ok"])

result = check_policy({"intent": "book", "entities": {"origin": "Cairo"}})
check_true("policy: deferred booking (no route yet) passes", result["policy_ok"])
check("policy: deferred booking does NOT require confirmation", result["confirmation_required"], False)

result = check_policy({"intent": "out_of_scope", "entities": {}})
check_true("policy: out_of_scope is rejected", not result["policy_ok"])

result = handle_error({"error": "x", "policy_applied": "booking_policy::route_not_found",
                        "entities": {"route_code": "XX"}, "retry_count": 0})
check("error_handler: retryable error sets retrying=True", result["retrying"], True)

result = handle_error({"error": "x", "policy_applied": "refund_policy::missing_booking_ref",
                        "entities": {}, "retry_count": 0})
check("error_handler: non-retryable error sets retrying=False", result["retrying"], False)

result = confirm({"confirmation_required": True, "mode": "batch"})
check("confirm: batch mode auto-confirms", result["confirmed"], True)

result = confirm({"confirmation_required": True, "mode": "interactive"})
check("confirm: interactive mode does not auto-confirm", result["confirmed"], False)

print()
print("=" * 60)
print("SECTION 4: LLM nodes (needs GROQ_API_KEY -- these cost a moment each)")
print("=" * 60)
from agent.nodes.intent_classifier import classify_intent
from agent.nodes.entity_extractor import extract_entities
from agent.nodes.response_generator import generate_response

result = classify_intent({"message": "I want to book a flight from Cairo to Luxor"})
check("intent_classifier: clear booking message", result["intent"], "book")

result = classify_intent({"message": "What's the best stock to invest in?"})
check("intent_classifier: unrelated question -> out_of_scope", result["intent"], "out_of_scope")

result = extract_entities({"message": "I want a flight from Cairo to Luxor"})
check("entity_extractor: extracts origin", result["entities"].get("origin"), "Cairo")
check("entity_extractor: extracts destination", result["entities"].get("destination"), "Luxor")
check("entity_extractor: extracts transport_type", result["entities"].get("transport_type"), "flight")

result = generate_response({
    "message": "refund my booking", "intent": "refund", "policy_ok": False,
    "policy_reason": "That booking is already refunded.",
})
check_true("response_generator: produces non-empty text for a decline",
           len(result["final_response"].strip()) > 0)

print()
print("=" * 60)
print("SECTION 5: Full compiled graph, batch mode (needs GROQ_API_KEY)")
print("=" * 60)
reseed()
from agent.graph import build_graph

g = build_graph()
result = g.invoke({"customer_id": 1, "message": "I'd like to refund booking BK-20250901-001, change of plans", "mode": "batch"})
check("graph: classifies refund intent", result["intent"], "refund")
check_true("graph: auto-confirms in batch mode", result["confirmed"])
check_true("graph: actually calls request_refund", "request_refund" in result.get("tools_called", []))
check_true("graph: produces a final_response", len(result.get("final_response", "").strip()) > 0)
reseed()

print()
print("=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 60)