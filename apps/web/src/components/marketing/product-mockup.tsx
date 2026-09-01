import { AlarmClock, ArrowRight, FileWarning, Hourglass, Scale, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "danger" | "warning" | "calc";

const TONE: Record<Tone, string> = {
  danger: "bg-danger/10 text-danger",
  warning: "bg-warning/15 text-warning",
  calc: "bg-calculation/10 text-calculation",
};

type Row = {
  icon: ReactNode;
  tone: Tone;
  title: string;
  detail: string;
  amount?: string;
  clock?: string;
  overdue?: boolean;
};

const GROUPS: { label: string; count: number; rows: Row[] }[] = [
  {
    label: "Obligations",
    count: 1,
    rows: [
      {
        icon: <AlarmClock />,
        tone: "warning",
        title: "Notice due",
        detail: "Hurricane Béatrice — first advice to reinsurers",
        clock: "in 4 days",
        overdue: false,
      },
    ],
  },
  {
    label: "Recovery",
    count: 2,
    rows: [
      {
        icon: <TrendingUp />,
        tone: "warning",
        title: "Number moved",
        detail: "Property Cat XOL — $8.70M → $10.20M after a late claim",
        amount: "$10.20M",
      },
      {
        icon: <Hourglass />,
        tone: "danger",
        title: "Overdue 32 days",
        detail: "Reinsurer B — bill issued, no payment. Chase.",
        amount: "$2.61M",
        clock: "32d overdue",
        overdue: true,
      },
    ],
  },
  {
    label: "Contract",
    count: 1,
    rows: [
      {
        icon: <FileWarning />,
        tone: "warning",
        title: "Treaty updated",
        detail: "Property Cat XOL v3 endorsed — 1 recovery to recheck",
      },
    ],
  },
  {
    label: "Exceptions",
    count: 1,
    rows: [
      {
        icon: <Scale />,
        tone: "danger",
        title: "Doesn't reconcile",
        detail: "Reinsurer C — billed $1.80M vs agreed $1.74M",
        amount: "$60,000",
      },
    ],
  },
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
        <span className="ml-2 font-mono text-[11px] text-muted-foreground">cedeon.app / home</span>
      </div>

      <div className="p-5">
        <div className="flex items-baseline justify-between">
          <p className="text-[13px] font-semibold tracking-tight">Needs you</p>
          <span className="text-[11px] text-muted-foreground">5 open</span>
        </div>

        <div className="mt-3 space-y-3">
          {GROUPS.map((group) => (
            <div key={group.label} className="space-y-1.5">
              <div className="flex items-center gap-2 px-1">
                <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
                  {group.label}
                </span>
                <span className="text-[10px] text-muted-foreground/50">{group.count}</span>
              </div>
              <div className="overflow-hidden rounded-lg border border-border/70">
                {group.rows.map((row, i) => (
                  <div
                    key={row.title}
                    className={cn(
                      "flex items-center gap-3 bg-background/60 px-3 py-2.5",
                      i > 0 && "border-t border-border/70",
                    )}
                  >
                    <span
                      className={cn(
                        "flex size-7 shrink-0 items-center justify-center rounded-md [&_svg]:size-3.5",
                        TONE[row.tone],
                      )}
                    >
                      {row.icon}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12.5px] font-medium text-foreground">
                        {row.title}
                      </span>
                      <span className="block truncate text-[11px] text-muted-foreground">
                        {row.detail}
                      </span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-0.5 text-right">
                      {row.amount ? (
                        <span className="font-mono text-[11px] tabular-nums text-foreground">
                          {row.amount}
                        </span>
                      ) : null}
                      {row.clock ? (
                        <span
                          className={cn(
                            "text-[10px]",
                            row.overdue ? "font-medium text-danger" : "text-muted-foreground",
                          )}
                        >
                          {row.clock}
                        </span>
                      ) : null}
                    </span>
                    <ArrowRight className="size-3.5 shrink-0 text-muted-foreground/40" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
