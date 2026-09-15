"""
CLI entrypoint for the ticket-booking agent -- now driving the true
ReAct graph (agent/react_graph.py) instead of the old fixed 7-node
pipeline. The old pipeline (agent/graph.py + agent/nodes/*) is left
in place and still passes its own smoke test; this file no longer
uses it.

Batch mode (eval):
    python run_agent.py --batch sample_questions_eval.jsonl --out outputs.jsonl

Interactive mode (chat):
    python run_agent.py --interactive --customer-id 3

Output contract note: unlike the old pipeline, there's no explicit
Intent Classifier or Policy Checker node here -- the LLM decides
everything by itself. "intent" and "policy_applied" in outputs.jsonl
are therefore RECONSTRUCTED after the fact from which tools got
called and what they returned, not directly reported by a node.
"confidence" has no ReAct equivalent (there's no structured
classification step producing one) and is always null. This is a
real, honest limitation of the ReAct approach vs. the old pipeline --
see README.md.
"""
import json
import sys
import time
import uuid
from pathlib import Path

import click
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from agent.react_graph import build_react_graph
from agent.react_tools import SENSITIVE_TOOL_NAMES

console = Console()

# Maps which sensitive/write tool got called to the old pipeline's
# intent vocabulary, purely for output-contract compatibility with
# the eval file's expected_intent field.
TOOL_TO_INTENT = {
    "book_ticket": "book",
    "request_refund": "refund",
    "cancel_booking": "refund",
    "search_routes": "inquiry",
    "get_booking_status": "inquiry",
}
# Priority order: a write tool tells you the real intent even if a
# read tool was also called earlier in the same turn (e.g. refund
# always calls get_booking_status first).
INTENT_PRIORITY = ["book_ticket", "request_refund", "cancel_booking",
                    "search_routes", "get_booking_status"]


# ---------------------------------------------------------------------------
# Resilient graph invocation -- retries transient API/network failures
# ---------------------------------------------------------------------------

def invoke_with_retry(graph, *args, max_attempts: int = 3, delay_seconds: float = 1.5, **kwargs) -> dict:
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return graph.invoke(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                console.print(f"[dim]  (connection hiccup, retrying {attempt}/{max_attempts - 1}...)[/dim]")
                time.sleep(delay_seconds)
    raise last_exc


# ---------------------------------------------------------------------------
# Parse a finished graph result into the output contract
# ---------------------------------------------------------------------------

def build_output(eval_id: str, result: dict) -> dict:
    messages = result.get("messages", [])

    tools_called, tool_inputs, tool_outputs = [], [], []
    tool_outputs_by_id = {
        m.tool_call_id: _safe_json_loads(m.content)
        for m in messages if isinstance(m, ToolMessage)
    }

    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            for call in m.tool_calls:
                tools_called.append(call["name"])
                tool_inputs.append(call["args"])
                tool_outputs.append(tool_outputs_by_id.get(call["id"]))

    final_response = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and not m.tool_calls:
            final_response = m.content
            break

    intent = None
    for candidate in INTENT_PRIORITY:
        if candidate in tools_called:
            intent = TOOL_TO_INTENT[candidate]
            break
    # No tool was called at all -- either out_of_scope, or the agent
    # asked a clarifying question. We can't tell those apart without
    # an explicit classifier, so this is left as None rather than
    # guessed; see the module docstring.

    policy_applied = None
    for output in tool_outputs:
        if isinstance(output, dict) and output.get("policy_applied"):
            policy_applied = output["policy_applied"]

    return {
        "id": eval_id,
        "intent": intent,
        "tools_called": tools_called,
        "tool_inputs": tool_inputs,
        "tool_outputs": tool_outputs,
        "policy_applied": policy_applied,
        "final_response": final_response,
        "confirmation_required": any(t in SENSITIVE_TOOL_NAMES for t in tools_called),
        "confidence": None,  # no ReAct equivalent -- see module docstring
    }


def _safe_json_loads(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------

def run_batch(input_path: str, output_path: str) -> None:
    graph = build_react_graph(customer_id=1)  # default customer for eval
    input_file = Path(input_path)
    output_file = Path(output_path)

    if not input_file.exists():
        console.print(f"[red]Input file not found: {input_path}[/red]")
        sys.exit(1)

    lines = [l.strip() for l in input_file.read_text().splitlines() if l.strip()]
    results = []
    passed = 0
    total = len(lines)

    console.print(f"\n[bold]Running batch eval — {total} cases[/bold]\n")

    for line in lines:
        case = json.loads(line)
        eval_id = case["id"]
        message = case["message"]
        expected_intent = case.get("expected_intent")
        expected_tool = case.get("expected_tool")

        console.print(f"[cyan]▶ {eval_id}[/cyan]")
        console.print(f"  Message: {message}")

        try:
            config = {"configurable": {"thread_id": f"batch-{eval_id}"}}
            result = invoke_with_retry(graph, {
                "messages": [HumanMessage(content=message)],
                "customer_id": 1,
                "mode": "batch",
            }, config=config)

            output = build_output(eval_id, result)

            intent_ok = output["intent"] == expected_intent
            tool_ok = (
                expected_tool == "none" and not output["tools_called"]
            ) or (
                expected_tool != "none" and expected_tool in output["tools_called"]
            )
            case_pass = intent_ok and tool_ok
            passed += case_pass

            status = "[green]PASS[/green]" if case_pass else "[red]FAIL[/red]"
            console.print(f"  Intent : {output['intent']} (expected {expected_intent}) {'✓' if intent_ok else '✗'}")
            console.print(f"  Tools  : {output['tools_called']} (expected {expected_tool}) {'✓' if tool_ok else '✗'}")
            console.print(f"  Response: {output['final_response'].strip()}")
            console.print(f"  [{status}]\n")

            results.append(output)

        except Exception as exc:
            console.print(f"  [red]ERROR: {exc}[/red]\n")
            results.append({
                "id": eval_id, "intent": None, "tools_called": [], "tool_inputs": [],
                "tool_outputs": [], "policy_applied": None,
                "final_response": f"ERROR: {exc}", "confirmation_required": False,
                "confidence": None,
            })

    output_file.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )

    console.print(f"[bold]Results: {passed}/{total} passed[/bold]")
    console.print(f"Output written to [cyan]{output_path}[/cyan]")


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def run_interactive(customer_id: int) -> None:
    graph = build_react_graph(customer_id)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    console.print(Panel(
        f"[bold green]Ticket Booking Agent (ReAct)[/bold green]\n"
        f"Customer ID: [cyan]{customer_id}[/cyan]\n"
        f"Type [bold]quit[/bold] or [bold]exit[/bold] to stop.",
        title="Welcome"
    ))

    while True:
        try:
            user_input = console.input("\n[bold yellow]You:[/bold yellow] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            console.print("[dim]Goodbye.[/dim]")
            break

        try:
            result = invoke_with_retry(graph, {
                "messages": [HumanMessage(content=user_input)],
                "customer_id": customer_id,
                "mode": "interactive",
            }, config=config)

            # The graph physically pauses here -- this is not the LLM
            # being asked to confirm, it's tools_node's interrupt()
            # call stopping the whole run. Loop in case the agent
            # queued more than one sensitive tool call in this turn.
            while "__interrupt__" in result:
                pending = result["__interrupt__"][0].value
                console.print(Panel(
                    pending["question"],
                    title="[bold yellow]Confirmation needed[/bold yellow]",
                    border_style="yellow",
                ))
                answer = console.input("[bold yellow]Confirm (yes/no):[/bold yellow] ").strip()
                result = invoke_with_retry(graph, Command(resume=answer), config=config)

            _print_response(result)

        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")


def _print_response(result: dict) -> None:
    messages = result.get("messages", [])
    tools_this_turn = [
        call["name"]
        for m in messages if isinstance(m, AIMessage) and m.tool_calls
        for call in m.tool_calls
    ]
    final_response = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and not m.tool_calls:
            final_response = m.content
            break

    meta = Text()
    if tools_this_turn:
        meta.append(f"tools={tools_this_turn}", style="dim")
        console.print(meta)

    console.print(Panel(final_response, title="[bold green]Agent[/bold green]", border_style="green"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--batch", "batch_input", default=None, help="Path to .jsonl eval file")
@click.option("--out", "batch_output", default="outputs.jsonl", show_default=True, help="Output .jsonl path")
@click.option("--interactive", "interactive", is_flag=True, default=False, help="Run interactive chat")
@click.option("--customer-id", "customer_id", default=1, show_default=True, help="Customer ID for interactive mode")
def main(batch_input, batch_output, interactive, customer_id):
    if batch_input:
        run_batch(batch_input, batch_output)
    elif interactive:
        run_interactive(customer_id)
    else:
        click.echo("Specify --batch <file> or --interactive. Use --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()