import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AuditEvent, BossReport, PaymentProposal, Ticket } from "./types";
import { CashTicker } from "./components/CashTicker";
import { TicketTray } from "./components/TicketTray";
import { ApprovalsPanel } from "./components/ApprovalsPanel";
import { Workbench } from "./components/Workbench";
import { AgentFeed } from "./components/AgentFeed";
import { Toast } from "./components/Toast";

const EVENTS_POLL_MS = 2000;
const SLOW_POLL_MS = 4000;

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [cash, setCash] = useState<number | null>(null);
  const [proposals, setProposals] = useState<PaymentProposal[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [reportByTicket, setReportByTicket] = useState<Record<number, BossReport>>({});
  const [runError, setRunError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((message: string) => {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  }, []);

  const refreshTickets = useCallback(async () => {
    try {
      const data = await api.getTickets();
      setTickets(data);
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  }, []);

  const refreshCash = useCallback(async () => {
    try {
      const data = await api.getCash();
      setCash(data.balance);
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  }, []);

  const refreshProposals = useCallback(async () => {
    try {
      const data = await api.getProposals("pending");
      setProposals(data);
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  }, []);

  const refreshEvents = useCallback(async () => {
    try {
      const data = await api.getEvents(40);
      setEvents(data);
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  }, []);

  useEffect(() => {
    refreshTickets();
    refreshCash();
    refreshProposals();
    refreshEvents();
  }, [refreshTickets, refreshCash, refreshProposals, refreshEvents]);

  useEffect(() => {
    const fast = setInterval(refreshEvents, EVENTS_POLL_MS);
    const slow = setInterval(() => {
      refreshTickets();
      refreshCash();
      refreshProposals();
    }, SLOW_POLL_MS);
    return () => {
      clearInterval(fast);
      clearInterval(slow);
    };
  }, [refreshEvents, refreshTickets, refreshCash, refreshProposals]);

  const selectedTicket = tickets.find((t) => t.id === selectedId) ?? null;

  async function handleRun(ticketId: number) {
    setRunning(true);
    setRunError(null);
    try {
      const res = await api.runTicket(ticketId);
      setReportByTicket((prev) => ({ ...prev, [ticketId]: res.report }));
      showToast(`Ticket #${ticketId} — Dan's team finished the pass.`);
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "The run failed.");
    } finally {
      setRunning(false);
      refreshTickets();
      refreshCash();
      refreshProposals();
      refreshEvents();
    }
  }

  async function handleApprove(proposalId: number) {
    try {
      const result = await api.approvePayment(proposalId);
      const amount = typeof result.amount === "number" ? result.amount : undefined;
      showToast(amount ? `Approved — $${amount.toFixed(2)} sent.` : "Payment approved.");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Could not approve that payment.");
    } finally {
      refreshProposals();
      refreshCash();
      refreshEvents();
      refreshTickets();
    }
  }

  async function handleReset() {
    try {
      await api.reset();
      showToast("Fresh day — database reset to the original values.");
    } catch {
      showToast("Could not reset the database.");
    } finally {
      setReportByTicket({});
      refreshTickets();
      refreshCash();
      refreshProposals();
      refreshEvents();
    }
  }

  return (
    <div className="desk">
      <header className="desk-header">
        <div className="brand">
          <span className="mark">🐾 Campus Customs</span>
          <span className="tagline">Ops Desk</span>
        </div>
        <div className="header-right">
          <CashTicker balance={cash} />
          <button className="reset-btn" onClick={handleReset}>
            Reset day
          </button>
        </div>
      </header>

      {!backendOnline && (
        <div style={{ background: "var(--red-bg)", color: "var(--red)", textAlign: "center", padding: "8px", fontSize: "0.85rem" }}>
          Can't reach the backend at http://localhost:8000 — start it with <code>uvicorn main:app --reload --port 8000</code> from{" "}
          <code>backend/</code>.
        </div>
      )}

      <div className="desk-body">
        <div className="column">
          <TicketTray tickets={tickets} selectedId={selectedId} onSelect={setSelectedId} />
          <ApprovalsPanel proposals={proposals} onApprove={handleApprove} />
        </div>

        <div className="column">
          <Workbench
            ticket={selectedTicket}
            running={running}
            onRun={() => selectedTicket && handleRun(selectedTicket.id)}
            report={selectedTicket ? (reportByTicket[selectedTicket.id] ?? null) : null}
            error={runError}
          />
        </div>

        <div className="column">
          <AgentFeed events={events} />
        </div>
      </div>

      {toast && <Toast message={toast} />}
    </div>
  );
}
