import type { AuditEvent, BossReport, CashBalance, PaymentProposal, RunTicketResponse, Ticket } from "./types";

const BASE_URL = "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}) as Record<string, unknown>);
    const detail = typeof body === "object" && body && "detail" in body ? String(body.detail) : undefined;
    throw new Error(detail ?? `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  getTickets: () => request<Ticket[]>("/api/tickets"),
  runTicket: (ticketId: number) => request<RunTicketResponse>(`/api/tickets/${ticketId}/run`, { method: "POST" }),
  getEvents: (limit = 40, runId?: string) =>
    request<AuditEvent[]>(`/api/events?limit=${limit}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`),
  getProposals: (status = "pending") => request<PaymentProposal[]>(`/api/payments/proposals?status=${status}`),
  approvePayment: (proposalId: number) =>
    request<Record<string, unknown>>("/api/payments/approve", {
      method: "POST",
      body: JSON.stringify({ proposal_id: proposalId }),
    }),
  getCash: (account = "checking") => request<CashBalance>(`/api/cash?account=${account}`),
  reset: () => request<Record<string, unknown>>("/api/reset", { method: "POST" }),
};

export type { BossReport };
