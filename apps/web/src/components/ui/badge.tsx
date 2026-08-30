import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger"
  | "fact"
  | "calculation"
  | "ai"
  | "human"
  | "outline";

const tones: Record<Tone, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  info: "border-calculation/30 bg-calculation/10 text-calculation",
  success: "border-human/30 bg-human/10 text-human",
  warning: "border-warning/40 bg-warning/15 text-warning",
  danger: "border-danger/30 bg-danger/10 text-danger",
  fact: "border-fact/30 bg-fact/10 text-fact",
  calculation: "border-calculation/30 bg-calculation/10 text-calculation",
  ai: "border-ai/30 bg-ai/10 text-ai",
  human: "border-human/30 bg-human/10 text-human",
  outline: "border-border-strong bg-transparent text-muted-foreground",
};

export function Badge({
  tone = "neutral",
  className,
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium [&_svg]:size-3",
        tones[tone],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
