import type { ApplicabilityAssessment, FindingKind, RecoveryCandidateStatus } from "@/lib/api";

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

const APPLICABILITY: Record<ApplicabilityAssessment, { label: string; tone: Tone }> = {
  supported: { label: "Treaty responds", tone: "success" },
  partially_supported: { label: "Partially responds", tone: "warning" },
  unclear: { label: "Unclear", tone: "warning" },
  contradicted: { label: "Treaty may not respond", tone: "danger" },
};

export function applicability(value: ApplicabilityAssessment | null) {
  return value ? (APPLICABILITY[value] ?? { label: value, tone: "neutral" as Tone }) : null;
}

const FINDING_KIND: Record<FindingKind, { label: string; tone: Tone }> = {
  relevant_clause: { label: "Relevant clause", tone: "info" },
  supporting_evidence: { label: "Supporting evidence", tone: "success" },
  missing_information: { label: "Missing information", tone: "warning" },
  ambiguity: { label: "Ambiguity", tone: "warning" },
  inconsistency: { label: "Inconsistency", tone: "danger" },
  notice_obligation: { label: "Notice obligation", tone: "info" },
  next_step: { label: "Next step", tone: "neutral" },
};

export function findingKind(value: FindingKind) {
  return FINDING_KIND[value] ?? { label: value, tone: "neutral" as Tone };
}
