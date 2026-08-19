"""
One-shot CLI entry point for the multi-model agent.

Usage:
    python agent.py "your prompt here"

For a proper interactive experience, use one of:
    python cli.py               # rich terminal REPL, streaming + slash commands
    streamlit run web_ui.py     # browser chat UI

This file is kept as a minimal, dependency-light single-shot runner (handy
for scripting/piping) built on the same core.run_turn() used by both
interfaces.
"""

import asyncio
import sys

from core import run_turn


async def main() -> None:
    if len(sys.argv) <= 1:
        print(
            "Usage: python agent.py \"your prompt\"\n"
            "For an interactive session, run: python cli.py\n"
            "For a web UI, run: streamlit run web_ui.py"
        )
        return

    prompt = " ".join(sys.argv[1:])
    result = await run_turn(
        prompt,
        on_tool_call=lambda name, inp: print(f"[tool call] {name}({inp})"),
    )

    if result.error:
        print(f"[error] {result.error}")
        return

    cost_str = f"${result.cost_usd:.4f}" if result.cost_usd is not None else "n/a"
    print(f"[router] tier={result.tier} model={result.model}")
    print(f"\n{result.text}\n")
    print(f"[result] cost={cost_str} tier={result.tier}")


if __name__ == "__main__":
    asyncio.run(main())
