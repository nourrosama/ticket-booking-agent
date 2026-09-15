"""
LangChain @tool wrappers around the existing plain-Python DB
functions in agent/tools/. This is the ReAct-facing adapter layer --
the underlying functions (search_routes, book_ticket, etc.) are
completely untouched and still independently unit-testable with zero
LLM involvement.

Design choice on customer_id: book_ticket needs a customer_id, but we
never want the LLM supplying or guessing one -- a session belongs to
one customer for its whole run (set via --customer-id). Rather than
fight LangGraph's InjectedState machinery for a single hand-invoked
node (it's built for the prebuilt ToolNode, not manual .invoke()
calls), build_tools(customer_id) returns a fresh book_ticket closure
with the id already baked in. The LLM's tool schema for book_ticket
never even shows a customer_id parameter, so it's structurally
impossible for the agent to book under the wrong customer.

The three "sensitive" tools (book_ticket, request_refund,
cancel_booking) are marked SENSITIVE_TOOL_NAMES purely as a lookup
set for agent/react_graph.py to decide when to call interrupt() --
that check happens in the graph, not here. This module only defines
what the tools ARE and how the LLM should reason about calling them.
"""
from typing import Optional

from langchain_core.tools import tool

from agent.tools.book_ticket import book_ticket as _book_ticket
from agent.tools.cancel_booking import cancel_booking as _cancel_booking
from agent.tools.get_booking_status import get_booking_status as _get_booking_status
from agent.tools.request_refund import request_refund as _request_refund
from agent.tools.search_routes import search_routes as _search_routes


# ---------------------------------------------------------------------------
# Safe / read-only tools -- identical across every session, no closure needed
# ---------------------------------------------------------------------------

@tool
def search_routes(
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    transport_type: Optional[str] = None,
    route_code: Optional[str] = None,
) -> dict:
    """Search available travel routes (flights, trains, buses).

    Use this to look up schedules, prices, and seat availability, or to
    find the route the customer wants to book. All arguments are optional
    filters combined with AND -- pass only what the customer actually
    mentioned. transport_type must be one of: flight, train, bus. If this
    returns more than one match, present the options to the customer and
    ask which one they want -- do not pick one for them.
    """
    return _search_routes(
        origin=origin, destination=destination,
        transport_type=transport_type, route_code=route_code,
    )


@tool
def get_booking_status(booking_ref: Optional[str] = None) -> dict:
    """Look up an existing booking by its reference, e.g. 'BK-20250801-005'.

    Returns the booking's status, seat, route, and payment details, plus
    its booking_id. Always call this before request_refund or
    cancel_booking -- both need booking_id, not booking_ref.
    """
    return _get_booking_status(booking_ref=booking_ref)


SAFE_TOOLS = [search_routes, get_booking_status]


# ---------------------------------------------------------------------------
# Sensitive / write tools -- built per-session so customer_id is baked in
# ---------------------------------------------------------------------------

def build_tools(customer_id: int) -> list:
    """Returns the full tool list (safe + sensitive) for one session.

    Called once when the graph is built for a given customer_id. The
    sensitive tools close over customer_id where relevant so the LLM's
    tool schema never exposes it as a settable argument.
    """

    @tool
    def book_ticket(route_id: int, payment_method: str) -> dict:
        """Book a ticket for the current customer on a specific route.

        Requires a route_id (get one from search_routes first -- never
        call this with a route_id you have not verified in this
        conversation) and a payment_method: credit_card, wallet, or cash.
        This writes to the database and cannot be undone by calling it
        again. The customer will always be asked to confirm before this
        actually runs, but you must still summarize exactly what you are
        about to book (route, price, payment method) before calling it,
        so that confirmation makes sense.
        """
        return _book_ticket(
            customer_id=customer_id, route_id=route_id, payment_method=payment_method,
        )

    @tool
    def request_refund(booking_id: int, reason: str = "Customer requested") -> dict:
        """Request a refund for a booking, identified by its booking_id
        (from get_booking_status, not the customer's booking_ref string).

        The refund percentage is calculated automatically from hours
        until departure and loyalty tier -- never state a percentage
        yourself before calling this and seeing the real result. This
        cancels the booking either way, even if the refund is 0%.
        """
        return _request_refund(booking_id=booking_id, reason=reason)

    @tool
    def cancel_booking(booking_id: int) -> dict:
        """Cancel a booking with NO refund, identified by its booking_id
        (from get_booking_status).

        Only use this if the customer explicitly does not want a refund
        check -- if they mention money back at all, use request_refund
        instead, since it also cancels the booking as part of processing.
        """
        return _cancel_booking(booking_id=booking_id)

    sensitive = [book_ticket, request_refund, cancel_booking]
    return SAFE_TOOLS + sensitive


SENSITIVE_TOOL_NAMES = {"book_ticket", "request_refund", "cancel_booking"}