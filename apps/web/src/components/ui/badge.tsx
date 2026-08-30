import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const tones: Record<Tone, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  info: "border-calculation/30 bg-calculation/5 text-calculation",
  success: "border-human/30 bg-human/5 text-human",
  warning: "border-warning/40 bg-warning/10 text-warning",
  danger: "border-danger/30 bg-danger/5 text-danger",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}
