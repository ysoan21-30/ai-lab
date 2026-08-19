"""
Starter tool set for the multi-model agent, plus the MCP server that
exposes them to the Claude Agent SDK.

Each tool is a small, single-purpose async function decorated with @tool.
Add new tools by writing a new function here (or in a new module) and
appending it to ALL_TOOLS below.
"""

from claude_agent_sdk import create_sdk_mcp_server

from .calculator import calculator
from .files import read_file, write_file
from .web_search import web_search
from .custom_api import custom_api_call
from .data_science import load_dataset, python_exec
from .scraping import scrape_page, crawl_site
from .rag_tools import retrieve_docs, list_rag_sources

ALL_TOOLS = [
    calculator,
    read_file,
    write_file,
    web_search,
    custom_api_call,
    load_dataset,
    python_exec,
    scrape_page,
    crawl_site,
    retrieve_docs,
    list_rag_sources,
]

# Server name shows up as the "mcp__<server_name>__<tool_name>" prefix that
# the agent uses to call these tools.
SERVER_NAME = "toolbox"

tools_server = create_sdk_mcp_server(
    name=SERVER_NAME,
    version="1.0.0",
    tools=ALL_TOOLS,
)

# Fully-qualified names, handy for allowed_tools lists.
ALLOWED_TOOL_NAMES = [f"mcp__{SERVER_NAME}__{t.name}" for t in ALL_TOOLS]
