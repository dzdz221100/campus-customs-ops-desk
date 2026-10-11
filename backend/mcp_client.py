"""Thin async helper the FastAPI backend uses to call MCP tools directly,
without going through an agent. Used for plain reads (tickets, cash,
proposals) and for the payment-approval route, which must be able to call
`resolve_payment_proposal` -- the one tool no agent's toolset includes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import Client

SERVER_SCRIPT = Path(__file__).resolve().parent.parent / "mcp_server" / "campus_customs_server.py"


async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    async with Client(SERVER_SCRIPT) as client:
        result = await client.call_tool(name, arguments or {})
        return result.data
