import { useState } from "react";
import type { PaymentProposal } from "../types";

function formatUsd(value: number): string {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
}

export function ApprovalsPanel({
  proposals,
  onApprove,
}: {
  proposals: PaymentProposal[];
  onApprove: (proposalId: number) => Promise<void>;
}) {
  const [approvingId, setApprovingId] = useState<number | null>(null);

  async function handleApprove(id: number) {
    setApprovingId(id);
    try {
      await onApprove(id);
    } finally {
      setApprovingId(null);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Needs Your Approval</h2>
        <span className="count-pill">{proposals.length} pending</span>
      </div>
      <div className="panel-body">
        {proposals.length === 0 ? (
          <p className="empty-note">Nothing waiting on you right now — the team only prepares payments; you decide if they go out.</p>
        ) : (
          proposals.map((p) => (
            <div className="proposal" key={p.id}>
              <div className="proposal-amount">{formatUsd(p.amount)}</div>
              <div className="proposal-meta">
                {p.kind} #{p.ref_id} · prepared by {p.proposed_by}
                <br />
                {p.reason}
              </div>
              <button className="approve-btn" disabled={approvingId === p.id} onClick={() => handleApprove(p.id)}>
                {approvingId === p.id ? "Approving…" : "Approve payment"}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
