import type { Ticket } from "../types";

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

export function TicketTray({
  tickets,
  selectedId,
  onSelect,
}: {
  tickets: Ticket[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>The Tray</h2>
        <span className="count-pill">{tickets.length} tickets</span>
      </div>
      <div className="panel-body">
        <div className="ticket-tray">
          {tickets.map((t) => (
            <div
              key={t.id}
              className={`ticket-card${selectedId === t.id ? " selected" : ""}`}
              onClick={() => onSelect(t.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onSelect(t.id)}
            >
              <div className="ticket-id">
                Ticket #{t.id} · {TYPE_LABEL[t.type] ?? t.type}
              </div>
              <div className="ticket-subject">{t.subject}</div>
              <div className="ticket-requester">{t.requester}</div>
              <span className={`badge ${t.is_open ? "open" : "resolved"}`}>{t.is_open ? "On the desk" : "Filed"}</span>
              {!t.is_open && <span className="badge sub" style={{ marginLeft: 6 }}>{t.status}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
