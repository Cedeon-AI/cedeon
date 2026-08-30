import { Check } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const TRUST = [
  { label: "Fact", cls: "text-fact bg-fact/10 border-fact/30" },
  { label: "Calculation", cls: "text-calculation bg-calculation/10 border-calculation/30" },
  { label: "AI interpretation", cls: "text-ai bg-ai/10 border-ai/30" },
  { label: "Human decision", cls: "text-human bg-human/10 border-human/30" },
];

export function AuthCard({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* brand panel */}
      <div className="relative hidden overflow-hidden border-r border-border/60 bg-muted/40 lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="pointer-events-none absolute inset-0 hero-glow opacity-70" />
        <div className="pointer-events-none absolute inset-0 dot-backdrop" />
        <Link href="/" className="relative">
          <Logo />
        </Link>
        <div className="relative max-w-md">
          <p className="text-2xl font-semibold leading-snug tracking-tight">
            From validated contract to evidence-backed recovery — every figure traced to a source.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {TRUST.map((t) => (
              <span
                key={t.label}
                className={`rounded-full border px-2.5 py-1 text-xs font-medium ${t.cls}`}
              >
                {t.label}
              </span>
            ))}
          </div>
        </div>
        <ul className="relative space-y-2 text-sm text-muted-foreground">
          {[
            "LLMs interpret. Deterministic code calculates. Humans approve.",
            "Exact decimal arithmetic — never binary floating point.",
            "An append-only audit trail of every decision.",
          ].map((line) => (
            <li key={line} className="flex items-center gap-2">
              <Check className="size-4 shrink-0 text-human" />
              {line}
            </li>
          ))}
        </ul>
      </div>

      {/* form panel */}
      <div className="relative flex flex-col items-center justify-center px-6 py-12">
        <div className="absolute right-6 top-6">
          <ThemeToggle />
        </div>
        <div className="w-full max-w-sm">
          <Link href="/" className="mb-8 inline-block lg:hidden">
            <Logo />
          </Link>
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm sm:p-7">
            <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
            <div className="mt-6">{children}</div>
          </div>
          {footer ? (
            <p className="mt-4 text-center text-sm text-muted-foreground">{footer}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
