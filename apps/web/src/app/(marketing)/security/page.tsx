import { FileText, GitBranch, Landmark, Lock, ScrollText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Reveal } from "@/components/marketing/reveal";
import { Button } from "@/components/ui/button";
import { Container, Section, SectionHeading } from "@/components/ui/layout";

export const metadata = {
  title: "Security",
  description:
    "How Cedeon keeps financial figures defensible: provenance, deterministic math, human sign-off, tenant isolation, and no outbound send.",
};

const PILLARS: { icon: ReactNode; title: string; body: string }[] = [
  {
    icon: <Landmark />,
    title: "Exact-decimal money, everywhere",
    body: "Every monetary value is Decimal in application code and NUMERIC in PostgreSQL. Binary floating point is never used for money, and currency is always explicit. The calculation engine is a pure, versioned module that may import only the Money value object.",
  },
  {
    icon: <FileText />,
    title: "Provenance before a term is executable",
    body: "An extracted treaty term carries its document, page, clause, supporting span, a confidence score and the model that proposed it. A person validates each term before it can feed a calculation; nothing becomes an executable layer without that step.",
  },
  {
    icon: <ScrollText />,
    title: "Deterministic calculation, no LLM in the loop",
    body: "Attachment, exhaustion, layer recovery and per-reinsurer allocation are computed by unit-tested code with a pinned engine version. The AI investigator is handed the deterministic figure as a fact and cannot overwrite it — at most it flags that it computed something different.",
  },
  {
    icon: <ShieldCheck />,
    title: "Uploaded documents are untrusted input",
    body: "Document text is treated as data, never as instruction. Production agents run with a fixed tool allowlist, no shell and no arbitrary web access. Prompt-injection attempts in a treaty cannot escalate into actions.",
  },
  {
    icon: <Lock />,
    title: "Tenant isolation and data handling",
    body: "Tenancy is enforced server-side on every request — an organization identifier in a request body is never trusted. Treaty text, claim data and personal data are kept out of ordinary logs and default debugging traces.",
  },
  {
    icon: <GitBranch />,
    title: "No outbound send",
    body: "The notice drafter produces a draft from approved facts and stops. There is deliberately no send action anywhere in the product; a notice's terminal state is 'approved'. Transmission to reinsurers or brokers stays in your systems.",
  },
];

const RECORD = [
  "Every agent run, with its model, prompt version, token usage and cost.",
  "Every tool call the investigator made, in order, with arguments and a result summary.",
  "Every human decision — confirm, edit, reject, request information — attributed and timestamped.",
  "An append-only audit trail; recovery calculations and packet versions are immutable once written.",
];

export default function SecurityPage() {
  return (
    <div>
      <div className="relative overflow-hidden border-b border-border/60">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-96 hero-glow" />
        <Container className="relative py-16 sm:py-20">
          <Reveal>
            <SectionHeading
              eyebrow="Trust & security"
              title="Auditable by construction"
              description="Cedeon's guarantees are structural. They come from where the boundaries are drawn between what a language model may do and what only deterministic code and accountable people may do."
            />
          </Reveal>
        </Container>
      </div>

      <Section>
        <Container className="grid gap-4 sm:grid-cols-2">
          {PILLARS.map((p, i) => (
            <Reveal key={p.title} delay={0.04 * i}>
              <div className="h-full rounded-xl border border-border bg-card p-6 shadow-sm">
                <span className="inline-flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary [&_svg]:size-5">
                  {p.icon}
                </span>
                <h2 className="mt-4 font-semibold tracking-tight">{p.title}</h2>
                <p className="mt-2 text-sm text-muted-foreground">{p.body}</p>
              </div>
            </Reveal>
          ))}
        </Container>
      </Section>

      <Section tint="muted" bordered>
        <Container className="grid gap-10 md:grid-cols-[1fr_1.1fr] md:items-start">
          <Reveal>
            <SectionHeading
              eyebrow="What is on the record"
              title="If it happened, it is written down"
            />
          </Reveal>
          <Reveal delay={0.1}>
            <ul className="space-y-3">
              {RECORD.map((item) => (
                <li
                  key={item}
                  className="flex gap-3 rounded-lg border border-border bg-card p-4 text-sm shadow-xs"
                >
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-human" />
                  <span className="text-muted-foreground">{item}</span>
                </li>
              ))}
            </ul>
          </Reveal>
        </Container>
      </Section>

      <Section className="py-14">
        <Container className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            Questions about deployment, data residency or contractual terms?
          </p>
          <Button asChild>
            <Link href="/login">Request access</Link>
          </Button>
        </Container>
      </Section>
    </div>
  );
}
