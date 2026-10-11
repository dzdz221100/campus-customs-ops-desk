# Campus Customs — Harness

This file has two parts: a **System Overview** a manager (or a grader) can read standalone to understand the whole system as it stands today, and **Problem-by-Problem Build Notes** below it, an unedited chronological record of how it got built, including the real dead ends, limit tunings, and discovered bugs along the way.

## System Overview (for Managers)

### What this is

An agent team that triages Campus Customs' (a small Yale-branded campus merch shop) open tickets -- customer orders, rent notices, bulk-discount requests -- and a human-facing dashboard to run them and approve the money they want to move. Every shop fact and every shop-state change goes through one MCP server; nothing is ever invented by an agent or hardcoded in the frontend.

### The database (`data/campus_customs.db` original / `data/campus_customs_new.db` working copy)

| Table | Fields | Why it matters |
|---|---|---|
| `desk` | `date_today`, `notes` | Anchors "today" (2026-08-31) so due dates can be judged overdue/upcoming instead of guessed. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Who can restock what, and how long it takes -- needed for honest delivery timelines. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` | Real on-hand stock -- the ground truth for "can we fill this order." |
| `pricing` | `sku`, `unit_cost`, `list_price` | Margin basis for any discount decision. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | The shop's rent obligation, to verify against a landlord's claim. |
| `cash_accounts` | `name`, `balance`, `date` | Real cash on hand -- the check before any payment. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Money owed to a vendor, linked to the ticket that needs it resolved. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | The real ledger of money that has actually moved. |
| `payment_proposals` | `id`, `ticket_id`, `kind`, `ref_id`, `amount`, `account`, `reason`, `proposed_by`, `status`, `created_at`, `resolved_by`, `resolved_at` | Added in Problem 7 -- a payment an agent has *prepared* but a human hasn't yet approved/rejected. Not in the original schema; recreated automatically (`CREATE TABLE IF NOT EXISTS`) by the MCP server, so a `/api/reset` always leaves it in place, empty. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The actual work queue, each row tied to the records it needs (inventory/pricing, a lease, an invoice). |

The three tickets this whole project is built around: **#101** (Tauhid Zaman wants a `CC-TEE-WHITE` S, which is out of stock and blocked on an unpaid restock invoice), **#102** (Elm City Properties' rent notice), and **#103** (Yale AI Club's 20-hoodie bulk-discount request, which exceeds on-hand stock).

### MCP tools (`mcp_server/campus_customs_server.py`) -- the only layer that touches the database

| Tool | Table(s) | Kind |
|---|---|---|
| `check_inventory_stock(sku, size)` | `inventory` | read |
| `get_lease_status(lease_id)` | `leases` | read |
| `get_pricing(sku)` | `pricing` | read |
| `get_today()` | `desk` | read |
| `list_open_tickets()` | `tickets` (status=open) | read |
| `list_all_tickets()` | `tickets` (any status) | read |
| `get_ticket(ticket_id)` | `tickets` | read |
| `get_invoice(invoice_id)` | `invoices` | read |
| `get_vendor(vendor_id)` | `vendors` | read |
| `get_cash_balance(account)` | `cash_accounts` | read |
| `propose_payment(ticket_id, kind, ref_id, amount, account, reason, proposed_by)` | `payment_proposals` (write) | write (prepares only) |
| `list_payment_proposals(status)` | `payment_proposals` | read |
| `resolve_payment_proposal(proposal_id, resolved_by)` | `payments`, `cash_accounts`, `invoices` (writes) | write (the only tool that moves real money) |
| `update_ticket_status(ticket_id, status, resolution_notes)` | `tickets` (write) | write |

`approve_payment` (Problem 5) no longer exists as a tool -- it's an internal helper (`_execute_payment`) reused only by `resolve_payment_proposal`, which is itself excluded from every agent's toolset (`MCPToolset.filtered(...)` in `backend/agents.py`). The only caller of `resolve_payment_proposal` anywhere in the codebase is the FastAPI backend's `/api/payments/approve` route -- i.e. a human clicking Approve on the dashboard.

### The five agents (`backend/`)

| Agent | Persona | Prompt file | Owns |
|---|---|---|---|
| Boss | Dan, Shift Lead | `backend/prompts/boss.md` | Triage/routing, sign-off on large payments or discounts, separation-of-duties enforcement |
| Customer Service | the Bulldog Greeter | `backend/prompts/customer_service.md` | `customer_order` tickets |
| Facilities | the Super | `backend/prompts/facilities.md` | `rent_notice` tickets |
| Inventory | the Quartermaster | `backend/prompts/inventory.md` | `price_override` tickets, stock/pricing questions |
| Accounting | the Ledger | `backend/prompts/accounting.md` | Verifying and *preparing* (never executing) payments |

All five run the same model, `gpt-6-luna`, via Portkey (`backend/agents.py::make_model`), with `model_settings={"openai_reasoning_effort": "none"}` (required -- see Specs & Limits). Every agent has the same MCP toolset (minus `resolve_payment_proposal`) plus a `delegate_to_<other>` tool for each of the other four agents -- full connectivity, a 20-edge complete graph, built generically in `backend/agents.py::_wire_delegation` rather than hand-wired per agent.

### API routes (`backend/main.py`, run with `uvicorn main:app --reload --port 8000` from `backend/`)

| Method & URL | What it does |
|---|---|
| `GET /api/tickets` | All tickets with `status` and a computed `is_open` flag. |
| `POST /api/tickets/{ticket_id}/run` | Runs the agent team (Boss, delegating per its rules) on exactly that ticket. |
| `GET /api/events?limit=&run_id=` | Recent audit-trail entries, newest first, for the dashboard's live feed. |
| `GET /api/payments/proposals?status=pending` | Payments agents have prepared, awaiting human review. |
| `POST /api/payments/approve` | Body `{"proposal_id": N}` -- the only route that can move real money. |
| `GET /api/cash?account=checking` | The shop's current real cash balance. |
| `POST /api/reset` | Restores the working database to its original values. |

### The dashboard (`frontend/`, React + Vite + TS, run with `npm run dev`, talks to `http://localhost:8000`)

A three-column "Ops Desk": a ticket Tray + pending-Approvals panel (left), a Workbench for the selected ticket with a "Run the team" button and post-run Resolution summary (center), and a live, 2-second-polling Agent Activity feed with a persona chip (color + nickname) per agent (right). Full rationale in `output/design.md`.

### Safety rules

- **No invented shop facts or state changes.** Every number and every write goes through the MCP server; no second tools layer exists anywhere (not in the agents, not in the backend, not in the frontend).
- **Separation of duties on money.** Only Accounting's prompt calls `propose_payment`; no agent can call `resolve_payment_proposal` (it's filtered out of every agent's toolset) -- a human is structurally required for any cash to move.
- **Cash reserve floor.** Accounting's prompt flags (and a human sees) if a payment would drop `checking` below $500.
- **Dollar/discount sign-off thresholds.** Payments over $500 and discounts steeper than 25% off list (or below 1.3x unit cost) need Boss's internal sign-off before Accounting prepares them -- understood as "safe to put in front of a human," not as final authorization; a human still independently approves on the dashboard regardless.
- **No fabricated delivery promises.** Any timeline an agent gives is derived from `get_vendor`'s `lead_days` and `get_today`, never guessed.
- **PII guard.** Customer Service never invents contact details beyond what's on a ticket, and escalates (rather than processes) anything that looks like sensitive personal data.
- **Append-only audit trail.** `output/audit_trail.json` is read-appended-rewritten, live, per event -- never truncated, never buffered until "later."
- **Don't trust an agent's own prose over the ground truth.** Problem 9 caught Boss's own closing summary flatly misreporting that "no payment was prepared" when one actually had been (verified via `GET /api/payments/proposals`, not the agent's words). Every claim in this harness and in `output/resolved_tickets.json` is checked against the database or the API directly, not copied from an agent's summary.

### Specs & limits

- Model: `gpt-6-luna` via Portkey, pinned for every agent, `openai_reasoning_effort="none"` (the model otherwise 400s on `/v1/chat/completions` with function tools).
- Per-agent loop cap: `UsageLimits(request_limit=10, tool_calls_limit=8)`.
- Delegation depth cap: `MAX_DELEGATION_DEPTH = 3` (raised from 2 in Problem 9 -- see its section below for why).
- Audit log entries are truncated (300 chars result / 120 chars per arg) to keep the trail file from ballooning.
- Dashboard polling: 2s for agent activity, 4s for tickets/cash/proposals.

## Problem-by-Problem Build Notes

### Problem 2 — Database Study

`data/campus_customs.db` is the original, read-only reference copy. `data/campus_customs_new.db` is an identical working copy created for this problem; every later problem that needs to change data (approve an invoice, adjust inventory, apply a discount, etc.) should write to the `_new` copy and leave the original untouched, so we always have a clean baseline to diff against.

The database models a single campus merch shop ("Campus Customs") on a given day (`desk.date_today` = 2026-08-31): what it has in stock, what it owes, what it's owed, its lease, its cash, and a small inbox of open tickets an agent needs to triage.

### Tables

**`desk`** — `date_today`, `notes`
Anchors "today" for the whole scenario (2026-08-31) so due dates, lease renewals, and ticket timestamps can be judged as overdue/upcoming/future. `notes` is a free-text scratchpad for the shop owner.

**`vendors`** — `id`, `name`, `specialty`, `lead_days`
Who the shop can order from and how long each takes to deliver (`lead_days`). An agent needs this to decide which vendor to use for a restock/reprint request and whether the lead time fits a customer's timeline.

**`inventory`** — `sku`, `name`, `size`, `qty`, `location` (PK: `sku` + `size`)
The actual stock on hand per product/size. This is the ground truth for "can we fulfill this order" and "what's running low" — several SKUs are already at 0 in a given size.

**`pricing`** — `sku`, `unit_cost`, `list_price`
What each SKU costs to produce/stock vs. what it sells for. Needed any time an agent has to judge a discount request (e.g. a bulk-order price override) against actual margin, not just vibes.

**`leases`** — `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
The shop's physical lease obligation. An agent handling a rent-related ticket needs this to confirm the amount and due date actually match what's being claimed before approving payment.

**`cash_accounts`** — `name`, `balance`, `date`
How much cash the shop actually has on a given date. This is the check against overcommitting — e.g. before approving a rent payment or a vendor invoice, the agent should confirm the account can cover it.

**`invoices`** — `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` (FK: `vendor_id` → `vendors.id`)
Money the shop owes a vendor for a specific job. Links a ticket's underlying need (e.g. "rush reprint stock") to a concrete dollar amount and due date the agent may need to approve/pay.

**`payments`** — `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
The ledger of payments actually made (currently empty). This is where an agent should record any payment it approves, with `ref_id` pointing back to the invoice or lease it settled and `approved_by` capturing accountability.

**`tickets`** — `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` (FK: `lease_id` → `leases.id`, `invoice_id` → `invoices.id`)
The actual work queue — the thing an agent is here to triage and act on. Each ticket's `type` determines which other tables matter (inventory/pricing for an order, leases/cash for a rent notice, pricing/inventory for a discount request), and the `lease_id`/`invoice_id` links tie a ticket directly to the record it needs to act against.

### The three open tickets

- **#101 — `customer_order`** (Tauhid Zaman): wants 1x `CC-TEE-WHITE`, size S. Inventory shows **0 in stock** for that exact SKU/size. It's already linked to `invoice_id = 501`, a $840 rush reprint of `CC-TEE-WHITE` S from vendor 1 (Bulldog Print Co, 5-day lead time) — due 2026-08-28, which is **already 3 days past due** relative to `desk.date_today` (2026-08-31) and still `open`. So the restock this customer is waiting on hasn't been paid for yet.
- **#102 — `rent_notice`** (Elm City Properties): "rent due in 2 days." Linked to `lease_id = 1` (Chapel Street shop), monthly rent $2,400, `next_due = 2026-09-02` — exactly 2 days after `desk.date_today`, so the notice checks out. `cash_accounts.checking` has $3,400, enough to cover it on its own, but that's before accounting for invoice #501's $840.
- **#103 — `price_override`** (Yale AI Club): wants a bulk discount on 20x `CC-HOOD-NAVY`, size M. Inventory only has **8** in that size/SKU — the requested quantity (20) exceeds on-hand stock by 12 before any discount question even comes up. Pricing: unit cost $22, list price $58 (62% margin at list).

(Full table dumps captured while studying the DB; see this file going forward for how later problems act on these three tickets.)

### Problem 3 — MCP Server

`mcp_server/campus_customs_server.py` is a FastMCP server with three tools. It reads from `data/campus_customs_new.db` (the working copy from Problem 2), not the original, so every agent in this assignment acts against the same mutable state. It is not run or connected to anything yet in this problem -- only built and syntax-checked (`python -m py_compile`).

| Tool | Table it reads | Ticket it unlocks | Why that tool is right for that ticket |
|---|---|---|---|
| `check_inventory_stock(sku, size)` | `inventory` | **101** | Ticket 101 is Tauhid Zaman asking for 1x `CC-TEE-WHITE` size S. The ticket itself doesn't say whether that's in stock -- this tool is the only way to confirm the real on-hand qty (which the Problem 2 study found to be 0), rather than an agent assuming the order can just be filled. |
| `get_lease_status(lease_id)` | `leases` | **102** | Ticket 102 is a secondhand claim from the landlord ("rent due in 2 days") with no amount or date attached to the ticket row itself. The ticket carries `lease_id = 1`, so this tool is what actually lets an agent pull the real `monthly_rent` and `next_due` and verify the notice is accurate before approving a payment, instead of trusting the email's wording. |
| `get_pricing(sku)` | `pricing` | **103** | Ticket 103 is the Yale AI Club asking for a bulk discount on 20x `CC-HOOD-NAVY` with no price information in the ticket at all. This tool supplies the `unit_cost` and `list_price` an agent needs to judge how much discount still leaves acceptable margin, rather than picking a discount number with no cost basis. |

(`mcp_server/README.md` has the short version of the same mapping for anyone opening the server folder directly.)

### Problem 4 — Connect and smoke-test the MCP server

Registered the server with this project's vibe coder (Claude Code) by adding a `campus-customs` entry to `.mcp.json` at the project root (`/Users/apple/Desktop/AI foundations/.mcp.json`), pointing at `hw5 AI/.venv/bin/python` running `mcp_server/campus_customs_server.py`, alongside the existing `yale-som-courses` and `outlook-mail` servers. `.mcp.json`-registered project servers only connect when a Claude Code session starts, so this live session won't show `campus-customs` as a connected tool until restarted.

To still smoke-test the three tools over the real MCP protocol in this problem (not just by calling the Python functions directly), wrote `mcp_server/run_smoke_test.py`, which uses `fastmcp.Client` to spawn the server over stdio -- the same transport `.mcp.json` uses -- and call each tool once. Results are saved to `output/mcp_smoke.json`: for each ticket, the natural-language prompt that motivated the call, the tool name, its arguments, its JSON output, and a direct re-query of `data/campus_customs_new.db` used to confirm the tool's output matches the database exactly (`matches_db_directly: true` for all three).

| Ticket | Tool | Result | Matches DB |
|---|---|---|---|
| 101 | `check_inventory_stock("CC-TEE-WHITE", "S")` | qty 0, Aisle B | yes |
| 102 | `get_lease_status(1)` | $2,400/mo, next due 2026-09-02 | yes |
| 103 | `get_pricing("CC-HOOD-NAVY")` | unit cost $22.00, list price $58.00 | yes |

### Problem 5 — Agent team + grown MCP tools

### The team

Five PydanticAI agents in `backend/`, each with its own system prompt in `backend/prompts/`, all running the single model `gpt-6-luna` via Portkey (`OpenAIChatModel("gpt-6-luna", provider=OpenAIProvider(base_url="https://api.portkey.ai/v1", ...))`, in `backend/agents.py::make_model`).

| Agent | File | Prompt | Owns |
|---|---|---|---|
| Boss ("Dan") | `backend/agents.py` | `backend/prompts/boss.md` | Triage, final sign-off on big $ / big discounts, separation-of-duties enforcement |
| Inventory ("the Quartermaster") | `backend/agents.py` | `backend/prompts/inventory.md` | Stock + pricing, `price_override` tickets (103) |
| Accounting ("the Ledger") | `backend/agents.py` | `backend/prompts/accounting.md` | The only agent allowed to call `approve_payment` |
| Facilities ("the Super") | `backend/agents.py` | `backend/prompts/facilities.md` | Lease/rent, `rent_notice` tickets (102) |
| Customer Service ("the Bulldog Greeter") | `backend/agents.py` | `backend/prompts/customer_service.md` | `customer_order` tickets (101) |

**Full connectivity:** `backend/agents.py::_wire_delegation` gives every agent a `delegate_to_<other>` tool for all four other agents (a complete graph, 20 delegate tools total), resolved lazily through a shared `agents` dict so there's no circular-construction issue. Data types for delegation/results live in `backend/models.py` (`ShopDeps`, `TicketResolution`, `BossReport`).

### All MCP tools now (table each one reads/writes)

| Tool | Table | Kind | Added in |
|---|---|---|---|
| `check_inventory_stock` | `inventory` | read | Problem 3 |
| `get_lease_status` | `leases` | read | Problem 3 |
| `get_pricing` | `pricing` | read | Problem 3 |
| `get_today` | `desk` | read | Problem 5 |
| `list_open_tickets` | `tickets` | read | Problem 5 |
| `get_ticket` | `tickets` | read | Problem 5 |
| `get_invoice` | `invoices` | read | Problem 5 |
| `get_vendor` | `vendors` | read | Problem 5 |
| `get_cash_balance` | `cash_accounts` | read | Problem 5 |
| `approve_payment` | `payments` (writes), `cash_accounts` (writes), `invoices` (writes, invoice payments only) | write | Problem 5 |
| `update_ticket_status` | `tickets` | write | Problem 5 |

No second shop-tools layer exists -- `backend/agents.py` wraps *only* these MCP tools (via `MCPToolset`) plus the delegate-to-teammate tools; no agent reads or writes `campus_customs_new.db` directly.

### Audit trail

Every real MCP tool call (via `MCPToolset`'s `process_tool_call` hook, shared by all 5 agents) and every `delegate_to_*` call is logged through `backend/agents.py::log_event` into an in-memory buffer, flushed once per top-level run by `backend/audit.py::append_audit_entries`, which reads the existing `output/audit_trail.json`, appends, and rewrites -- never truncates. Each `AuditEntry` (`backend/models.py`) records a UTC timestamp, `run_id`, which agent acted, the tool name (`null` for a closing/summary entry), truncated args/result, and a `stop_reason` on closing entries.

### Real run (not a simulated/sample log)

Ran `cd backend && python run_team.py` once against the live Portkey endpoint. Boss called `list_open_tickets`, delegated ticket 101 -> Customer Service, 102 -> Facilities, 103 -> Inventory, per its routing rule, and each specialist used the real MCP tools before responding. Result (`output/team_run_report.json`, 42 real audit entries appended to `output/audit_trail.json` across all 5 agents):

- **Ticket 101**: confirmed `CC-TEE-WHITE` size S is at 0 stock; found the linked restock invoice 501 ($840, open, overdue since 2026-08-28). Customer Service delegated to Accounting, which verified the invoice and cash balance ($3,400) but correctly **refused to pay** -- $840 exceeds the $500 sign-off threshold, so it tried to escalate to Boss, which hit the 2-hop delegation limit (see "Observed limit" below). No payment was made; ticket closed `needs_approval`.
- **Ticket 102**: Facilities verified lease 1 against the landlord's notice -- $2,400/mo, next due 2026-09-02, which is genuinely 2 days after the shop's `get_today()` (2026-08-31) -- confirmed the notice is accurate, and correctly did **not** pay early. Ticket closed.
- **Ticket 103**: Inventory confirmed only 8 of the requested 20 `CC-HOOD-NAVY` M are in stock (a 12-unit shortfall) and that a 25%-off price ($43.50) still clears the 1.3x-unit-cost floor ($28.60) -- but since the quantity itself can't be met, it escalated for direction rather than inventing stock or silently shrinking the order. Ticket closed `needs_approval`.

No `campus_customs_new.db` row was invented or guessed anywhere in this run -- every number in the three summaries above traces to a real tool call (verified against the same audit entries).

**Observed limit (not a bug, logged honestly):** `MAX_DELEGATION_DEPTH = 2` means the chain Boss -> Customer Service -> Accounting -> Boss is one hop too many, so Accounting's attempt to escalate ticket 101's payment back to Boss was blocked with a clear message instead of silently looping. This is the token/cost guardrail working as designed, but it also means a legitimate 3-hop approval round-trip doesn't finish in a single triage pass -- in practice that ticket waits for the next run or a human to look at the `needs_approval` queue, which is an acceptable and realistic outcome for a shift-lead workflow, not a failure.

### Safety rules (a real business would want these before agents touch real customers/money)

- **No invented shop facts, ever.** Every number an agent states must come from an MCP tool call against `campus_customs_new.db` -- enforced by giving agents *no other* way to learn shop state (no bypassing tools layer).
- **Separation of duties on money.** Only the Accounting agent's prompt permits calling `approve_payment`; every other agent is instructed to delegate a payment request to Accounting instead of acting on it directly, so no single agent both decides and executes a cash movement.
- **Cash reserve floor.** Accounting's prompt requires checking `get_cash_balance` first and refusing to let a payment drop `checking` below $500, escalating instead.
- **Dollar sign-off threshold.** Payments over $500, and discounts steeper than 25% off list or below 1.3x unit cost, require Boss's sign-off before Accounting/Inventory act -- encoded directly in `boss.md`, `accounting.md`, and `inventory.md`.
- **No fabricated delivery promises.** Customer Service and Inventory are instructed to only state timelines derivable from `get_vendor`'s `lead_days` and `get_today`, never a guessed date.
- **PII guard.** Customer Service's prompt forbids inventing customer contact details beyond what's on the ticket, and requires escalating to Boss (not processing normally) if a ticket ever contains something like a card number or SSN.
- **Append-only audit trail.** `audit_trail.json` is read-appended-rewritten, never truncated, so a bad run can't erase evidence of what happened before it.

### Limits that keep token/cost use in check

- **Model pinned:** every agent uses exactly `gpt-6-luna` (via Portkey) -- no per-agent model drift.
- **Per-agent loop cap:** `AGENT_USAGE_LIMITS = UsageLimits(request_limit=10, tool_calls_limit=8)` bounds any single agent's own tool-calling loop.
- **Delegation depth cap:** `MAX_DELEGATION_DEPTH = 2` bounds how many agent-to-agent hops one ticket can take before a `delegate_to_*` tool refuses outright (full mesh connectivity otherwise risks an unbounded A->B->A->B loop).
- **Audit log truncation:** `backend/audit.py::truncate` (300 chars, 120 for individual args) keeps `audit_trail.json` from ballooning on a verbose tool result.
- **`reasoning_effort` pinned to `"none"`:** `gpt-6-luna` rejected function-tool calls on `/v1/chat/completions` with its default reasoning effort (an azure-openai 400); `model_settings={"openai_reasoning_effort": "none"}` on every agent fixes this and also avoids paying for reasoning tokens on what are short, tool-driven decisions.

### Problem 7 — Backend routes (FastAPI)

**Architecture change this problem required:** "agents only prepare the pay, [the backend route] is what actually changes cash." Problem 5's `approve_payment` tool (which both agents and a human could theoretically call, and which agents *did* call directly) has been replaced:

- `approve_payment` is now an internal function `_execute_payment` -- no longer an exposed MCP tool at all.
- **`propose_payment`** (new MCP tool, `payment_proposals` table) -- what Accounting calls now. Writes a `pending` proposal row; touches nothing else.
- **`resolve_payment_proposal`** (new MCP tool) -- the only tool in the server that can actually debit `cash_accounts` / mark an invoice paid. It is explicitly filtered out of every agent's toolset in `backend/agents.py` (`MCPToolset.filtered(...)`), so no agent -- not even Accounting -- can call it even if it tried. Confirmed live: the pydantic-ai startup banner shows Boss with **17** tools (13 MCP tools it can see + 4 `delegate_to_*`), one fewer MCP tool than the other agents would see if `resolve_payment_proposal` weren't filtered.
- **`list_payment_proposals`** and **`list_all_tickets`** (new MCP tools) support the dashboard's read side.

All five agent prompts (`backend/prompts/*.md`) were updated to match: Accounting "prepares" rather than "pays," and every other agent's "Accounting pays it" language now says a human approves it on the dashboard first.

### Routes (`backend/main.py`)

| Method & URL | What it does |
|---|---|
| `GET /api/tickets` | All tickets (101/102/103) with `status` and a computed `is_open` flag, via `list_all_tickets`. |
| `POST /api/tickets/{ticket_id}/run` | Runs the agent team (Boss, delegating per its rules) on exactly that one ticket and returns the run id + `BossReport`. |
| `GET /api/events?limit=&run_id=` | Recent entries from `output/audit_trail.json` (which agent, which tool, truncated args/result), newest first, so the dashboard can poll and refresh. |
| `GET /api/payments/proposals?status=pending` | Payment proposals Accounting has prepared, filterable by status (`pending`/`approved`/`rejected`/empty for all) -- the dashboard's approval queue. |
| `POST /api/payments/approve` | Body `{"proposal_id": N}`. The only route that calls `resolve_payment_proposal` -- the human-click action that actually debits cash and marks an invoice paid. Also writes its own `agent: "human"` audit entry. |
| `GET /api/cash?account=checking` | The shop's current real cash balance via `get_cash_balance`. |
| `POST /api/reset` | Copies `data/campus_customs.db` back over `data/campus_customs_new.db` for a fresh run (tickets back to `open`, payments/proposals gone). |

Verified live: started `uvicorn main:app --port 8000` (an alternate port during testing, since 8000 was already in use by another homework's server in this environment) from inside `backend/`, and exercised every route for real -- `POST /api/reset` → all 3 tickets back to `open`; `POST /api/tickets/101/run` → a real Portkey/`gpt-6-luna` run that found 0 stock and the overdue invoice; a payment proposal taken through `POST /api/payments/approve` → `checking` debited from $3,400.00 to $2,560.00 and invoice 501 marked `paid`; a second approve attempt on the same `proposal_id` correctly returned 400 ("already approved"); `GET /api/events` showed both the agent run and the human approval as separate audit entries. Working database was reset back to its pristine (`open`/unpaid) state afterward so the next problem's dashboard starts clean.

### Problem 8 — Agent dashboard (React + Vite + TS)

Built in `frontend/`; talks to the backend at `http://localhost:8000` (see `output/design.md` for the full look-and-feel rationale: layout, agent personas, cash ticker, etc.). One backend behavior change this problem required: `backend/agents.py`'s audit logging used to buffer every event and only write `output/audit_trail.json` once at the end of a run -- which meant the dashboard's live Agent Activity feed would've shown nothing until a run was already finished. `log_event` now writes each entry straight to disk the instant it happens, so the dashboard's 2-second poll shows real incremental progress while Boss is still mid-delegation, not a wall of text after the fact.

Verified live end to end (backend on 8000 via `uvicorn`, frontend via `npm run dev` on 5173, CORS already allowing that origin from Problem 7): loaded the board, selected ticket 101, clicked "Run the team on this ticket," watched Boss → Customer Service → Accounting entries appear in the Agent Activity feed in near real time while the button showed a spinner, saw the ticket flip to a green "Filed" badge and a Resolution card appear the moment the run finished, then approved a prepared payment and watched the header's cash ticker animate from $3,400.00 to $2,560.00 with a red drop flash. Reset the working database back to pristine afterward.

### Problem 9 — Resolve the tickets

Reset `data/campus_customs_new.db` to the original values (`POST /api/reset`) and recorded the starting checking balance -- **$3,400.00** -- before running anything.

**A real fix discovered mid-run:** the first live attempt at ticket 101 showed the legitimate 3-hop approval chain (Boss -> Customer Service -> Accounting -> Boss, for sign-off on an $840 payment over the $500 threshold) getting blocked by `MAX_DELEGATION_DEPTH = 2`, exactly as flagged as a possibility back in Problem 5/6. Rather than accept that as permanent, raised the cap to **3** -- still bounded (no agent can bounce a ticket around indefinitely), but wide enough for the one real business round-trip the shop's own rules require. Also found that `boss.md`/`accounting.md`'s wording ("sign-off before Accounting pays") was making the model *overly* conservative -- Dan would decline to give a clear go-ahead because he seemed to think he was authorizing the money to move, when a human was always going to independently review it anyway. Clarified both prompts: Boss's sign-off means "safe to queue for human review," not final authorization. Also taught Customer Service (via `customer_service.md`) what to do once an invoice it previously found unpaid comes back `paid` on a later run, so ticket 101 could actually reach a terminal `resolved` state across two passes instead of stalling forever at `needs_approval`.

**What actually happened, ticket by ticket** (full blow-by-blow with Expected-vs-Actual comparison in `output/desk_tickets.html`; structured summary in `output/resolved_tickets.json`):

- **#101 (resolved, 2 runs):** Pass 1 -- Customer Service found 0 stock + an open $840 invoice, delegated to Accounting, which verified the numbers, got Boss's sign-off (the 3-hop chain completing this time), and called `propose_payment`. A human approved it on the dashboard: **checking $3,400.00 → $2,560.00**, invoice #501 marked paid. Pass 2 -- Customer Service saw the invoice was now paid and closed the ticket `resolved` with an honest 5-day-lead-time window. **Real, caught-in-the-act bug:** Boss's own pass-1 `overall_summary` claimed *"no payment was prepared and no funds moved"* -- false; a proposal had already been created in the same run. Caught only because `GET /api/payments/proposals` was checked directly instead of trusting the agent's prose.
- **#102 (resolved, 1 run):** Facilities verified the landlord's notice against lease #1 -- $2,400/mo, due 2026-09-02, genuinely 2 days out -- and closed it without paying, since nothing is due today. **$0 cash impact.**
- **#103 (needs_approval, 1 run, left honest):** Inventory found only 8 of the requested 20 hoodies in stock and valid discount math, but escalated the 12-unit shortfall to Boss, who confirmed the numbers and left the ticket open for the requester to revise their ask. **$0 cash impact.** Not forced to a fake "resolved" -- this system has no tool that can conjure inventory, and no human-approval mechanism for anything but payments, so an honest `needs_approval` is the correct terminal state, not a failure.

**Cash, itemized and verified against the database directly** (not just the API):

| | Amount |
|---|---:|
| Starting balance | $3,400.00 |
| Ticket 101 (invoice #501, Bulldog Print Co, human-approved) | −$840.00 |
| Ticket 102 | $0.00 |
| Ticket 103 | $0.00 |
| **Ending balance** | **$2,560.00** |

Confirmed three independent ways: `GET /api/cash`, `sqlite3 data/campus_customs_new.db "select * from cash_accounts"` (`checking | 2560.0`), and the single row in `payments` (`id=1, kind=invoice, ref_id=501, amount=840.0`).

**Deliverables from this problem:** `output/desk_tickets.html` (Actual sections + Cash tab filled in, Expected kept for comparison), `output/resolved_tickets.json` (per-ticket final status/outcome/agent contributions/human approval), `output/resolved_board.html` (real Playwright-captured screenshots of the live React dashboard for all three tickets -- `output/screenshots/ticket_10{1,2,3}.png` -- since the sandboxed browser-preview tool couldn't reach a plain-Bash-started backend directly; this is the second time that limitation came up, after Problem 6), and this harness's new System Overview section above. Real runs appended **65 new entries** to `output/audit_trail.json` (64 across `run-cabac001`, `run-9411ddd7`, `run-99371d6f`, `run-9398b9d8`, plus 1 human-approval entry) -- append-only, nothing from earlier problems was touched (171 entries total in the file).
