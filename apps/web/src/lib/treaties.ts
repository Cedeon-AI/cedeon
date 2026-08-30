import type { TreatyVersionStatus } from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const STATUS: Record<TreatyVersionStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  parsing: { label: "Parsing document", tone: "info" },
  extracting: { label: "Extracting terms", tone: "info" },
  needs_validation: { label: "Needs validation", tone: "warning" },
  validated: { label: "Validated", tone: "success" },
  active: { label: "Active", tone: "success" },
  superseded: { label: "Superseded", tone: "neutral" },
};

export function versionStatus(status: TreatyVersionStatus) {
  return STATUS[status] ?? { label: status, tone: "neutral" as Tone };
}

export function isBusy(status: TreatyVersionStatus) {
  return status === "parsing" || status === "extracting";
}

const CANDIDATE_TONE: Record<string, Tone> = {
  extracted: "info",
  not_found: "neutral",
  ambiguous: "warning",
  conflicting: "danger",
};

export function candidateTone(status: string): Tone {
  return CANDIDATE_TONE[status] ?? "neutral";
}

const TERM_LABELS: Record<string, string> = {
  attachment: "Attachment (retention)",
  limit: "Limit",
  currency: "Currency",
  effective_date: "Effective date",
  expiration_date: "Expiration date",
  notice_provision: "Notice provision",
  covered_perils: "Covered perils",
  covered_business: "Covered business",
  territory: "Territory",
  event_definition: "Event definition",
  hours_clause: "Hours clause",
  reinstatements: "Reinstatements",
  exclusions: "Exclusions",
  participation: "Participation",
};

export function termLabel(key: string) {
  return TERM_LABELS[key] ?? key.replace(/_/g, " ");
}

export function formatShare(share: string) {
  return `${(Number(share) * 100).toFixed(2)}%`;
}
