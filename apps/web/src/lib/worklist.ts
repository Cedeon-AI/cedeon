import type { WorklistItemOut, WorklistKind } from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const KIND: Record<WorklistKind, { label: string; tone: Tone }> = {
  notice_due: { label: "Notice", tone: "danger" },
  recovery_drift: { label: "Number moved", tone: "warning" },
  recovery_review: { label: "Review", tone: "info" },
  suggested_recovery: { label: "Suggested", tone: "info" },
  packet_approval: { label: "Packet", tone: "info" },
  term_validation: { label: "Terms", tone: "info" },
  recoverable_overdue: { label: "Overdue", tone: "warning" },
};

export function worklistKind(kind: WorklistKind) {
  return KIND[kind] ?? { label: kind, tone: "neutral" as Tone };
}

/** The short right-aligned status on a row: a countdown if there's a deadline,
 * otherwise how long it's been waiting. */
export function worklistClock(item: WorklistItemOut): { text: string; overdue: boolean } | null {
  if (item.due_in_days !== null && item.due_in_days !== undefined) {
    if (item.due_in_days < 0) {
      return { text: `${Math.abs(item.due_in_days)}d overdue`, overdue: true };
    }
    if (item.due_in_days === 0) return { text: "due today", overdue: true };
    return { text: `${item.due_in_days}d left`, overdue: item.due_in_days <= 3 };
  }
  if (item.age_days && item.age_days > 0) {
    return { text: `${item.age_days}d waiting`, overdue: false };
  }
  return null;
}
