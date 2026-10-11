import type { AgentId } from "./types";

export interface AgentPersona {
  label: string;
  nickname: string;
  initials: string;
  color: string;
  glyph: string;
}

export const AGENT_PERSONAS: Record<AgentId, AgentPersona> = {
  boss: { label: "Boss", nickname: "Dan, Shift Lead", initials: "D", color: "#00356b", glyph: "compass" },
  inventory: { label: "Inventory", nickname: "the Quartermaster", initials: "Q", color: "#a3691b", glyph: "box" },
  accounting: { label: "Accounting", nickname: "the Ledger", initials: "L", color: "#2e7d4f", glyph: "ledger" },
  facilities: { label: "Facilities", nickname: "the Super", initials: "S", color: "#6b4a2f", glyph: "wrench" },
  customer_service: { label: "Customer Service", nickname: "the Bulldog Greeter", initials: "B", color: "#b23a6b", glyph: "paw" },
  human: { label: "You", nickname: "Dashboard operator", initials: "Y", color: "#3a3a3a", glyph: "hand" },
};

export function personaFor(agent: string): AgentPersona {
  return AGENT_PERSONAS[agent as AgentId] ?? { label: agent, nickname: agent, initials: agent.slice(0, 1).toUpperCase(), color: "#555", glyph: "dot" };
}
