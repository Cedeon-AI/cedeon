import type { AgentRunStatus, AgentType } from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const AGENT_LABEL: Record<AgentType, string> = {
  treaty_extraction: "Treaty extraction",
  recovery_investigator: "Recovery investigator",
  notice_drafter: "Notice drafter",
};

export function agentLabel(t: AgentType | string) {
  return AGENT_LABEL[t as AgentType] ?? t;
}

const RUN_STATUS: Record<AgentRunStatus, Tone> = {
  running: "info",
  succeeded: "success",
  failed: "danger",
};

export function runStatusTone(s: AgentRunStatus): Tone {
  return RUN_STATUS[s] ?? "neutral";
}

const ACTOR_TONE: Record<string, Tone> = {
  user: "info",
  agent: "warning",
  system: "neutral",
};

export function actorTone(actor: string): Tone {
  return ACTOR_TONE[actor] ?? "neutral";
}

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 4,
});

export function usd(amount: string | number) {
  return USD.format(typeof amount === "string" ? Number(amount) : amount);
}
