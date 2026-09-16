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