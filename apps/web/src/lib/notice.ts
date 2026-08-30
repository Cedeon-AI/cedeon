import type { NoticeKind, NoticeStatus } from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const KIND_LABEL: Record<NoticeKind, string> = {
  initial_loss_advice: "Initial Loss Advice",
  reinsurer_notification: "Reinsurer Notification of Loss",
};

export function noticeKindLabel(kind: NoticeKind) {
  return KIND_LABEL[kind] ?? kind;
}

export const NOTICE_KINDS: NoticeKind[] = ["initial_loss_advice", "reinsurer_notification"];

const STATUS: Record<NoticeStatus, { label: string; tone: Tone }> = {
  draft: { label: "Draft", tone: "neutral" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  superseded: { label: "Superseded", tone: "neutral" },
};

export function noticeStatus(status: NoticeStatus) {
  return STATUS[status] ?? { label: status, tone: "neutral" as Tone };
}
