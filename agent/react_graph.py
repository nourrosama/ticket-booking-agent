"""
True ReAct graph: a single LLM node bound to all five tools decides
for itself which tool to call and when, observes the result, and
loops until it has nothing more to do. This replaces the old fixed
7-node pipeline (agent/graph.py + agent/nodes/*) with a 2-node loop:

    agent --(tool call?)--> tools --> agent --(tool call?)--> ...
      |
      +--(no tool call)--> END

Nothing about the old pipeline files is deleted -- they still work,
are still what the smoke test exercises for deterministic policy
math, and are kept as a reference for how the same business rules
read as explicit code vs. as prompt instructions.

Confirmation is enforced STRUCTURALLY here, not just by the prompt:
the "tools" node calls interrupt() before running book_ticket,
request_refund, or cancel_booking, but only when mode == "interactive".
interrupt() pauses the entire graph mid-node and hands control back
to whoever called .invoke() -- it is not the LLM being asked nicely,
it is the graph physically stopping. Resuming happens by calling
.invoke(Command(resume=answer), config) with the same thread_id.

In batch mode this interrupt is skipped entirely -- tools execute
immediately, same as the old Confirmation node auto-confirming for
eval runs.

A checkpointer (MemorySaver) is required for interrupt() to work --
LangGraph needs somewhere to persist the paused state between the
interrupt and the resume call. MemorySaver keeps this in-process,
which is fine for a single CLI session; a real deployment would swap
in a persistent checkpointer (e.g. Postgres) without touching this
file.
"""
import json

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from agent.llm import get_llm
from agent.react_prompt import SYSTEM_PROMPT
from agent.react_state import ReactState
from agent.react_tools import SENSITIVE_TOOL_NAMES, build_tools


def _make_agent_node(tools: list):
    llm_with_tools = get_llm().bind_tools(tools)

    def agent_node(state: ReactState) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    return agent_node


def _make_tools_node(tools: list):
    tools_by_name = {t.name: t for t in tools}

    def tools_node(state: ReactState) -> dict:
        last = state["messages"][-1]
        outgoing = []

        for call in last.tool_calls:
            name, args, call_id = call["name"], dict(call["args"]), call["id"]
            tool_fn = tools_by_name[name]

            if name in SENSITIVE_TOOL_NAMES and state.get("mode") == "interactive":
                answer = interrupt({
                    "tool": name,
                    "args": args,
                    "question": f"Confirm: {name}({args})? Reply yes to proceed.",
                })
                if str(answer).strip().lower() not in ("yes", "y", "confirm", "ok", "proceed"):
                    outgoing.append(ToolMessage(
                        content=json.dumps({
                            "success": False,
                            "error": "Cancelled by customer -- action was NOT executed.",
                        }),
                        tool_call_id=call_id,
                    ))
                    continue

            result = tool_fn.invoke(args)
            outgoing.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=call_id))

        return {"messages": outgoing}

    return tools_node


def _route_after_agent(state: ReactState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def build_react_graph(customer_id: int):
    """Builds and compiles a fresh graph for one customer's session.

    Tools are rebuilt per call (via build_tools) so book_ticket's
    closure always has the right customer_id baked in -- see
    react_tools.py for why this beats passing customer_id as an
    LLM-visible argument.
    """
    tools = build_tools(customer_id)

    graph = StateGraph(ReactState)
    graph.add_node("agent", _make_agent_node(tools))
    graph.add_node("tools", _make_tools_node(tools))

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _route_after_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=MemorySaver())