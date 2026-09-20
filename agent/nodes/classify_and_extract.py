"""
Classify and Extract: the first node every message hits.
Does in one LLM call what the old pipeline did in two:
  1. Labels the message with one or more intents
  2. Pulls out the concrete entities the tools will need

Combining them saves one round-trip to the LLM and keeps the prompt
context identical for both tasks — the same message is read once.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent.llm import get_llm
from agent.state import AgentState

SYSTEM_PROMPT = """You are the first step of a travel booking customer service agent.
Given a customer message, do TWO things in one response:

1. CLASSIFY INTENT — assign one or more intents:
   - book: customer wants to reserve/purchase a new ticket (ready to buy, not just browsing)
   - inquiry: customer is asking about an existing booking, or searching routes/schedules without committing to buy
   - refund: customer wants to cancel a booking and/or get money back
   - out_of_scope: anything unrelated to travel bookings (hotels, financial advice, competitor questions, etc.)

   INTENT DECISION RULES (apply in order):
   1. Any commit-to-purchase phrasing ("book", "reserve", "I'd like to book", "buy me a ticket") → book
   2. Asking about an existing booking by reference number → inquiry
   3. Asking what routes/schedules/prices exist, without committing → inquiry
   4. Cancelling or requesting a refund → refund
   5. Anything else → out_of_scope
   Only include out_of_scope if the ENTIRE message is off-topic (never mix it with the others).

2. EXTRACT ENTITIES — pull out only what is explicitly stated. Leave a field null if not mentioned.
   - origin: departure city
   - destination: arrival city
   - transport_type: flight, train, or bus — only if specified
   - route_code: a specific route code like 'EG-201' — only if mentioned
   - booking_ref: a booking reference like 'BK-20250901-001' — only if mentioned
   - payment_method: credit_card, wallet, or cash — only if specified
   - reason: the customer's stated reason for cancelling/refunding, if any

Examples:
  "I'd like to book a train from Cairo to Alexandria, paying by credit card"
    → intents: ["book"], origin: "Cairo", destination: "Alexandria", transport_type: "train", payment_method: "credit_card"
  "What's the status of BK-20250901-003 and can I get a refund?"
    → intents: ["inquiry", "refund"], booking_ref: "BK-20250901-003"
  "What flights are available from Cairo to Luxor?"
    → intents: ["inquiry"], origin: "Cairo", destination: "Luxor", transport_type: "flight"

Respond with the list of intents, a confidence score (0–1), and the extracted entities."""


class ClassifyAndExtractResult(BaseModel):
    intents: list[Literal["book", "inquiry", "refund", "out_of_scope"]] = Field(
        description="All intents found in the message"
    )
    confidence: float = Field(description="Overall confidence score between 0 and 1")
    origin: Optional[str] = Field(default=None)
    destination: Optional[str] = Field(default=None)
    transport_type: Optional[Literal["flight", "train", "bus"]] = Field(default=None)
    route_code: Optional[str] = Field(default=None)
    booking_ref: Optional[str] = Field(default=None)
    payment_method: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)


def classify_and_extract(state: AgentState) -> dict:
    llm = get_llm().with_structured_output(ClassifyAndExtractResult)
    result: ClassifyAndExtractResult = llm.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state["message"]},
        ]
    )

    # Deduplicate intents while preserving order
    seen: set[str] = set()
    unique_intents = []
    for i in result.intents:
        if i not in seen:
            seen.add(i)
            unique_intents.append(i)

    # Only keep entity fields the LLM actually found (exclude nulls)
    entity_fields = ("origin", "destination", "transport_type", "route_code",
                     "booking_ref", "payment_method", "reason")
    entities = {k: getattr(result, k) for k in entity_fields if getattr(result, k) is not None}

    return {
        "intents": unique_intents,
        "confidence": result.confidence,
        "entities": entities,
    }
