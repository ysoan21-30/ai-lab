"""Placeholder tool for calling your own internal API / service.

This is the pattern to copy when you want the agent to call something
specific to your business (a CRM, an internal database, a ticketing system,
etc). Replace the body of `custom_api_call` with a real HTTP call, and
tighten the input_schema to match your API's real parameters.
"""

from typing import Any

from claude_agent_sdk import tool


@tool(
    "custom_api_call",
    (
        "Call a placeholder internal API. Replace this tool's implementation "
        "with a real call to your own service (CRM, database, internal API, etc)."
    ),
    {"endpoint": str, "payload": dict},
)
async def custom_api_call(args: dict[str, Any]) -> dict[str, Any]:
    endpoint = args.get("endpoint", "")
    payload = args.get("payload", {})

    # --- Replace below with a real request, e.g.:
    # async with httpx.AsyncClient() as client:
    #     resp = await client.post(f"https://api.yourcompany.com/{endpoint}", json=payload)
    #     resp.raise_for_status()
    #     return {"content": [{"type": "text", "text": resp.text}]}

    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"[placeholder] Would call endpoint '{endpoint}' with payload {payload}. "
                    "Implement tools/custom_api.py to connect this to a real API."
                ),
            }
        ]
    }
