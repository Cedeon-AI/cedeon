import type { NoticeObligationOut, NoticeTrigger } from "@/lib/api";

export const TRIGGER_LABEL: Record<NoticeTrigger, string> = {
  loss_occurrence: "the date of loss",
  knowledge_of_loss: "the date of knowledge",
  claim_advice: "first claim advice",
};

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

/** The countdown chip for a notice deadline. */
export function deadlineChip(ob: NoticeObligationOut): { text: string; tone: Tone } {
  if (ob.satisfied) {
    return {
      text: ob.satisfied_on ? `Notice filed ${ob.satisfied_on}` : "Notice filed",
      tone: "success",
    };
  }
  if (ob.deadline === null || ob.days_until === null || ob.days_until === undefined) {
    return { text: "No deadline set", tone: "neutral" };
  }
  const d = ob.days_until;
  if (d < 0) return { text: `Notice ${Math.abs(d)}d overdue`, tone: "danger" };
  if (d === 0) return { text: "Notice due today", tone: "danger" };
  if (d <= 7) return { text: `Notice due in ${d}d`, tone: "warning" };
  return { text: `Notice due ${ob.deadline}`, tone: "info" };
}
