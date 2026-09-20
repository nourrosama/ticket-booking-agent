"""
Intent Classifier: the first node every message hits. Labels the
message with one or more intents so the graph knows what to do.

A single message can carry multiple intents — e.g. "check my booking
BK-123 AND cancel it" → ["inquiry", "refund"]. All matching intents
are returned; out_of_scope is only included when the ENTIRE message
is off-topic.
"""
from typing import Literal

from pydantic import BaseModel, Field

from agent.llm import get_llm
from agent.state import AgentState

SYSTEM_PROMPT = """You are the intent classifier for a travel booking customer service agent.
Classify the customer's message into one or more of these intents:

- book: customer wants to search for or book a new ticket
- inquiry: customer is asking about an existing booking, schedule, price, or availability
- refund: customer wants to cancel a booking and/or get money back
- out_of_scope: anything else (financial advice, competitor comparisons, medical travel advice, unrelated topics)

A message can contain more than one intent. Examples:
  "What's the status of BK-123 and can I get a refund?" → ["inquiry", "refund"]
  "Book me a flight to Luxor and also check my booking BK-456" → ["book", "inquiry"]
  "I want to cancel my booking BK-789" → ["refund"]

Return ALL intents that apply. Only include out_of_scope if the entire message is off-topic
(never mix out_of_scope with the others).

If the message is only asking what's available/scheduled without wanting to reserve,
classify as inquiry, not book — book is for when the customer clearly wants to make a reservation.

Respond with the list of intents and an overall confidence score from 0 to 1."""


class IntentResult(BaseModel):
    intents: list[Literal["book", "inquiry", "refund", "out_of_scope"]] = Field(
        description="All intents found in the message"
    )
    confidence: float = Field(description="Overall confidence score between 0 and 1")


def classify_intent(state: AgentState) -> dict:
    llm = get_llm().with_structured_output(IntentResult)
    result: IntentResult = llm.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state["message"]},
        ]
    )
    # Deduplicate while preserving order
    seen = set()
    unique_intents = []
    for i in result.intents:
        if i not in seen:
            seen.add(i)
            unique_intents.append(i)
    return {"intents": unique_intents, "confidence": result.confidence}
