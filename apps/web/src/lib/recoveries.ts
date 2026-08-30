import type { RecoveryCandidateStatus } from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const STATUS: Record<RecoveryCandidateStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  needs_review: { label: "Needs review", tone: "warning" },
  in_review: { label: "In review", tone: "info" },
  confirmed: { label: "Confirmed", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  notice_drafted: { label: "Notice drafted", tone: "info" },
};

export function candidateStatus(status: RecoveryCandidateStatus) {
  return STATUS[status] ?? { label: status, tone: "neutral" as Tone };
}

export const CANDIDATE_FILTERS: { label: string; value: RecoveryCandidateStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Needs review", value: "needs_review" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Rejected", value: "rejected" },
];
