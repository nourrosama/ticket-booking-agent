"""
Wires all 6 nodes into the graph with LangGraph. This file only
does routing — all logic lives in the node functions it imports.

Flow:
  classify_and_extract -> check_policy -> confirm
    -> [route_after_confirmation] -> execute_tools OR generate_response
  execute_tools -> [route_after_tools] -> handle_error OR generate_response
  handle_error -> [route_after_error] -> check_policy (retry loop) OR generate_response
  generate_response -> END

Checkpointer note: pass a MemorySaver (or other checkpointer) to
build_graph() for interactive mode — required for interrupt/resume.
Batch mode passes None (auto-confirms, never interrupts).
"""
from langgraph.graph import END, StateGraph

from agent.nodes.classify_and_extract import classify_and_extract
from agent.nodes.confirmation import confirm
from agent.nodes.error_handler import handle_error
from agent.nodes.policy_checker import check_policy
from agent.nodes.response_generator import generate_response
from agent.nodes.tool_executor import execute_tools
from agent.state import AgentState


def route_after_confirmation(state: AgentState) -> str:
    if not state.get("policy_ok", False):
        return "generate_response"
    if state.get("confirmation_required") and not state.get("confirmed"):
        return "generate_response"
    return "execute_tools"


def route_after_tools(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "generate_response"


def route_after_error(state: AgentState) -> str:
    return "check_policy" if state.get("retrying") else "generate_response"


def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)

    graph.add_node("classify_and_extract", classify_and_extract)
    graph.add_node("check_policy", check_policy)
    graph.add_node("confirm", confirm)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("handle_error", handle_error)
    graph.add_node("generate_response", generate_response)

    graph.set_entry_point("classify_and_extract")
    graph.add_edge("classify_and_extract", "check_policy")
    graph.add_edge("check_policy", "confirm")

    graph.add_conditional_edges(
        "confirm",
        route_after_confirmation,
        {"execute_tools": "execute_tools", "generate_response": "generate_response"},
    )
    graph.add_conditional_edges(
        "execute_tools",
        route_after_tools,
        {"handle_error": "handle_error", "generate_response": "generate_response"},
    )
    graph.add_conditional_edges(
        "handle_error",
        route_after_error,
        {"check_policy": "check_policy", "generate_response": "generate_response"},
    )

    graph.add_edge("generate_response", END)

    return graph.compile(checkpointer=checkpointer)
