"""FastAPI backend for the Campus Customs dashboard.

Run (from inside backend/):
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from audit import append_audit_entries
from mcp_client import call_tool
from models import AuditEntry, BossReport
from team_runner import run_single_ticket

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
ORIGINAL_DB_PATH = DATA_DIR / "campus_customs.db"
WORKING_DB_PATH = DATA_DIR / "campus_customs_new.db"
AUDIT_PATH = OUTPUT_DIR / "audit_trail.json"

app = FastAPI(title="Campus Customs Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TicketSummary(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    status: str
    is_open: bool


class RunTicketResponse(BaseModel):
    run_id: str
    report: BossReport


class ApprovePaymentRequest(BaseModel):
    proposal_id: int


@app.get("/api/tickets", response_model=list[TicketSummary])
async def list_tickets():
    """All three tickets and whether each is currently open or resolved."""
    rows = await call_tool("list_all_tickets")
    return [
        TicketSummary(
            id=row["id"],
            type=row["type"],
            requester=row["requester"],
            subject=row["subject"],
            status=row["status"],
            is_open=row["status"] == "open",
        )
        for row in rows
    ]


@app.post("/api/tickets/{ticket_id}/run", response_model=RunTicketResponse)
async def run_ticket(ticket_id: int):
    """Run the agent team (Boss, delegating as needed) on one ticket now."""
    ticket = await call_tool("get_ticket", {"ticket_id": ticket_id})
    if not ticket.get("found"):
        raise HTTPException(status_code=404, detail=f"No ticket with id {ticket_id}")
    run_id, report = await run_single_ticket(ticket_id)
    return RunTicketResponse(run_id=run_id, report=report)


@app.get("/api/events")
async def recent_events(limit: int = 50, run_id: str | None = None):
    """Recent agent-loop events (what each agent did, which tools it used),
    newest first, so the dashboard can refresh and show live activity."""
    if not AUDIT_PATH.exists():
        return []
    entries = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if run_id:
        entries = [e for e in entries if e.get("run_id") == run_id]
    return list(reversed(entries))[:limit]


@app.get("/api/payments/proposals")
async def list_proposals(status: str = "pending"):
    """Payments the agent team has prepared, awaiting (by default) human approval."""
    return await call_tool("list_payment_proposals", {"status": status})


@app.post("/api/payments/approve")
async def approve_payment(body: ApprovePaymentRequest):
    """A human clicking Approve on the dashboard -- the only route that can
    actually move money. Agents only ever prepare a proposal via
    `propose_payment`; this calls `resolve_payment_proposal`, which no agent
    has in its toolset."""
    result = await call_tool(
        "resolve_payment_proposal",
        {"proposal_id": body.proposal_id, "resolved_by": "dashboard-operator"},
    )
    append_audit_entries(
        [
            AuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                run_id=f"human-approval-{body.proposal_id}",
                agent="human",
                tool_name="resolve_payment_proposal",
                args={"proposal_id": body.proposal_id},
                result=json.dumps(result),
                stop_reason="completed" if result.get("approved") else "rejected",
            )
        ]
    )
    if not result.get("approved"):
        raise HTTPException(status_code=400, detail=result.get("reason", "Payment could not be approved"))
    return result


@app.get("/api/cash")
async def cash_balance(account: str = "checking"):
    """The shop's current cash balance."""
    result = await call_tool("get_cash_balance", {"account": account})
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"No cash account named {account!r}")
    return result


@app.post("/api/reset")
async def reset_database():
    """Restore the working database to the original shipped values, for a fresh run."""
    shutil.copyfile(ORIGINAL_DB_PATH, WORKING_DB_PATH)
    return {"reset": True, "restored_from": str(ORIGINAL_DB_PATH.name), "restored_to": str(WORKING_DB_PATH.name)}
