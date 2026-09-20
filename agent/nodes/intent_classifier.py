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

- book: customer wants to reserve/purchase a new ticket (they are ready to buy, not just browsing)
- inquiry: customer is asking about an existing booking status, or searching available routes/schedules without committing to buy
- refund: customer wants to cancel a booking and/or get money back
- out_of_scope: anything else (hotel recommendations, financial advice, competitor comparisons, medical advice, unrelated topics)

INTENT DECISION RULES — apply in order:
1. Any phrasing that commits to a purchase ("book", "reserve", "I'd like to book", "I want to buy a ticket", "buy me a ticket") → book
2. Asking about an existing booking by reference number → inquiry
3. Asking what routes/schedules/prices exist, without committing to buy → inquiry
4. Cancelling a booking or requesting a refund → refund
5. Anything unrelated to travel bookings → out_of_scope

A single message can trigger more than one intent. Examples:
  "I'd like to book a train from Cairo to Alexandria, paying by credit card" → ["book"]
  "Book me a ticket and also check my booking BK-456" → ["book", "inquiry"]
  "What flights are available from Cairo to Luxor?" → ["inquiry"]
  "What's the status of my booking BK-123 and can I get a refund?" → ["inquiry", "refund"]
  "I want to cancel my booking BK-789" → ["refund"]
  "Can you recommend a hotel in Cairo?" → ["out_of_scope"]

Only include out_of_scope if the ENTIRE message is off-topic (never mix out_of_scope with the others).

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
