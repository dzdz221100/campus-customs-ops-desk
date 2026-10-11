"""MCP smoke test for the Campus Customs server (Problem 4).

Connects to campus_customs_server.py exactly as a vibe-coder client would
(over stdio, spawning the server as a subprocess) and calls each of the
three tools once, tying each call to the ticket/prompt it's meant to
unlock. Writes the evidence to output/mcp_smoke.json.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from fastmcp import Client

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SERVER_SCRIPT = HERE / "campus_customs_server.py"
DB_PATH = ROOT / "data" / "campus_customs_new.db"
OUTPUT_PATH = ROOT / "output" / "mcp_smoke.json"

TESTS = [
    {
        "ticket": 101,
        "prompt": "A customer (Tauhid Zaman) is asking for a white bulldog tee, size S -- do we actually have that in stock?",
        "tool": "check_inventory_stock",
        "arguments": {"sku": "CC-TEE-WHITE", "size": "S"},
        "db_check_sql": "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        "db_check_params": ("CC-TEE-WHITE", "S"),
    },
    {
        "ticket": 102,
        "prompt": "Elm City Properties says rent is due in 2 days on the Chapel Street lease -- what does our own lease record say the amount and due date actually are?",
        "tool": "get_lease_status",
        "arguments": {"lease_id": 1},
        "db_check_sql": "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
        "db_check_params": (1,),
    },
    {
        "ticket": 103,
        "prompt": "The Yale AI Club wants a bulk discount on 20 navy hoodies -- what's our unit cost and list price on that SKU so we can judge the margin?",
        "tool": "get_pricing",
        "arguments": {"sku": "CC-HOOD-NAVY"},
        "db_check_sql": "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
        "db_check_params": ("CC-HOOD-NAVY",),
    },
]


def db_row(sql: str, params: tuple) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


async def main() -> None:
    results = []
    async with Client(SERVER_SCRIPT) as client:
        for test in TESTS:
            tool_result = await client.call_tool(test["tool"], test["arguments"])
            tool_output = tool_result.data
            expected = db_row(test["db_check_sql"], test["db_check_params"])
            matches_db = all(tool_output.get(k) == v for k, v in expected.items())
            results.append(
                {
                    "ticket": test["ticket"],
                    "prompt": test["prompt"],
                    "tool": test["tool"],
                    "arguments": test["arguments"],
                    "tool_output": tool_output,
                    "matches_db_directly": matches_db,
                    "db_row_checked_against": expected,
                }
            )

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"Wrote {len(results)} results to {OUTPUT_PATH}")
    for r in results:
        print(f"  ticket {r['ticket']} / {r['tool']}: matches_db_directly={r['matches_db_directly']}")


if __name__ == "__main__":
    asyncio.run(main())
