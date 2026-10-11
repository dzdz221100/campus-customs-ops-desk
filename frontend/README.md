# Campus Customs Ops Desk

React + Vite + TypeScript dashboard for the Campus Customs agent team. Talks to the FastAPI backend at `http://localhost:8000` (see `../backend`).

See `../output/design.md` for the design rationale.

## Run

```
npm install
npm run dev
```

Opens on `http://localhost:5173`. The backend must already be running (`uvicorn main:app --reload --port 8000` from `../backend`) for the board to load any data.
