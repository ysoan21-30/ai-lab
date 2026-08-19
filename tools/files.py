"""File read/write tools, sandboxed to a WORKSPACE_DIR.

Paths are resolved relative to WORKSPACE_DIR and any attempt to escape it
(via '..' or an absolute path outside the sandbox) is rejected. This keeps
the agent from touching arbitrary files on the machine it runs on.
"""

import os
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

WORKSPACE_DIR = Path(os.environ.get("AGENT_WORKSPACE_DIR", "./workspace")).resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def resolve_workspace_path(path: str) -> Path | None:
    """Resolve `path` relative to WORKSPACE_DIR, rejecting any attempt to
    escape the sandbox. Returns None if the path escapes. Shared with the
    data-science tools so datasets/scripts live in the same sandboxed area
    as read_file/write_file."""
    candidate = (WORKSPACE_DIR / path).resolve()
    if WORKSPACE_DIR not in candidate.parents and candidate != WORKSPACE_DIR:
        return None
    return candidate


# Backwards-compatible alias used within this module.
_resolve = resolve_workspace_path


@tool(
    "read_file",
    "Read the contents of a text file inside the agent's workspace directory.",
    {"path": str},
)
async def read_file(args: dict[str, Any]) -> dict[str, Any]:
    target = _resolve(args["path"])
    if target is None:
        return {
            "content": [{"type": "text", "text": "Path escapes the workspace sandbox."}],
            "is_error": True,
        }
    if not target.exists():
        return {
            "content": [{"type": "text", "text": f"File not found: {args['path']}"}],
            "is_error": True,
        }
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "content": [{"type": "text", "text": "File is not valid UTF-8 text."}],
            "is_error": True,
        }
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "write_file",
    "Write text content to a file inside the agent's workspace directory (creates or overwrites).",
    {"path": str, "content": str},
)
async def write_file(args: dict[str, Any]) -> dict[str, Any]:
    target = _resolve(args["path"])
    if target is None:
        return {
            "content": [{"type": "text", "text": "Path escapes the workspace sandbox."}],
            "is_error": True,
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(args["content"], encoding="utf-8")
    return {
        "content": [{"type": "text", "text": f"Wrote {len(args['content'])} chars to {args['path']}"}]
    }
