"""Shared entry point for running the Boss agent, used by both the CLI
(run_team.py) and the FastAPI backend (main.py)."""

from __future__ import annotations

import uuid

from agents import AGENT_USAGE_LIMITS, build_agents, log_event
from models import BossReport, ShopDeps

TRIAGE_ALL_INSTRUCTIONS = (
    "Triage every open ticket right now: call list_open_tickets first, then handle or "
    "delegate each one per your shop rules, and report back one TicketResolution per ticket "
    "plus an overall_summary."
)


def _single_ticket_instructions(ticket_id: int) -> str:
    return (
        f"Handle ticket #{ticket_id} right now: call get_ticket({ticket_id}) first, then handle "
        "or delegate it per your shop rules, and report back a BossReport containing exactly one "
        "TicketResolution for this ticket plus an overall_summary."
    )


async def run_boss(instructions: str) -> tuple[str, BossReport]:
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    agents = build_agents()
    deps = ShopDeps(run_id=run_id, agent_name="boss", delegation_depth=0)

    log_event(run_id, "boss", None, {}, "team run started")
    try:
        run_result = await agents["boss"].run(
            instructions,
            deps=deps,
            output_type=BossReport,
            usage_limits=AGENT_USAGE_LIMITS,
        )
        report = run_result.output
        log_event(run_id, "boss", None, {}, report.overall_summary, stop_reason="completed")
    except Exception as exc:
        log_event(run_id, "boss", None, {}, str(exc), stop_reason=f"error: {type(exc).__name__}")
        raise
    return run_id, report


async def run_triage_all_open() -> tuple[str, BossReport]:
    return await run_boss(TRIAGE_ALL_INSTRUCTIONS)


async def run_single_ticket(ticket_id: int) -> tuple[str, BossReport]:
    return await run_boss(_single_ticket_instructions(ticket_id))
