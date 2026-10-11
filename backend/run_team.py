"""CLI entry point: Boss triages every currently-open Campus Customs ticket.

Run (from inside backend/):  python run_team.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from team_runner import run_triage_all_open

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
REPORT_PATH = OUTPUT_DIR / "team_run_report.json"


async def main() -> None:
    _run_id, report = await run_triage_all_open()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report.model_dump(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
