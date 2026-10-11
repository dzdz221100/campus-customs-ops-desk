import type { BossReport, Ticket } from "../types";

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

const STATUS_LABEL: Record<string, string> = {
  resolved: "Resolved",
  needs_approval: "Needs approval",
  escalated: "Escalated",
};

export function Workbench({
  ticket,
  running,
  onRun,
  report,
  error,
}: {
  ticket: Ticket | null;
  running: boolean;
  onRun: () => void;
  report: BossReport | null;
  error: string | null;
}) {
  if (!ticket) {
    return (
      <div className="panel">
        <div className="workbench-empty">Pick a ticket from the tray to start the team on it.</div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>The Workbench</h2>
        <span className={`badge ${ticket.is_open ? "open" : "resolved"}`}>{ticket.is_open ? "On the desk" : "Filed"}</span>
      </div>
      <div className="panel-body">
        <div className="fact-grid">
          <div className="fact">
            <div className="fact-label">Ticket</div>
            <div className="fact-value">#{ticket.id}</div>
          </div>
          <div className="fact">
            <div className="fact-label">Type</div>
            <div className="fact-value">{TYPE_LABEL[ticket.type] ?? ticket.type}</div>
          </div>
          <div className="fact">
            <div className="fact-label">Requester</div>
            <div className="fact-value">{ticket.requester}</div>
          </div>
          <div className="fact">
            <div className="fact-label">Status</div>
            <div className="fact-value">{ticket.status}</div>
          </div>
        </div>
        <p style={{ fontSize: "0.92rem", color: "var(--ink-soft)", margin: "0 0 16px" }}>{ticket.subject}</p>

        <button className="run-btn" onClick={onRun} disabled={running}>
          {running && <span className="spinner" />}
          {running ? "Boss is working the ticket…" : "Run the team on this ticket"}
        </button>

        {error && (
          <p style={{ color: "var(--red)", fontSize: "0.85rem", marginTop: 10 }}>{error}</p>
        )}

        {report && (
          <div className="resolution-card">
            <h3>Resolution</h3>
            <div className="overall-summary">{report.overall_summary}</div>
            {report.tickets_handled.map((r) => (
              <div className="per-ticket-resolution" key={r.ticket_id}>
                <div className="resolution-status-row">
                  <span className="badge sub">{STATUS_LABEL[r.status_recommendation] ?? r.status_recommendation}</span>
                </div>
                <div style={{ fontSize: "0.88rem", lineHeight: 1.55 }}>{r.summary}</div>
                {r.tools_used.length > 0 && (
                  <div className="tool-pill-row">
                    {r.tools_used.map((tool) => (
                      <span className="tool-pill" key={tool}>
                        {tool}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
