export type AgentId = "boss" | "inventory" | "accounting" | "facilities" | "customer_service" | "human";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: string;
  is_open: boolean;
}

export interface TicketResolution {
  ticket_id: number;
  status_recommendation: "resolved" | "needs_approval" | "escalated";
  summary: string;
  tools_used: string[];
}

export interface BossReport {
  tickets_handled: TicketResolution[];
  overall_summary: string;
}

export interface RunTicketResponse {
  run_id: string;
  report: BossReport;
}

export interface AuditEvent {
  timestamp: string;
  run_id: string;
  agent: string;
  tool_name: string | null;
  args: Record<string, unknown>;
  result: string;
  stop_reason: string | null;
}

export interface PaymentProposal {
  id: number;
  ticket_id: number;
  kind: string;
  ref_id: number;
  amount: number;
  account: string;
  reason: string;
  proposed_by: string;
  status: string;
  created_at: string;
  resolved_by: string | null;
  resolved_at: string | null;
}

export interface CashBalance {
  found: boolean;
  name: string;
  balance: number;
  date: string;
}
