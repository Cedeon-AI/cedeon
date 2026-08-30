import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Reveal } from "@/components/marketing/reveal";
import { Button } from "@/components/ui/button";
import { Container, Section, SectionHeading } from "@/components/ui/layout";

export const metadata = {
  title: "About",
  description:
    "Cedeon is an independent reinsurance financial-intelligence layer. Recovery identification is the first wedge.",
};

const BELIEFS = [
  {
    title: "The contract is the source of truth",
    body: "A reinsurance recovery is an argument about what a treaty says and what a loss did. Both halves have to be legible, cited and checkable — not buried in a spreadsheet or a model's confidence.",
  },
  {
    title: "Language models interpret; they do not decide",
    body: "LLMs are very good at reading contracts and drafting prose, and unfit to be the source of truth for a number. We draw that line hard and keep it visible in the product.",
  },
  {
    title: "A financial finding needs a paper trail",
    body: "Every figure Cedeon surfaces can be traced to a validated term, a committed loss and a versioned calculation — and every human decision along the way is on the record.",
  },
  {
    title: "Sit beside the system of record, not on top of it",
    body: "Cedeon reads from claims, reinsurance administration, accounting, broker and document systems. It is a financial-intelligence layer, not a replacement for any of them.",
  },
];

export default function AboutPage() {
  return (
    <div>
      <div className="relative overflow-hidden border-b border-border/60">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-96 hero-glow" />
        <Container className="relative py-16 sm:py-20">
          <Reveal>
            <SectionHeading
              eyebrow="About"
              title="An independent reinsurance financial-intelligence layer"
              description="Cedeon sits above and beside existing claims, reinsurance administration, accounting, broker and document systems. Recovery identification is the initial wedge — the place where a validated contract, clean loss data and deterministic math turn into money a cedent is owed."
            />
          </Reveal>
        </Container>
      </div>

      <Section>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="What we believe"
              title="Four principles the product is built on"
            />
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {BELIEFS.map((b, i) => (
              <Reveal key={b.title} delay={0.04 * i}>
                <div className="h-full rounded-xl border border-border bg-card p-6 shadow-sm">
                  <h2 className="font-semibold tracking-tight">{b.title}</h2>
                  <p className="mt-2 text-sm text-muted-foreground">{b.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      <Section tint="muted" bordered>
        <Container className="grid gap-8 md:grid-cols-3">
          {[
            { k: "Focus", v: "Ceded reinsurance recovery" },
            { k: "Model", v: "LLMs interpret · code calculates · humans approve" },
            { k: "Stage", v: "Early — access by request" },
          ].map((s) => (
            <div key={s.k}>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {s.k}
              </p>
              <p className="mt-1 text-lg font-semibold tracking-tight">{s.v}</p>
            </div>
          ))}
        </Container>
      </Section>

      <Section className="py-14">
        <Container className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-2xl font-semibold tracking-tight">
            Work with us on the first cohort
          </h2>
          <Button asChild size="lg">
            <Link href="/login">
              Request access <ArrowRight className="size-4" />
            </Link>
          </Button>
        </Container>
      </Section>
    </div>
  );
}
