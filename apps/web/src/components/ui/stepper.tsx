import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type Step = { key: string; label: string };

export function Stepper({
  steps,
  current,
}: {
  steps: readonly Step[];
  /** index of the active step; steps before it render as complete */
  current: number;
}) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-3">
      {steps.map((step, i) => {
        const state = i < current ? "done" : i === current ? "active" : "todo";
        return (
          <li key={step.key} className="flex items-center gap-2">
            <span
              className={cn(
                "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium tabular-nums transition",
                state === "done" && "border-human bg-human text-white",
                state === "active" && "border-primary bg-primary/10 text-primary",
                state === "todo" && "border-border text-muted-foreground",
              )}
            >
              {state === "done" ? <Check className="size-3.5" /> : i + 1}
            </span>
            <span
              className={cn(
                "text-sm",
                state === "active" ? "font-medium text-foreground" : "text-muted-foreground",
              )}
            >
              {step.label}
            </span>
            {i < steps.length - 1 ? (
              <span className="mx-1 h-px w-6 bg-border sm:w-10" aria-hidden="true" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
