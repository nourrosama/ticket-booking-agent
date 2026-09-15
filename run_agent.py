"""
CLI entrypoint for the ticket-booking agent.

Batch mode (eval):
    python run_agent.py --batch sample_questions_eval.jsonl --out outputs.jsonl

Interactive mode (chat):
    python run_agent.py --interactive --customer-id 3
"""
import json
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from agent.graph import build_graph

console = Console()

# policy_applied values that mean "just missing one piece of info the
# customer can supply in their next message" -- worth holding the
# conversation open for, rather than starting over from scratch
RECOVERABLE_POLICIES = {
    "booking_policy::missing_payment_method",
    "refund_policy::missing_booking_ref",
}


# ---------------------------------------------------------------------------
# Output contract builder
# ---------------------------------------------------------------------------

def build_output(eval_id: str, state: dict) -> dict:
    return {
        "id": eval_id,
        "intent": state.get("intent"),
        "tools_called": state.get("tools_called", []),
        "tool_inputs": state.get("tool_inputs", []),
        "tool_outputs": state.get("tool_outputs", []),
        "policy_applied": state.get("policy_applied"),
        "final_response": state.get("final_response", ""),
        "confirmation_required": state.get("confirmation_required", False),
        "confidence": state.get("confidence", 0.0),
    }


# ---------------------------------------------------------------------------
# Resilient graph invocation -- retries transient API/network failures
# (e.g. Groq connection hiccups on the free tier) a couple of times
# before giving up. This is separate from the graph's own internal
# repair loop, which handles business-logic errors (bad route, no
# seats) -- this handles the call itself failing to complete at all.
# ---------------------------------------------------------------------------

def invoke_with_retry(graph, state: dict, max_attempts: int = 3, delay_seconds: float = 1.5) -> dict:
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return graph.invoke(state)
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                console.print(f"[dim]  (connection hiccup, retrying {attempt}/{max_attempts - 1}...)[/dim]")
                time.sleep(delay_seconds)
    raise last_exc


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------

def run_batch(input_path: str, output_path: str) -> None:
    graph = build_graph()
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
            state = invoke_with_retry(graph, {
                "customer_id": 1,   # default customer for eval
                "message": message,
                "mode": "batch",
            })

            actual_intent = state.get("intent")
            actual_tools = state.get("tools_called", [])

            intent_ok = actual_intent == expected_intent
            # "none" means no tool expected; otherwise check if expected tool was called
            tool_ok = (
                expected_tool == "none" and not actual_tools
            ) or (
                expected_tool != "none" and expected_tool in actual_tools
            )

            case_pass = intent_ok and tool_ok
            passed += case_pass

            status = "[green]PASS[/green]" if case_pass else "[red]FAIL[/red]"
            console.print(f"  Intent : {actual_intent} (expected {expected_intent}) {'✓' if intent_ok else '✗'}")
            console.print(f"  Tools  : {actual_tools} (expected {expected_tool}) {'✓' if tool_ok else '✗'}")
            console.print(f"  Response: {state.get('final_response', '').strip()}")
            console.print(f"  [{status}]\n")

            results.append(build_output(eval_id, state))

        except Exception as exc:
            console.print(f"  [red]ERROR: {exc}[/red]\n")
            results.append({
                "id": eval_id,
                "intent": None,
                "tools_called": [],
                "tool_inputs": [],
                "tool_outputs": [],
                "policy_applied": None,
                "final_response": f"ERROR: {exc}",
                "confirmation_required": False,
                "confidence": 0.0,
            })

    # Write outputs.jsonl -- explicit utf-8 so LLM-generated punctuation
    # (curly quotes, non-breaking hyphens, etc.) never crashes the write
    # on a system whose default console/file encoding isn't utf-8
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
    graph = build_graph()
    console.print(Panel(
        f"[bold green]Ticket Booking Agent[/bold green]\n"
        f"Customer ID: [cyan]{customer_id}[/cyan]\n"
        f"Type [bold]quit[/bold] or [bold]exit[/bold] to stop.",
        title="Welcome"
    ))

    # Tracks whether we're waiting on a yes/no confirmation for a pending action
    pending_state: dict | None = None
    # Tracks a message that was declined only for missing one piece of
    # info (e.g. "what's your payment method?") so the next reply can
    # be combined with it instead of starting a fresh, context-less turn
    partial_message: str | None = None

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

        # --- Confirmation reply handling ---
        if pending_state is not None:
            if user_input.lower() in ("yes", "y", "confirm", "ok", "proceed"):
                try:
                    state = invoke_with_retry(graph, {
                        **pending_state,
                        "confirmed": True,
                        "mode": "interactive",
                    })
                    pending_state = None
                    _print_response(state)
                except Exception as exc:
                    console.print(f"[red]Error: {exc}[/red]")
                    pending_state = None
            else:
                console.print("[dim]Action cancelled.[/dim]")
                pending_state = None
            continue

        # --- Combine with a held-over partial request, if any ---
        message = f"{partial_message} {user_input}" if partial_message else user_input
        partial_message = None

        # --- Normal turn ---
        try:
            state = invoke_with_retry(graph, {
                "customer_id": customer_id,
                "message": message,
                "mode": "interactive",
            })

            _print_response(state)

            if state.get("confirmation_required") and not state.get("confirmed"):
                # Waiting on confirmation -- save state for next turn
                pending_state = {
                    "customer_id": customer_id,
                    "message": message,
                    "intent": state.get("intent"),
                    "entities": state.get("entities", {}),
                    "policy_ok": state.get("policy_ok"),
                    "policy_applied": state.get("policy_applied"),
                    "policy_reason": state.get("policy_reason"),
                    "confirmation_required": True,
                    "confirmed": False,
                    "mode": "interactive",
                }
            elif (not state.get("policy_ok", True)
                  and state.get("policy_applied") in RECOVERABLE_POLICIES):
                # Declined only for missing info -- hold the message so
                # the next reply can complete it, rather than losing context
                partial_message = message

        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")


def _print_response(state: dict) -> None:
    response = state.get("final_response", "").strip()
    intent = state.get("intent", "")
    tools = state.get("tools_called", [])

    meta = Text()
    meta.append(f"intent={intent}", style="dim")
    if tools:
        meta.append(f"  tools={tools}", style="dim")
    console.print(meta)

    console.print(Panel(response, title="[bold green]Agent[/bold green]", border_style="green"))


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