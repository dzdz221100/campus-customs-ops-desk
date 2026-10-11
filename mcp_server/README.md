# Campus Customs MCP server

A FastMCP server that gives every agent in this assignment a shared view of
the Campus Customs shop -- both reading shop facts and, as of Problem 5,
acting on them. It talks to the working copy of the database,
`data/campus_customs_new.db` (the original `data/campus_customs.db` is left
untouched as a reference). This is the *only* layer that touches the
database -- every agent reads and writes through these tools, never the
database file directly, so nothing is ever invented or guessed.

## Tools

Read-only (Problem 2/3 tickets):

- **`check_inventory_stock(sku, size)`** -- reads `inventory`. Real on-hand qty/location for a SKU/size (ticket 101).
- **`get_lease_status(lease_id)`** -- reads `leases`. A lease's real landlord, rent, and next due date (ticket 102).
- **`get_pricing(sku)`** -- reads `pricing`. Unit cost and list price for a SKU (ticket 103).

Read-only (Problem 5 additions, so agents can actually work a ticket end to end):

- **`get_today()`** -- reads `desk`. The shop's "today," so due dates can be judged overdue/upcoming instead of guessed.
- **`list_open_tickets()`** -- reads `tickets`. The whole open work queue, for triage.
- **`get_ticket(ticket_id)`** -- reads `tickets`. One ticket's full detail (requester, sku/size/qty, lease_id/invoice_id, notes).
- **`get_invoice(invoice_id)`** -- reads `invoices`. A vendor invoice's amount, due date, and status.
- **`get_vendor(vendor_id)`** -- reads `vendors`. A vendor's specialty and `lead_days`.
- **`get_cash_balance(account)`** -- reads `cash_accounts`. A cash account's real balance.

Write (Problem 5 additions -- the only way any agent changes shop state):

- **`update_ticket_status(ticket_id, status, resolution_notes)`** -- writes `tickets`. Appends `resolution_notes` to the ticket's existing notes and sets its status; never overwrites the original request text.

Read-only (Problem 7 addition):

- **`list_all_tickets()`** -- reads `tickets`, any status. Backs the dashboard's ticket board (open *and* resolved), unlike `list_open_tickets`.

Payments, prepare/approve split (Problem 7 -- "agents only prepare the pay, a human approval route is what actually changes cash"):

- **`propose_payment(ticket_id, kind, ref_id, amount, account, reason, proposed_by)`** -- writes a `pending` row to `payment_proposals`. This is what Accounting calls; it never touches `cash_accounts` or `payments`.
- **`list_payment_proposals(status="pending")`** -- reads `payment_proposals`, filterable by status.
- **`resolve_payment_proposal(proposal_id, resolved_by)`** -- the *only* tool that can actually debit `cash_accounts`, insert into `payments`, and mark an `invoices` row `"paid"`. It is deliberately excluded from every agent's toolset (`backend/agents.py`) -- only the FastAPI backend's `/api/payments/approve` route (a human clicking Approve) ever calls it.

## Run

```
python campus_customs_server.py          # stdio
python campus_customs_server.py --http   # http://127.0.0.1:8010/mcp
```
