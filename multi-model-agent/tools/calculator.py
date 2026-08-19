"""A safe arithmetic calculator tool.

Deliberately avoids eval() on arbitrary expressions from the model; only a
fixed set of operations on two numbers are supported. Extend the `OPS` dict
if you need more operations (pow, mod, sqrt, etc).
"""

from typing import Any

from claude_agent_sdk import tool

OPS = {
    "add": lambda a, b: a + b,
    "subtract": lambda a, b: a - b,
    "multiply": lambda a, b: a * b,
    "divide": lambda a, b: a / b if b != 0 else None,
    "power": lambda a, b: a**b,
}


@tool(
    "calculator",
    "Perform basic arithmetic (add, subtract, multiply, divide, power) on two numbers.",
    {"operation": str, "a": float, "b": float},
)
async def calculator(args: dict[str, Any]) -> dict[str, Any]:
    op = args.get("operation", "")
    a, b = args.get("a"), args.get("b")

    fn = OPS.get(op)
    if fn is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Unknown operation '{op}'. Supported: {', '.join(OPS)}",
                }
            ],
            "is_error": True,
        }

    result = fn(a, b)
    if result is None:
        return {
            "content": [{"type": "text", "text": "Division by zero is not allowed."}],
            "is_error": True,
        }

    return {"content": [{"type": "text", "text": f"{a} {op} {b} = {result}"}]}
