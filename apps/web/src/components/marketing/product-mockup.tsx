import { ArrowRight, Check, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

type Kind = "fact" | "calculation" | "ai" | "human";

const KIND_META: Record<Kind, { label: string; bar: string; chip: string }> = {
  fact: { label: "Fact", bar: "border-l-fact", chip: "bg-fact/10 text-fact" },
  calculation: {
    label: "Calculation",
    bar: "border-l-calculation",
    chip: "bg-calculation/10 text-calculation",
  },
  ai: { label: "AI interpretation", bar: "border-l-ai", chip: "bg-ai/10 text-ai" },
  human: { label: "Human decision", bar: "border-l-human", chip: "bg-human/10 text-human" },
};

const STATEMENTS: { kind: Kind; text: string; meta: string }[] = [
  {
    kind: "fact",
    text: "Layer: USD 20,000,000 excess of USD 50,000,000, 3 reinsurers.",
    meta: "Property Cat XOL 2024 · p.4 §3.1 — validated",
  },
  {
    kind: "fact",
    text: "Event incurred: USD 58,700,000 across 10 underlying claims.",
    meta: "Loss import LI-2481 · committed",
  },
  {
    kind: "calculation",
    text: "Layer recovery: USD 8,700,000.00",
    meta: "XOL engine v1.0.0 · min(58.7M − 50M, 20M)",
  },
  {
    kind: "ai",
    text: "Treaty responds. Hours clause satisfied; no exclusion applies.",
    meta: "Investigator · 4 citations · read-only",
  },
];

const ALLOCATION = [
  { name: "Reinsurer A", pct: 50, amount: "4,350,000.00" },
  { name: "Reinsurer B", pct: 30, amount: "2,610,000.00" },
  { name: "Reinsurer C", pct: 20, amount: "1,740,000.00" },
];

export function ProductMockup({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-border-strong bg-card shadow-lg",
        className,
      )}
    >
      {/* window chrome */}
      <div className="flex items-center gap-2 border-b border-border/70 bg-muted/50 px-4 py-2.5">
        <div className="flex gap-1.5">
          <span className="size-2.5 rounded-full bg-border-strong" />
          <span className="size-2.5 rounded-full bg-border-strong" />
          <span className="size-2.5 rounded-full bg-border-strong" />
        </div>
        <span className="ml-2 font-mono text-[11px] text-muted-foreground">
          cedeon.app / recovery-candidates / rc_2f9c
        </span>
      </div>

      <div className="grid gap-0 md:grid-cols-[1.55fr_1fr]">
        {/* left: classified statements */}
        <div className="border-b border-border/70 p-5 md:border-b-0 md:border-r">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[13px] font-semibold tracking-tight">Recovery packet</p>
              <p className="text-xs text-muted-foreground">Hurricane Béatrice · draft v3</p>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-[11px] font-medium text-warning">
              Pending human review
            </span>
          </div>

          <div className="mt-4 space-y-2">
            {STATEMENTS.map((s) => {
              const m = KIND_META[s.kind];
              return (
                <div
                  key={s.text}
                  className={cn(
                    "rounded-r-md border border-l-2 border-border/70 bg-background/60 px-3 py-2",
                    m.bar,
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        m.chip,
                      )}
                    >
                      {m.label}
                    </span>
                  </div>
                  <p className="mt-1 text-[13px] leading-snug text-foreground">{s.text}</p>
                  <p className="mt-0.5 font-mono text-[10.5px] text-muted-foreground">{s.meta}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* right: figure + allocation */}
        <div className="flex flex-col gap-4 p-5">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Layer recovery
            </p>
            <p className="mt-1 font-mono text-2xl font-semibold tracking-tight text-calculation">
              $8,700,000.00
            </p>
            <p className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
              <ShieldCheck className="size-3" /> Deterministic · unit-tested engine
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Per-reinsurer share
            </p>
            {ALLOCATION.map((a) => (
              <div key={a.name} className="space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">{a.name}</span>
                  <span className="font-mono text-foreground">${a.amount}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-calculation/70"
                    style={{ width: `${a.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-auto flex items-center gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-md bg-human/10 px-2.5 py-1.5 text-[11px] font-medium text-human"
            >
              <Check className="size-3" /> Confirm
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground"
            >
              Draft notice <ArrowRight className="size-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
