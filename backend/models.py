"""Pydantic/dataclass types shared by the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass
class ShopDeps:
    """Per-run context threaded through every agent call and delegation.

    This is bookkeeping only -- never shop data, which comes solely from the
    MCP server. `delegation_depth` lets `delegate_to_*` tools refuse once
    `MAX_DELEGATION_DEPTH` is hit, so two agents can't loop on each other
    forever and burn tokens.
    """

    run_id: str
    agent_name: str
    delegation_depth: int = 0


class TicketResolution(BaseModel):
    """Structured output every specialist agent returns for one ticket."""

    ticket_id: int = Field(description="The ticket this result is about.")
    status_recommendation: Literal["resolved", "needs_approval", "escalated"] = Field(
        description=(
            "'resolved' if fully handled, 'needs_approval' if a human/Boss sign-off is still "
            "required before acting, 'escalated' if it's outside this agent's authority."
        )
    )
    summary: str = Field(description="Plain-English account of what was checked and decided, citing real tool results.")
    tools_used: list[str] = Field(default_factory=list, description="Names of MCP tools actually called while handling this ticket.")


class BossReport(BaseModel):
    """Boss agent's final structured output after triaging the open tickets."""

    tickets_handled: list[TicketResolution] = Field(description="One entry per ticket triaged this run.")
    overall_summary: str = Field(description="A short end-of-day summary across all tickets handled, for a human owner to skim.")


class AuditEntry(BaseModel):
    """One logged event from a team run, appended to output/audit_trail.json.

    One entry per MCP tool call or delegation an agent actually makes
    (`tool_name` set), plus one closing entry per agent sub-run with
    `stop_reason` set and `tool_name` null. No customer PII beyond what's
    already on a ticket (a name) is ever logged here.
    """

    timestamp: str = Field(description="UTC ISO-8601 timestamp of this event.")
    run_id: str = Field(description="Groups every entry from the same top-level team run together.")
    agent: str = Field(description="Which agent (boss/inventory/accounting/facilities/customer_service) produced this entry.")
    tool_name: str | None = Field(default=None, description="MCP tool or delegate_to_* name called, or null for a closing entry.")
    args: dict = Field(default_factory=dict, description="Short/truncated tool arguments, {} for a closing entry.")
    result: str = Field(default="", description="Short/truncated tool result, or a final summary for a closing entry.")
    stop_reason: str | None = Field(default=None, description="Set only on a closing entry, e.g. 'completed' or 'error: ValueError'.")
