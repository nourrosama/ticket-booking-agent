from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ReactState(TypedDict):
    messages: Annotated[list, add_messages]
    customer_id: int
    mode: Literal["batch", "interactive"]