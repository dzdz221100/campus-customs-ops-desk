"""Builds the five Campus Customs agents (Boss, Inventory, Accounting,
Facilities, Customer Service) over the shared campus-customs MCP server,
wired with full agent-to-agent delegation.

All shop facts and all shop-state changes go through the MCP server at
mcp_server/campus_customs_server.py -- no second, bypassing tools layer.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from audit import append_audit_entries, truncate
from models import AuditEntry, ShopDeps, TicketResolution

BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
PROMPTS_DIR = BACKEND_ROOT / "prompts"
SERVER_SCRIPT = PROJECT_ROOT / "mcp_server" / "campus_customs_server.py"
ENV_PATH = PROJECT_ROOT / ".env"

# The only model every agent on this team is allowed to use.
MODEL_NAME = "gpt-6-luna"

# Keeps any one agent's own tool-calling loop bounded -- a specialist here
# only ever needs a handful of calls (get_ticket, 1-3 lookups, maybe one
# delegation, update_ticket_status). This leaves headroom without allowing
# an unbounded (and unboundedly expensive) loop.
AGENT_USAGE_LIMITS = UsageLimits(request_limit=10, tool_calls_limit=8)

# How many hops a ticket can be delegated across agents before a
# delegate_to_* tool refuses and forces a direct decision instead. Full
# agent-to-agent connectivity means a cycle (A -> B -> A -> B...) is
# possible in principle; this is the hard stop on that, and on the token
# cost such a cycle would otherwise rack up.
#
# Set to 3, not 2: Problem 9's end-to-end run showed that 2 was one hop
# short of the shop's own legitimate approval chain -- Boss -> a specialist
# -> Accounting -> Boss (for sign-off on a payment over the $500 threshold)
# is a real 3-hop business process, not a runaway loop, and capping it at 2
# blocked Accounting from ever getting Boss's go-ahead to prepare a payment
# at all. 3 still bounds the graph (no agent can bounce a ticket around
# indefinitely) while allowing that one real round trip to complete.
MAX_DELEGATION_DEPTH = 3

AGENT_PROMPT_FILES = {
    "boss": "boss.md",
    "inventory": "inventory.md",
    "accounting": "accounting.md",
    "facilities": "facilities.md",
    "customer_service": "customer_service.md",
}

load_dotenv(ENV_PATH, override=False)

def log_event(run_id: str, agent: str, tool_name: str | None, args: dict, result: object, stop_reason: str | None = None) -> None:
    """Writes straight to output/audit_trail.json as each event happens
    (not buffered until the run ends) -- the dashboard's Agent Activity feed
    (Problem 8) polls that file and needs to see entries appear live while a
    run is still in progress, not all at once after it finishes."""
    append_audit_entries(
        [
            AuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                run_id=run_id,
                agent=agent,
                tool_name=tool_name,
                args={k: truncate(v, 120) for k, v in args.items()} if args else {},
                result=truncate(result),
                stop_reason=stop_reason,
            )
        ]
    )


def make_model() -> OpenAIChatModel:
    portkey_api_key = os.getenv("PORTKEY_API_KEY")
    if not portkey_api_key:
        raise RuntimeError(f"PORTKEY_API_KEY is missing. Expected it in {ENV_PATH}.")
    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenAIProvider(base_url="https://api.portkey.ai/v1", api_key=portkey_api_key),
    )


async def _process_tool_call(ctx: RunContext[ShopDeps], call_tool, tool_name: str, args: dict):
    """Shared by every agent's MCP toolset -- logs each real MCP tool call
    (the shop-fact/shop-state layer) to the audit trail, then forwards it
    unchanged."""
    result = await call_tool(tool_name, args)
    log_event(ctx.deps.run_id, ctx.deps.agent_name, tool_name, args, result)
    return result


# The only MCP tool capable of actually moving money. Excluded from every
# agent's toolset below -- real payment execution only happens when the
# FastAPI backend's human-approval route calls it directly (see
# backend/main.py), never from an agent.
MONEY_MOVING_TOOL = "resolve_payment_proposal"


def _make_toolset() -> MCPToolset:
    base = MCPToolset(SERVER_SCRIPT, process_tool_call=_process_tool_call)
    return base.filtered(lambda ctx, tool_def: tool_def.name != MONEY_MOVING_TOOL)


def build_agents() -> dict[str, Agent]:
    model = make_model()
    agents: dict[str, Agent] = {}
    for name, prompt_file in AGENT_PROMPT_FILES.items():
        system_prompt = (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")
        agents[name] = Agent(
            model,
            output_type=TicketResolution,
            system_prompt=system_prompt,
            deps_type=ShopDeps,
            toolsets=[_make_toolset()],
            retries=2,
            # gpt-6-luna rejects function tools on /v1/chat/completions unless
            # reasoning_effort is turned off (azure-openai 400s otherwise).
            model_settings={"openai_reasoning_effort": "none"},
        )
    _wire_delegation(agents)
    return agents


def _wire_delegation(agents: dict[str, Agent]) -> None:
    """Full connectivity: every agent gets a delegate_to_<other> tool for
    every other agent. Looked up lazily through `agents` so build order
    doesn't matter and there's no circular-construction problem."""
    for from_name, agent in agents.items():
        for to_name in agents:
            if to_name != from_name:
                _add_delegate_tool(agent, from_name, to_name, agents)


def _add_delegate_tool(agent: Agent, from_name: str, to_name: str, agents: dict[str, Agent]) -> None:
    tool_name = f"delegate_to_{to_name}"

    async def delegate(ctx: RunContext[ShopDeps], ticket_id: int, instructions: str) -> str:
        if ctx.deps.delegation_depth >= MAX_DELEGATION_DEPTH:
            msg = (
                f"Delegation limit ({MAX_DELEGATION_DEPTH} hops) reached -- "
                f"resolve or escalate ticket {ticket_id} yourself instead of delegating further."
            )
            log_event(ctx.deps.run_id, from_name, tool_name, {"ticket_id": ticket_id}, msg)
            return msg

        log_event(
            ctx.deps.run_id,
            from_name,
            tool_name,
            {"ticket_id": ticket_id, "instructions": instructions},
            "delegating...",
        )
        child_deps = ShopDeps(
            run_id=ctx.deps.run_id,
            agent_name=to_name,
            delegation_depth=ctx.deps.delegation_depth + 1,
        )
        run_result = await agents[to_name].run(
            f"Ticket #{ticket_id}, handed to you by {from_name}: {instructions}",
            deps=child_deps,
            usage_limits=AGENT_USAGE_LIMITS,
        )
        output: TicketResolution = run_result.output
        log_event(ctx.deps.run_id, to_name, None, {}, output.model_dump(), stop_reason="delegation_completed")
        return output.model_dump_json()

    delegate.__name__ = tool_name
    delegate.__doc__ = (
        f"Hand this ticket off to the {to_name.replace('_', ' ').title()} agent, with clear "
        "instructions on what you need from them. Returns their structured result as JSON."
    )
    agent.tool(delegate)
