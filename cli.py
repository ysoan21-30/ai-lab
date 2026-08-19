"""
Rich terminal REPL for the multi-model agent.

Features over the plain agent.py REPL:
  - Live token-by-token streaming of the answer as it's generated
  - Colored panels for tool calls, tier/cost info, and errors
  - Conversation memory across turns (same session_id resumed each turn)
  - Slash commands: /tier, /auto, /clear, /history, /help, /exit

Run:
    python cli.py
"""

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from config import TIERS
from core import run_turn

console = Console()

HELP_TEXT = """\
[bold]Commands[/bold]
  /tier <fast|balanced|deep>   Force every future turn to this model tier
  /auto                        Go back to automatic tier routing
  /clear                       Start a new conversation (forgets history)
  /history                     Show this conversation's turn count / cost so far
  /help                        Show this message
  /exit, /quit                 Leave
"""

TIER_COLORS = {"fast": "green", "balanced": "yellow", "deep": "magenta"}


def print_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Multi-Model Agent[/bold cyan]\n"
            "Type a message, or [bold]/help[/bold] for commands.",
            border_style="cyan",
        )
    )


async def stream_answer(prompt: str, session_id: str | None, force_tier: str | None):
    """Runs one turn, live-printing the answer as it streams in."""
    buffer: list[str] = []
    tool_calls_seen: list[tuple[str, dict]] = []

    def on_delta(chunk: str) -> None:
        buffer.append(chunk)
        console.print(chunk, end="", highlight=False)

    def on_tool(name: str, tool_input: dict) -> None:
        tool_calls_seen.append((name, tool_input))
        short_name = name.split("__")[-1]
        console.print(
            f"\n[dim]  ↳ using tool [bold]{short_name}[/bold]({tool_input})[/dim]\n"
        )

    console.print("\n[bold blue]Agent[/bold blue] ", end="")
    result = await run_turn(
        prompt,
        session_id=session_id,
        force_tier=force_tier,
        on_text_delta=on_delta,
        on_tool_call=on_tool,
    )
    console.print()  # newline after streamed text
    return result


async def repl() -> None:
    print_banner()

    session_id: str | None = None
    forced_tier: str | None = None
    turn_count = 0
    total_cost = 0.0

    while True:
        try:
            prompt = console.input("\n[bold green]>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not prompt:
            continue

        if prompt.startswith("/"):
            cmd, *rest = prompt[1:].split(maxsplit=1)
            arg = rest[0].strip() if rest else ""

            if cmd in {"exit", "quit"}:
                break
            elif cmd == "help":
                console.print(Panel(HELP_TEXT, border_style="blue"))
            elif cmd == "tier":
                if arg in TIERS:
                    forced_tier = arg
                    console.print(f"[dim]Forcing tier: {arg}[/dim]")
                else:
                    console.print(
                        f"[red]Unknown tier '{arg}'. Choose from: {', '.join(TIERS)}[/red]"
                    )
            elif cmd == "auto":
                forced_tier = None
                console.print("[dim]Back to automatic tier routing.[/dim]")
            elif cmd == "clear":
                session_id = None
                turn_count = 0
                total_cost = 0.0
                console.print("[dim]Conversation cleared.[/dim]")
            elif cmd == "history":
                console.print(f"[dim]{turn_count} turn(s), ${total_cost:.4f} total so far.[/dim]")
            else:
                console.print(f"[red]Unknown command: /{cmd}. Try /help.[/red]")
            continue

        result = await stream_answer(prompt, session_id, forced_tier)

        if result.error:
            console.print(Panel(result.error, title="Error", border_style="red"))
            continue

        session_id = result.session_id
        turn_count += 1
        total_cost += result.cost_usd or 0.0

        color = TIER_COLORS.get(result.tier, "white")
        cost_str = f"${result.cost_usd:.4f}" if result.cost_usd is not None else "n/a"
        console.print(
            Text.from_markup(
                f"[dim][{color}]{result.tier}[/{color}] · {result.model} · {cost_str}[/dim]"
            )
        )


if __name__ == "__main__":
    asyncio.run(repl())
