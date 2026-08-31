import type { RecoverableStatus } from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const STATUS: Record<RecoverableStatus, { label: string; tone: Tone }> = {
  pending: { label: "Pending", tone: "neutral" },
  notified: { label: "Notified", tone: "info" },
  agreed: { label: "Agreed", tone: "info" },
  billed: { label: "Billed", tone: "warning" },
  collected: { label: "Collected", tone: "success" },
  disputed: { label: "Disputed", tone: "danger" },
  written_off: { label: "Written off", tone: "neutral" },
};

export function recoverableStatus(status: RecoverableStatus) {
  return STATUS[status] ?? { label: status, tone: "neutral" as Tone };
}

/** The forward flow — for the "advance" button. */
const FLOW: RecoverableStatus[] = ["pending", "notified", "agreed", "billed", "collected"];

export function nextStatus(current: RecoverableStatus): RecoverableStatus | null {
  const i = FLOW.indexOf(current);
  return i >= 0 ? (FLOW[i + 1] ?? null) : null;
}

export const AGING_LABEL: Record<string, string> = {
  current: "Current",
  "1_30": "1–30 days",
  "31_60": "31–60 days",
  "61_90": "61–90 days",
  "90_plus": "90+ days",
};

export const RECOVERABLE_STATUSES: RecoverableStatus[] = [
  "pending",
  "notified",
  "agreed",
  "billed",
  "collected",
  "disputed",
  "written_off",
];
