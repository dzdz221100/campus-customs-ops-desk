# Campus Customs — Agent Team + Ops Desk

A PydanticAI agent team (Boss, Inventory, Accounting, Facilities, Customer Service) that triages a small campus shop's support tickets over a shared MCP server, plus a FastAPI backend and a React dashboard to run it and approve payments.

Full write-up: [`output/harness.md`](output/harness.md) (system overview: tables, MCP tools, agents, API routes, safety rules) and [`output/design.md`](output/design.md) (dashboard design rationale). The ticket-by-ticket plan vs. actual results and reflection are in [`output/desk_tickets.html`](output/desk_tickets.html) (double-click to open).

## Setup

Requires Python 3.11+ and Node 18+.

```bash
# 1. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Your own Portkey key (never commit the real .env)
cp .env.example .env
# edit .env and fill in PORTKEY_API_KEY

# 3. Frontend dependencies
cd frontend && npm install && cd ..
```

Both `data/campus_customs.db` (original, read-only reference) and `data/campus_customs_new.db` (working copy the app actually reads/writes) are included, so the app runs immediately with no setup. `POST /api/reset` restores the working copy to the original at any time.

## Run

```bash
# Terminal 1 — backend (from backend/)
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend (from frontend/)
cd frontend
npm run dev
```

Open the printed `http://localhost:5173` URL — that's the dashboard. It talks to the backend at `http://localhost:8000`.

## Repo layout

- `mcp_server/` — the FastMCP server; the only layer that touches `data/campus_customs_new.db`.
- `backend/` — the 5 PydanticAI agents (`agents.py`, prompts in `prompts/`) and the FastAPI app (`main.py`).
- `frontend/` — the React + Vite + TS dashboard.
- `data/` — the original and working SQLite databases.
- `output/` — all write-ups, run evidence, and deliverables (`harness.md`, `design.md`, `desk_tickets.html`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`, screenshots).
- `AI_prompts.md` — the prompt log for the assignment.
