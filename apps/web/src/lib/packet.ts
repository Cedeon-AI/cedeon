import type { PacketStatementClass, PacketVersionStatus } from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const CLASS_META: Record<PacketStatementClass, { label: string; color: string; tone: Tone }> = {
  fact: { label: "Fact", color: "border-primary bg-primary/5", tone: "info" },
  calculation: {
    label: "Calculation",
    color: "border-calculation bg-calculation/5",
    tone: "info",
  },
  ai_interpretation: {
    label: "AI interpretation",
    color: "border-warning bg-warning/10",
    tone: "warning",
  },
  human_decision: {
    label: "Human decision",
    color: "border-human bg-human/5",
    tone: "success",
  },
};

export function statementClass(value: PacketStatementClass) {
  return CLASS_META[value] ?? { label: value, color: "border-border", tone: "neutral" as Tone };
}

const VERSION_STATUS: Record<PacketVersionStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  superseded: { label: "Superseded", tone: "neutral" },
};

export function packetVersionStatus(value: PacketVersionStatus) {
  return VERSION_STATUS[value] ?? { label: value, tone: "neutral" as Tone };
}
