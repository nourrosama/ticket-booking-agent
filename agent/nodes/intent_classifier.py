"""
Intent Classifier: the first node every message hits. Labels the
message as one of the four intents so the graph knows which branch
to route down next.
"""
from typing import Literal

from pydantic import BaseModel, Field

from agent.llm import get_llm
from agent.state import AgentState

SYSTEM_PROMPT = """You are the intent classifier for a travel booking customer service agent.
Classify the customer's message into exactly one of these intents:

- book: customer wants to search for or book a new ticket
- inquiry: customer is asking about an existing booking, schedule, price, or availability
- refund: customer wants to cancel a booking and/or get money back
- out_of_scope: anything else (financial advice, competitor comparisons, medical travel advice, unrelated topics)

If the message is only asking what's available/scheduled ("what flights are there", "when does the train leave")
without actually saying they want to book/reserve it, classify as inquiry, not book -- book is for when the
customer clearly wants to make a reservation.

Respond with the intent and a confidence score from 0 to 1."""


class IntentResult(BaseModel):
    intent: Literal["book", "inquiry", "refund", "out_of_scope"] = Field(
        description="The classified intent"
    )
    confidence: float = Field(description="Confidence score between 0 and 1")


def classify_intent(state: AgentState) -> dict:
    llm = get_llm().with_structured_output(IntentResult)
    result: IntentResult = llm.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state["message"]},
        ]
    )
    return {"intent": result.intent, "confidence": result.confidence}