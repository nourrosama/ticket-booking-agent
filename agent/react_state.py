"""
State for the true-ReAct agent.

This replaces agent/state.py's AgentState for the new graph. The old
AgentState had one field per pipeline stage (intent, entities,
policy_ok, ...) because each stage was a separate deterministic node.
A ReAct agent doesn't have those stages -- there's just a running
conversation the LLM reasons over, so the state collapses to a single
message list plus the two pieces of session context that never
change mid-conversation.

`messages` uses LangGraph's `add_messages` reducer, which means nodes
don't need to manually append to a list -- returning {"messages": [x]}
merges x onto the end of the existing list automatically.
"""
from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ReactState(TypedDict):
    messages: Annotated[list, add_messages]
    customer_id: int
    mode: Literal["batch", "interactive"]