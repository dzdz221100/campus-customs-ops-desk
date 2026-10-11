# Campus Customs Ops Desk — Design Notes

## The concept

The brief asked for something "people would want to sit at," not a homework form. The frame I picked: this isn't a generic admin panel, it's **a literal desk** — the kind a shift lead like Dan actually works at, with an in-tray of paper tickets, a line of staff he can hand things to, a ledger drawer for money that needs a signature, and a cash box on the counter. Every visual decision below serves that frame rather than decorating it.

## Layout — three columns, like a trading floor for a five-person shop

- **Left: The Tray + Needs Your Approval.** Tickets are the thing you triage first, so they're leftmost and always visible, not buried behind a click. Pending payment approvals sit directly underneath — on a real desk, the thing waiting for your signature lives next to your inbox, not on a separate screen.
- **Center: The Workbench.** Whatever ticket is selected gets the big, uncontested middle of the screen: its facts, the one button that matters ("Run the team on this ticket"), and — once a run finishes — the Resolution writeup. This is deliberately the only place you *act*; the side columns are for *watching and approving*.
- **Right: Agent Activity.** A standing, always-on live feed, independent of which ticket is selected. The brief says to show what each agent is doing *while* the ticket runs — rather than build a special "running" view that appears and disappears, I made the activity feed a permanent fixture, like a police-scanner / ops-radio panel that's always chattering. It's reassuring in the same way a real ops floor's status board is: things are visibly happening even when you're not the one clicking.

Below ~1080px the three columns stack (tray → workbench → feed) so it still works on a laptop half-screen, but the three-column arrangement is the real design — it's what makes this feel like a desk with several things going on at once, not a single wizard flow.

## How the agents read differently

Five different people work this desk, and the UI treats them like five different people, not five rows in a table:

- Each agent keeps its **prompt-file nickname** next to its formal role — "Boss · Dan, Shift Lead", "Customer Service · the Bulldog Greeter" — so the personality we wrote into `backend/prompts/` actually surfaces where a human reads it, instead of staying backend trivia.
- Each agent gets a **fixed color and a round initial-chip** (Boss navy, Inventory brass/amber, Accounting green, Facilities brown, Customer Service rose, and a neutral charcoal "Y" for *you*, the human). Once you've watched one run, you stop reading names and start pattern-matching on color — exactly how a real dispatch board works.
- Delegations are phrased in plain language ("Customer Service → *handed this to accounting*") instead of showing the raw `delegate_to_accounting` tool name, so the feed reads like a conversation between coworkers, not a function-call log — while the real tool name and arguments are still there underneath, in monospace, for anyone who wants the receipts.
- The feed is **live, not a reload**: `backend/agents.py`'s audit logging was changed from "buffer everything, write once at the end of a run" to writing each event straight to `output/audit_trail.json` the instant it happens. The dashboard polls every 2 seconds, so you watch Boss hand a ticket to Customer Service, then Customer Service check stock, then escalate to Accounting, in close to real time — not as a wall of text that appears all at once when the run finally finishes 15 seconds later.

## Resolved tickets and cash

- A ticket moves from an amber **"On the desk"** badge to a green **"Filed"** badge the moment its backend status stops being `open` — regardless of the exact resulting status string (`resolved`, `needs_approval`, `closed`, whatever the agents actually wrote). "Filed" is honest about what happened (the team worked it and it's off the open pile) while a small secondary pill still shows the literal status underneath, so "needs approval" doesn't quietly disappear into a false "all good" green checkmark.
- The **Resolution** card (center column) is written to be read by a shop owner, not a developer: Boss's `overall_summary` up top in a highlighted strip, then each ticket's own summary in plain prose, with the MCP tools actually used shown as small pill tags underneath — so "I trust this" is backed by "here's exactly what it looked up," one click away, not hidden.
- The **cash ticker** in the header is deliberately the one piece of chrome that never moves position — it's always top-right, like a real till display. When an approval goes through and the balance drops, the number **flashes red and gives a small downward nudge** before settling (a rise, e.g. from a future refund, flashes green and nudges up). It's a tiny animation, but it's the one moment in the whole app where real money visibly moved, and it earns a little drama for that reason alone.

## Smaller creative decisions, and why

- **Paper-and-ledger palette** (parchment background, Yale blue + brass trim, hand-cut "perforated edge" dots on the left of each ticket card) instead of a generic SaaS blue-and-white theme — because this is a merch shop with a shift lead named Dan, not a fintech dashboard, and the visual language should say so.
- **Fraunces** (a warm display serif) for headings and the wordmark, **Inter** for UI text, **JetBrains Mono** for anything that's a real number or a real tool/field name (ticket IDs, dollar figures, tool calls). Mixing a serif "voice" with a mono "receipt" font is what makes the page feel like a real business document rather than a component library demo.
- **"Reset day"** button in the header — a thin, deliberately low-key ghost button (it's an admin/demo action, not a primary one) that calls the same `/api/reset` route from Problem 7, so a grader (or you) can run the same three tickets again from a clean morning without touching the terminal.
- **Toast confirmations** ("Approved — $840.00 sent.", "Ticket #101 — Dan's team finished the pass.") instead of relying on the page just quietly updating — a human approving real money, even fake-real money, deserves a clear "yes, that happened," not a silent re-render.
- **Honest failure state**: if the backend at `localhost:8000` isn't running, the page doesn't just show empty panels — a banner says exactly that and gives the exact command to fix it. A desk that silently shows nothing when the phone line is down isn't a desk you'd trust.

## What I didn't build (on purpose)

No ticket detail beyond what `/api/tickets` actually returns (no sku/size/qty shown on the Workbench) — the backend's `TicketSummary` deliberately doesn't carry those fields, and hardcoding them into the frontend from memory of the Problem 2 study would mean the UI could silently drift from what the backend actually says. Real shop facts only ever come from a real route, same rule that's held since Problem 3's MCP server.
