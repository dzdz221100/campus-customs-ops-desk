"""Campus Customs MCP server.

Exposes tools over the Campus Customs working database
(data/campus_customs_new.db) so every agent in this assignment reads and
acts on the same ground truth instead of guessing or inventing numbers.
This is the *only* layer that touches the database -- agents never read or
write `campus_customs_new.db` directly, only through these tools.

Run the server (stdio):  python campus_customs_server.py
Run the server (HTTP):    python campus_customs_server.py --http
HTTP URL:                  http://127.0.0.1:8010/mcp
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
DB_PATH = HERE.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")


def _query(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _ensure_schema() -> None:
    """`payment_proposals` isn't part of the original database -- it's added
    here (idempotently) so a `reset` that restores the original file still
    ends up with a working proposals table on the next tool call, without
    ever touching the original `campus_customs.db`."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                kind TEXT NOT NULL,
                ref_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                account TEXT NOT NULL,
                reason TEXT,
                proposed_by TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_by TEXT,
                resolved_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


_ensure_schema()


@mcp.tool
def check_inventory_stock(sku: str, size: str) -> dict:
    """Look up the real on-hand quantity and location for one SKU/size in `inventory`.

    Use this before deciding whether a customer order (e.g. ticket 101) can
    actually be fulfilled -- it returns the true on-hand qty from the
    database, never a guess.
    """
    rows = _query(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (sku, size),
    )
    if not rows:
        return {"found": False, "sku": sku, "size": size}
    return {"found": True, **rows[0]}


@mcp.tool
def get_lease_status(lease_id: int) -> dict:
    """Look up one lease's landlord, monthly rent, and next due date in `leases`.

    Use this to verify a rent notice (e.g. ticket 102) against the actual
    lease record -- the claimed amount and due date -- before approving any
    payment.
    """
    rows = _query(
        "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
        (lease_id,),
    )
    if not rows:
        return {"found": False, "lease_id": lease_id}
    return {"found": True, **rows[0]}


@mcp.tool
def get_pricing(sku: str) -> dict:
    """Look up unit cost and list price for one SKU in `pricing`.

    Use this to evaluate a discount request (e.g. ticket 103) against the
    product's actual margin instead of guessing what price is fair.
    """
    rows = _query(
        "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
        (sku,),
    )
    if not rows:
        return {"found": False, "sku": sku}
    return {"found": True, **rows[0]}


@mcp.tool
def get_today() -> dict:
    """Return the shop's "today" (`desk.date_today`) and any desk notes.

    Use this to judge whether a due date is actually overdue/upcoming --
    e.g. whether ticket 102's "rent due in 2 days" claim checks out, or how
    overdue ticket 101's linked invoice already is -- instead of assuming
    today's real-world date.
    """
    rows = _query("SELECT date_today, notes FROM desk LIMIT 1")
    if not rows:
        return {"found": False}
    return {"found": True, **rows[0]}


@mcp.tool
def list_open_tickets() -> list[dict]:
    """List every ticket in `tickets` with status = 'open'.

    Use this first to see the whole work queue (currently tickets 101, 102,
    103) before deciding who should handle what -- never assume which
    tickets are open without checking.
    """
    return _query("SELECT * FROM tickets WHERE status = 'open' ORDER BY id")


@mcp.tool
def list_all_tickets() -> list[dict]:
    """List every ticket in `tickets`, any status, open or resolved.

    Use this (not `list_open_tickets`) when something needs to see the whole
    board regardless of state -- e.g. a dashboard showing each ticket's
    current status.
    """
    return _query("SELECT * FROM tickets ORDER BY id")


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Look up the full row for one ticket in `tickets`.

    Use this to get a ticket's requester, subject, linked sku/size/qty,
    lease_id/invoice_id, and notes in full before acting on it.
    """
    rows = _query("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if not rows:
        return {"found": False, "ticket_id": ticket_id}
    return {"found": True, **rows[0]}


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Look up one invoice's vendor, amount, due date, and status in `invoices`.

    Use this on ticket 101's linked invoice (501) to see the real amount
    owed and whether it's already been paid before telling a customer when
    restocked items will arrive.
    """
    rows = _query(
        "SELECT id, vendor_id, amount, due_date, status, description FROM invoices WHERE id = ?",
        (invoice_id,),
    )
    if not rows:
        return {"found": False, "invoice_id": invoice_id}
    return {"found": True, **rows[0]}


@mcp.tool
def get_vendor(vendor_id: int) -> dict:
    """Look up one vendor's name, specialty, and lead_days in `vendors`.

    Use this to know how long a restock/reprint will actually take (e.g. the
    vendor behind ticket 101's invoice) before promising a delivery date.
    """
    rows = _query("SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,))
    if not rows:
        return {"found": False, "vendor_id": vendor_id}
    return {"found": True, **rows[0]}


@mcp.tool
def get_cash_balance(account: str = "checking") -> dict:
    """Look up one cash account's real balance in `cash_accounts`.

    Use this before approving any payment (a vendor invoice or rent) to
    confirm the shop can actually cover it, instead of assuming it can.
    """
    rows = _query("SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,))
    if not rows:
        return {"found": False, "account": account}
    return {"found": True, **rows[0]}


def _execute_payment(kind: str, ref_id: int, amount: float, account: str, approved_by: str) -> dict:
    """Actually record a payment against a real invoice or lease and debit
    the cash account. Not an MCP tool -- this is the real money-moving logic,
    only reachable through `resolve_payment_proposal`, which only the
    backend's human-approval route is meant to call. No agent has a tool
    that reaches this function directly."""
    if kind not in ("invoice", "lease"):
        return {"approved": False, "reason": f"kind must be 'invoice' or 'lease', got {kind!r}"}

    ref_table = "invoices" if kind == "invoice" else "leases"
    if not _query(f"SELECT id FROM {ref_table} WHERE id = ?", (ref_id,)):
        return {"approved": False, "reason": f"No {kind} with id {ref_id} in the database"}

    balance_rows = _query("SELECT balance FROM cash_accounts WHERE name = ?", (account,))
    if not balance_rows:
        return {"approved": False, "reason": f"No cash account named {account!r}"}
    balance = balance_rows[0]["balance"]
    if amount > balance:
        return {"approved": False, "reason": f"Payment of {amount} exceeds {account} balance of {balance}"}

    now = datetime.now(timezone.utc).isoformat()
    new_balance = balance - amount
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, account, now, approved_by),
        )
        payment_id = cur.lastrowid
        conn.execute("UPDATE cash_accounts SET balance = ? WHERE name = ?", (new_balance, account))
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
        conn.commit()
    finally:
        conn.close()

    return {
        "approved": True,
        "payment_id": payment_id,
        "kind": kind,
        "ref_id": ref_id,
        "amount": amount,
        "account": account,
        "approved_by": approved_by,
        "paid_at": now,
        "new_balance": new_balance,
    }


@mcp.tool
def propose_payment(ticket_id: int, kind: str, ref_id: int, amount: float, account: str, reason: str, proposed_by: str) -> dict:
    """Prepare (but do not execute) a payment against a real invoice or lease.

    `kind` must be "invoice" or "lease"; `ref_id` must be that exact row's id
    in the database -- this never prepares a payment that isn't tied to a
    real invoice/lease. This only inserts a row into `payment_proposals`
    with status "pending" -- it never touches `cash_accounts`, `payments`,
    or `invoices`. A human reviews and approves/rejects the proposal later
    (via `resolve_payment_proposal`, which no agent can call); this is the
    only way any agent can get money moved at all.
    """
    if kind not in ("invoice", "lease"):
        return {"created": False, "reason": f"kind must be 'invoice' or 'lease', got {kind!r}"}
    ref_table = "invoices" if kind == "invoice" else "leases"
    if not _query(f"SELECT id FROM {ref_table} WHERE id = ?", (ref_id,)):
        return {"created": False, "reason": f"No {kind} with id {ref_id} in the database"}

    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """
            INSERT INTO payment_proposals
                (ticket_id, kind, ref_id, amount, account, reason, proposed_by, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (ticket_id, kind, ref_id, amount, account, reason, proposed_by, now),
        )
        proposal_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    return {"created": True, **_query("SELECT * FROM payment_proposals WHERE id = ?", (proposal_id,))[0]}


@mcp.tool
def list_payment_proposals(status: str = "pending") -> list[dict]:
    """List payment proposals in `payment_proposals`, filtered by status.

    Use `status="pending"` (the default) to see what's waiting on a human's
    approval right now; pass "approved", "rejected", or "" (empty, for all)
    to see other states.
    """
    if status:
        return _query("SELECT * FROM payment_proposals WHERE status = ? ORDER BY id", (status,))
    return _query("SELECT * FROM payment_proposals ORDER BY id")


@mcp.tool
def resolve_payment_proposal(proposal_id: int, resolved_by: str) -> dict:
    """Approve a pending payment proposal and actually move the money.

    This is the only tool in the whole server that can debit `cash_accounts`
    -- it is intentionally excluded from every agent's toolset (see
    `backend/agents.py`) so the only way a real payment happens is a human
    approving a proposal from the dashboard, which calls this. Fails
    (no write) if the proposal doesn't exist, isn't `pending`, or the
    underlying payment can't actually go through (e.g. insufficient funds) --
    in that last case the proposal stays `pending` so it can be revisited.
    """
    rows = _query("SELECT * FROM payment_proposals WHERE id = ?", (proposal_id,))
    if not rows:
        return {"approved": False, "reason": f"No payment proposal with id {proposal_id}"}
    proposal = rows[0]
    if proposal["status"] != "pending":
        return {"approved": False, "reason": f"Proposal {proposal_id} is already {proposal['status']}"}

    result = _execute_payment(proposal["kind"], proposal["ref_id"], proposal["amount"], proposal["account"], resolved_by)
    if not result.get("approved"):
        return result

    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE payment_proposals SET status = 'approved', resolved_by = ?, resolved_at = ? WHERE id = ?",
            (resolved_by, now, proposal_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {**result, "proposal_id": proposal_id}


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, resolution_notes: str) -> dict:
    """Update one ticket's status and append a resolution note in `tickets`.

    Use this to close out or escalate a ticket once a real decision has been
    made (e.g. after `propose_payment` succeeds, or after confirming stock).
    `resolution_notes` is appended to the ticket's existing notes, never
    replacing the original customer/requester text.
    """
    rows = _query("SELECT notes FROM tickets WHERE id = ?", (ticket_id,))
    if not rows:
        return {"found": False, "ticket_id": ticket_id}
    existing_notes = rows[0]["notes"] or ""
    combined_notes = f"{existing_notes} | {resolution_notes}".strip(" |")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
            (status, combined_notes, ticket_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"found": True, **_query("SELECT * FROM tickets WHERE id = ?", (ticket_id,))[0]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve Streamable HTTP on port 8010 instead of stdio",
    )
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=8010)
    else:
        mcp.run()
