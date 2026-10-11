import type { AuditEvent } from "../types";
import { personaFor } from "../agentPersonas";

function timeOnly(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}

function describe(event: AuditEvent): { headline: string; detail: string } {
  if (!event.tool_name) {
    return {
      headline: event.stop_reason ? `finished (${event.stop_reason})` : "started working",
      detail: event.result,
    };
  }
  if (event.tool_name.startsWith("delegate_to_")) {
    const target = event.tool_name.replace("delegate_to_", "").replace(/_/g, " ");
    return { headline: `handed this to ${target}`, detail: event.result };
  }
  return { headline: `called ${event.tool_name}()`, detail: event.result };
}

export function AgentFeed({ events }: { events: AuditEvent[] }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Agent Activity</h2>
        <span className="count-pill" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="feed-live-dot" /> live
        </span>
      </div>
      <div className="panel-body">
        <div className="feed-list">
          {events.length === 0 && <p className="empty-note">No activity yet — run a ticket to watch the team work.</p>}
          {events.map((event, i) => {
            const persona = personaFor(event.agent);
            const { headline, detail } = describe(event);
            return (
              <div className="feed-item" key={`${event.timestamp}-${i}`}>
                <div className="avatar-chip" style={{ background: persona.color }}>
                  {persona.initials}
                </div>
                <div className="feed-item-body">
                  <div className="feed-item-top">
                    <span className="feed-agent-name">{persona.label}</span>
                    <span className="feed-agent-nickname">{persona.nickname}</span>
                    <span className="feed-timestamp">{timeOnly(event.timestamp)}</span>
                  </div>
                  <div className="feed-tool-name">{headline}</div>
                  <div className="feed-result">{detail}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
