"""
Entity Extractor: pulls the concrete details out of the message that
the tools will need (route info, a booking reference, a reason for
cancelling, etc). Runs after Intent Classifier, same
with_structured_output pattern, just a richer schema.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent.llm import get_llm
from agent.state import AgentState

SYSTEM_PROMPT = """You are an entity extractor for a travel booking customer service agent.
Extract any of the following details mentioned in the customer's message.
Leave a field null if it is not mentioned -- do not guess or invent values.

- origin: departure city
- destination: arrival city
- transport_type: flight, train, or bus, if specified
- route_code: a specific route code like 'EG-201', if mentioned
- booking_ref: a booking reference like 'BK-20250901-001', if mentioned
- payment_method: credit_card, wallet, or cash, if specified
- reason: the customer's stated reason for cancelling/refunding, if any"""


class Entities(BaseModel):
    origin: Optional[str] = Field(default=None)
    destination: Optional[str] = Field(default=None)
    transport_type: Optional[Literal["flight", "train", "bus"]] = Field(default=None)
    route_code: Optional[str] = Field(default=None)
    booking_ref: Optional[str] = Field(default=None)
    payment_method: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)


def extract_entities(state: AgentState) -> dict:
    llm = get_llm().with_structured_output(Entities)
    result: Entities = llm.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state["message"]},
        ]
    )
    # exclude_none: only keep fields the LLM actually found, so
    # downstream nodes can just check `if "booking_ref" in entities`
    # instead of also checking `is not None` everywhere
    return {"entities": result.model_dump(exclude_none=True)}