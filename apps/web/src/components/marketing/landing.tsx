import {
  AlarmClock,
  ArrowRight,
  Boxes,
  Check,
  ClipboardCheck,
  Clock,
  Coins,
  FileSearch,
  FileText,
  FileWarning,
  GitBranch,
  Landmark,
  Layers,
  LineChart,
  Minus,
  RefreshCw,
  Scale,
  ScrollText,
  ShieldCheck,
  Sigma,
  Sparkles,
  TrendingUp,
  UserCheck,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { ProductMockup } from "@/components/marketing/product-mockup";
import { Reveal } from "@/components/marketing/reveal";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Container, Eyebrow, Section, SectionHeading } from "@/components/ui/layout";
import { cn } from "@/lib/utils";

type Kind = "fact" | "calculation" | "ai" | "human";

const KIND_LABEL: Record<Kind, string> = {
  fact: "Fact",
  calculation: "Calculation",
  ai: "AI interpretation",
  human: "Human decision",
};

const KIND_CLASS: Record<Kind, string> = {
  fact: "text-fact border-fact/30 bg-fact/5",
  calculation: "text-calculation border-calculation/30 bg-calculation/5",
  ai: "text-ai border-ai/30 bg-ai/5",
  human: "text-human border-human/30 bg-human/5",
};

const SYSTEMS = [
  "Claims systems",
  "Reinsurance administration",
  "Accounting / GL",
  "Broker statements",
  "Document stores",
];

// The categories the queue groups by today — the four ways work lands on the desk.
const CATEGORIES: { name: string; body: string; icon: ReactNode; tone: string }[] = [
  {
    name: "Recovery",
    body: "A treaty responds to a loss and no one has opened the recovery — or a confirmed figure moved and needs a fresh look.",
    icon: <Sigma />,
    tone: "text-calculation bg-calculation/10",
  },
  {
    name: "Obligations",
    body: "A claim has triggered a notice you owe. Cedeon computes the deadline from the validated provision and counts it down.",
    icon: <AlarmClock />,
    tone: "text-warning bg-warning/15",
  },
  {
    name: "Contract",
    body: "An endorsement changed the wording. The terms carry forward for re-validation and every recovery on the old version is flagged.",
    icon: <FileWarning />,
    tone: "text-warning bg-warning/15",
  },
  {
    name: "Exceptions",
    body: "What Cedeon calculated and what was agreed, billed or collected don't line up — surfaced with the gap and the evidence.",
    icon: <Scale />,
    tone: "text-danger bg-danger/10",
  },
];

// Continuous checks that put an item on the queue — everything built since the first release.
const WATCHES: { title: string; body: string; icon: ReactNode }[] = [
  {
    title: "Notice deadlines",
    body: "From a validated, structured notice provision, Cedeon derives the reference date, computes the deadline in calendar or business days, and counts it down on the queue. The model never sets a date.",
    icon: <AlarmClock />,
  },
  {
    title: "Recalculation & drift",
    body: "Every committed loss re-runs the affected recoveries. A figure that moves without a person is drift: the confirmed recovery reverts to review and the before → after is shown.",
    icon: <TrendingUp />,
  },
  {
    title: "Suggested recoveries",
    body: "Cedeon screens each validated treaty layer against each loss event — currency, the treaty window, gross above the attachment — and proposes opening a recovery where none exists.",
    icon: <Sparkles />,
  },
  {
    title: "Aged recoverables",
    body: "Each reinsurer's leg is tracked notified → agreed → billed → collected. Aging is derived, and a deterministic next action — chase an acknowledgement, issue the bill, chase payment — sits on every open leg.",
    icon: <Wallet />,
  },
  {
    title: "Contract changes",
    body: "An endorsement opens a new treaty version — terms, layers and panels copied forward — and re-runs extraction against the endorsement so the validator sees a term-by-term diff of what changed. Recoveries on the superseded version are flagged.",
    icon: <GitBranch />,
  },
  {
    title: "Reinstatement premium",
    body: "When a loss erodes a layer, Cedeon computes the reinstatement premium due — from the deposit premium, the rate per reinstatement, the flat or pro-rata-as-to-time basis, and how much of the limit earlier losses in the period already used. Deterministic; the analyst validates the terms.",
    icon: <RefreshCw />,
  },
  {
    title: "Hours-clause occurrence view",
    body: "For a catastrophe loss, Cedeon proposes how the claims group into occurrence windows under the treaty's hours clause. It proposes — the cedent chooses when each window starts.",
    icon: <Clock />,
  },
  {
    title: "Internal reconciliation",
    body: "Cedeon's own expected figure against the agreed, billed and collected amounts on the record — agreed below expected, billed without agreement, collected short.",
    icon: <Scale />,
  },
  {
    title: "Statement reconciliation",
    body: "Enter the figures a reinsurer stated — agreed, paid — and Cedeon reconciles each line against what it holds: their agreed below yours or below the calculated figure, paid short or over.",
    icon: <FileWarning />,
  },
];

const PIPELINE: { title: string; body: string; kind: Kind; icon: ReactNode }[] = [
  {
    title: "Treaty document",
    body: "Upload the PDF or DOCX. Cedeon parses it with page, section and clause structure intact.",
    kind: "fact",
    icon: <FileText />,
  },
  {
    title: "Validated terms",
    body: "AI proposes each term with an exact citation and a confidence score. A person confirms before anything becomes executable.",
    kind: "human",
    icon: <UserCheck />,
  },
  {
    title: "Deterministic recovery",
    body: "A versioned, unit-tested engine computes attachment, layer recovery and each reinsurer's share — on every layer a loss pierces. No LLM touches the math.",
    kind: "calculation",
    icon: <Sigma />,
  },
  {
    title: "AI investigation",
    body: "A bounded, read-only agent checks applicability, relevant clauses, missing evidence and notice obligations — every finding cited.",
    kind: "ai",
    icon: <FileSearch />,
  },
  {
    title: "Recovery packet",
    body: "An evidence-backed artifact that keeps fact, calculation, AI interpretation and human decision visibly separate.",
    kind: "fact",
    icon: <ScrollText />,
  },
  {
    title: "Review, notice & collection",
    body: "Confirm, edit or reject. Draft the loss advice. Then track the recoverable to cash. Every decision is attributed and audited.",
    kind: "human",
    icon: <Check />,
  },
];

const CAPABILITIES: { title: string; body: string; icon: ReactNode }[] = [
  {
    title: "Contract understanding with provenance",
    body: "Every extracted term links to its document, page, clause and supporting span, with a confidence score and the model that proposed it.",
    icon: <FileText />,
  },
  {
    title: "Deterministic recovery engine",
    body: "Attachment, exhaustion, layer recovery, per-reinsurer allocation and reinstatement premium are versioned, unit-tested code. Exact decimal arithmetic — never floating point.",
    icon: <Sigma />,
  },
  {
    title: "Multi-layer programmes",
    body: "A treaty version is a stack of excess-of-loss layers, each with its own reinsurer panel. A loss opens a deterministic recovery on every layer it reaches; the siblings group as one programme.",
    icon: <Layers />,
  },
  {
    title: "Bounded AI investigator",
    body: "A read-only agent with a fixed tool allowlist and usage limits. It explains why a treaty responds — it never emits a rival number.",
    icon: <FileSearch />,
  },
  {
    title: "Evidence-backed recovery packet",
    body: "An immutable, versioned artifact. Fact, calculation, AI interpretation and human decision stay visibly separate on every line.",
    icon: <ScrollText />,
  },
  {
    title: "Notice drafter — no auto-send",
    body: "Drafts an initial loss advice from approved facts only. It stops at draft. A person sends it, from their own system.",
    icon: <GitBranch />,
  },
];

type LayerState = "built" | "foundation" | "started" | "later";
const LAYER_META: Record<LayerState, { label: string; class: string }> = {
  built: { label: "Built", class: "text-human border-human/30 bg-human/10" },
  foundation: {
    label: "Foundation built",
    class: "text-calculation border-calculation/30 bg-calculation/10",
  },
  started: { label: "Started", class: "text-warning border-warning/40 bg-warning/15" },
  later: { label: "Later", class: "text-muted-foreground border-border bg-muted" },
};

const LAYERS: { name: string; question: string; state: LayerState }[] = [
  {
    name: "Contract intelligence",
    question: "What does this treaty mean, as executable terms?",
    state: "built",
  },
  {
    name: "Recovery intelligence",
    question: "What does the contract mean for these losses?",
    state: "built",
  },
  {
    name: "Obligation intelligence",
    question: "What has a claim triggered that I owe — a notice, a reinstatement premium?",
    state: "built",
  },
  {
    name: "Exception / reconciliation",
    question:
      "What doesn't line up — expected vs agreed vs billed vs collected, and vs what the reinsurer says?",
    state: "built",
  },
  {
    name: "Portfolio / renewal",
    question: "What patterns should I act on across the book?",
    state: "later",
  },
];

const AUDIENCES: { role: string; body: string; icon: ReactNode }[] = [
  {
    role: "Head of ceded reinsurance",
    body: "Open the desk on one ranked list — recoveries to review, notices coming due, treaty changes, what doesn't reconcile — with the clauses to back each one.",
    icon: <ScrollText />,
  },
  {
    role: "Reinsurance accounting",
    body: "Turn a validated contract and committed losses into a recoverable you can book, then track it notified → agreed → billed → collected.",
    icon: <Coins />,
  },
  {
    role: "Finance & capital teams",
    body: "A defensible view of expected recoveries and their aging, separate from the claims system's estimates.",
    icon: <LineChart />,
  },
  {
    role: "Claims & recovery leads",
    body: "Catch notice obligations and missing evidence early, and see the moment a recovery figure moves.",
    icon: <ClipboardCheck />,
  },
];

const NOT_LIST: string[] = [
  "A system of record. Cedeon reads from your systems; it does not replace claims, reinsurance administration or the general ledger.",
  "An autonomous agent. Nothing is sent, filed or booked without a person deciding.",
  "A generic AI assistant. It does one thing — ceded reinsurance, contract to cash — with provenance.",
  "A model that guesses at money. Every figure is deterministic code over validated inputs.",
  "A pricing, placement or cat model. It works the recoveries your existing programme creates.",
];

type Cell = boolean | "partial" | string;
const COMPARE: { row: string; cedeon: Cell; manual: Cell; assistant: Cell }[] = [
  {
    row: "One ranked queue of what needs a person today",
    cedeon: true,
    manual: false,
    assistant: false,
  },
  {
    row: "Exact treaty citations on every term",
    cedeon: true,
    manual: "partial",
    assistant: false,
  },
  { row: "Deterministic, unit-tested math", cedeon: true, manual: "partial", assistant: false },
  { row: "No financial figure authored by an LLM", cedeon: true, manual: true, assistant: false },
  {
    row: "Recovery figures re-checked on every new loss",
    cedeon: true,
    manual: false,
    assistant: false,
  },
  {
    row: "Notice deadlines & reinstatement premium computed",
    cedeon: true,
    manual: "partial",
    assistant: false,
  },
  {
    row: "Recoverables tracked to cash, with aging",
    cedeon: true,
    manual: "partial",
    assistant: false,
  },
  {
    row: "Your figures — and a reinsurer's — reconciled",
    cedeon: true,
    manual: "partial",
    assistant: false,
  },
  { row: "Immutable audit trail of every decision", cedeon: true, manual: false, assistant: false },
];

const FAQ: { q: string; a: string }[] = [
  {
    q: "Is this a recovery calculator?",
    a: "Recovery is module one, but the product you open is the ceded-reinsurance desk's queue — what needs you today. It watches: notices coming due, reinstatement premium owed, recovery figures that moved, treaty endorsements, recoverables aging past their date, and where your figures — or a reinsurer's — don't reconcile. The deterministic recovery calculation sits underneath that.",
  },
  {
    q: "Does an LLM ever calculate a financial figure?",
    a: "No. Extraction and notice drafting use language models; every financial calculation — layer recovery, per-reinsurer allocation, reinstatement premium, reconciliation — runs in versioned, unit-tested code using exact decimal arithmetic. The investigator agent is handed the deterministic figure as a fact and cannot overwrite it.",
  },
  {
    q: "What treaty structures does the engine support today?",
    a: "Per-occurrence excess of loss — $X limit excess of $Y attachment — a stack of such layers in one programme, each with its own reinsurer panel, and reinstatement premium terms on a layer. Quota share, aggregate covers and index clauses are out of scope for now; the data model is built so they can be added without a rewrite.",
  },
  {
    q: "How does the hours clause work?",
    a: "It is assistive. Cedeon groups a catastrophe loss's claims into rolling occurrence windows under the treaty's hours clause and proposes the grouping. The cedent chooses when each window starts — Cedeon never auto-decides an occurrence or splits an event.",
  },
  {
    q: "What does a person actually have to approve?",
    a: "Material interpretations. A human validates each extracted term before it can feed a calculation, enters the operational terms (the layer stack, panels, reinstatement rates) directly, reviews the recovery packet before it is final, and approves any notice draft. Every action is attributed and audited.",
  },
  {
    q: "How does reconciliation work?",
    a: "Two checks, both deterministic. Internal: Cedeon's own expected figure for a leg against the agreed / billed / collected amounts on the record. External: a batch of figures a reinsurer stated — agreed, paid — matched to your recoverables and checked line by line. Both surface the material gaps with the evidence; a file importer for real bordereau formats is the next step.",
  },
  {
    q: "Does Cedeon send notices to reinsurers or brokers?",
    a: "No. The notice drafter produces a draft from approved facts and stops there. There is deliberately no send action anywhere in the product. Sending stays in your systems, with your people.",
  },
  {
    q: "How does Cedeon fit with our existing claims and reinsurance systems?",
    a: "It sits beside them as a financial-intelligence layer. Cedeon reads treaties and loss data, surfaces what needs attention, and hands back evidence-backed work. It does not replace your system of record.",
  },
  {
    q: "Is Cedeon generally available?",
    a: "It is an early product. Access is granted to a small number of ceded reinsurance and finance teams at a time — request access and we will be in touch.",
  },
];

function Mark({ value }: { value: Cell }) {
  if (value === true) return <Check className="mx-auto size-4 text-human" aria-label="Yes" />;
  if (value === false)
    return <Minus className="mx-auto size-4 text-muted-foreground/50" aria-label="No" />;
  if (value === "partial")
    return <span className="mx-auto block text-xs font-medium text-warning">Partial</span>;
  return <span className="text-xs text-muted-foreground">{value}</span>;
}

export function Landing() {
  return (
    <div className="relative">
      {/* ---------------------------------------------------------------- Hero */}
      <div className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-160 hero-glow" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-140 grid-backdrop" />
        <Container className="relative pt-16 pb-16 sm:pt-24">
          <div className="mx-auto max-w-3xl text-center">
            <Eyebrow>
              <span className="size-1.5 rounded-full bg-accent" />
              The intelligence system for ceded reinsurance
            </Eyebrow>
            <h1 className="mt-6 text-balance text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
              Reinsurance intelligence from{" "}
              <span className="text-gradient">contract to recovery</span>.
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg text-muted-foreground">
              Cedeon turns your treaties into executable terms, watches your losses against them,
              and opens the ceded-reinsurance desk on one ranked list — recoveries to review,
              notices coming due, contract changes, what doesn't reconcile — each backed by a
              citation, a deterministic calculation and a human decision.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Button asChild size="lg">
                <Link href="/login">
                  Request access <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="secondary">
                <Link href="/login">Sign in</Link>
              </Button>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Built for ceded reinsurance and finance teams · Every figure traced to a source
            </p>
          </div>

          <Reveal delay={0.15} className="mt-14 sm:mt-16">
            <ProductMockup className="mx-auto max-w-2xl" />
          </Reveal>
        </Container>
      </div>

      {/* ---------------------------------------------------- Systems it sits beside */}
      <Section tint="muted" bordered className="py-12 sm:py-14">
        <Container>
          <p className="text-center text-sm text-muted-foreground">
            An independent financial-intelligence layer — it reads from your systems, it doesn't
            replace them.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2.5">
            {SYSTEMS.map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm text-muted-foreground shadow-xs"
              >
                <Boxes className="size-4 text-muted-foreground/70" />
                {s}
              </span>
            ))}
          </div>
        </Container>
      </Section>

      {/* -------------------------------------------------------- Attention queue */}
      <Section id="queue">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="What needs me today"
              title="The desk opens on a queue, not a blank search box"
              description="Cedeon holds the validated contract, the committed losses and every recovery in flight — and turns that into one ranked list of what a person has to act on, grouped the way the work actually divides."
            />
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2">
            {CATEGORIES.map((c, i) => (
              <Reveal key={c.name} delay={0.04 * i}>
                <div className="flex h-full gap-4 rounded-xl border border-border bg-card p-5 shadow-sm">
                  <span
                    className={cn(
                      "inline-flex size-10 shrink-0 items-center justify-center rounded-lg [&_svg]:size-5",
                      c.tone,
                    )}
                  >
                    {c.icon}
                  </span>
                  <div>
                    <h3 className="font-semibold tracking-tight">{c.name}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{c.body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
          <p className="mt-6 text-center text-xs text-muted-foreground">
            The queue is a derived view over concrete records — not a pile of generic alerts. Every
            item links straight to the treaty, the calculation or the recoverable behind it.
          </p>
        </Container>
      </Section>

      {/* ------------------------------------------------------------ Principle */}
      <Section tint="muted" bordered>
        <Container className="grid gap-10 md:grid-cols-[1.1fr_1fr] md:items-center">
          <Reveal>
            <SectionHeading
              eyebrow="The non-negotiable"
              title="LLMs interpret. Deterministic code calculates. Humans approve."
              description="An LLM is never the source of truth for a financial figure. Every extracted term carries its document, page, clause, supporting text and confidence — and a person validates it before it can feed a calculation. Money is exact decimal arithmetic, versioned and unit-tested."
            />
          </Reveal>
          <Reveal delay={0.1} className="grid grid-cols-2 gap-3">
            {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
              <div
                key={k}
                className={cn(
                  "rounded-xl border px-4 py-4 text-sm font-medium shadow-xs",
                  KIND_CLASS[k],
                )}
              >
                <span className="block text-[11px] font-semibold uppercase tracking-wide opacity-70">
                  Trust class
                </span>
                {KIND_LABEL[k]}
              </div>
            ))}
          </Reveal>
        </Container>
      </Section>

      {/* -------------------------------------------------------- What Cedeon watches */}
      <Section id="watches">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="What Cedeon watches"
              title="The checks that put something on your queue"
              description="Each one is deterministic and explainable. Cedeon proposes; a person decides and the decision is recorded."
            />
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {WATCHES.map((w, i) => (
              <Reveal key={w.title} delay={0.04 * i}>
                <div className="h-full rounded-xl border border-border bg-card p-5 shadow-sm">
                  <span className="inline-flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary [&_svg]:size-5">
                    {w.icon}
                  </span>
                  <h3 className="mt-4 font-semibold tracking-tight">{w.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{w.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      {/* --------------------------------------------------------- How it works */}
      <Section id="how-it-works" tint="muted" bordered>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="How it works"
              title="One vertical thread, done properly"
              description="From a real-shaped excess-of-loss treaty and a loss dataset to a potential recovery — explained with exact treaty citations and deterministic calculations, then tracked to cash. Every step feeds the queue."
            />
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {PIPELINE.map((step, i) => (
              <Reveal key={step.title} delay={0.04 * i}>
                <div className="group relative h-full rounded-xl border border-border bg-card p-5 shadow-sm transition hover:border-border-strong hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        "inline-flex size-9 items-center justify-center rounded-lg border [&_svg]:size-4",
                        KIND_CLASS[step.kind],
                      )}
                    >
                      {step.icon}
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </div>
                  <h3 className="mt-4 font-semibold tracking-tight">{step.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{step.body}</p>
                  <span
                    className={cn(
                      "mt-3 inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium",
                      KIND_CLASS[step.kind],
                    )}
                  >
                    {KIND_LABEL[step.kind]}
                  </span>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      {/* ------------------------------------------------------------ Platform */}
      <Section id="platform">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Platform"
              title="The building blocks of a defensible recovery"
              description="Each with a single responsibility and a clear boundary between what a model may do and what only code and people may do."
            />
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((cap, i) => (
              <Reveal key={cap.title} delay={0.04 * i}>
                <div className="h-full rounded-xl border border-border bg-card p-5 shadow-sm">
                  <span className="inline-flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary [&_svg]:size-5">
                    {cap.icon}
                  </span>
                  <h3 className="mt-4 font-semibold tracking-tight">{cap.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{cap.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      {/* ----------------------------------------------------- Recovery is module one */}
      <Section id="layers" tint="muted" bordered>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="The arc"
              title="Recovery is module one of an intelligence system"
              description="Each layer answers a harder question than the one below it, and feeds the ones above. We are building them in order — recovery first, because its ROI is provable — and the data model stays honest to the whole arc."
            />
          </Reveal>
          <Reveal delay={0.1} className="mt-10 space-y-2.5">
            {LAYERS.map((layer) => {
              const m = LAYER_META[layer.state];
              return (
                <div
                  key={layer.name}
                  className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4 shadow-xs sm:flex-row sm:items-center sm:gap-4"
                >
                  <span className="w-full shrink-0 font-semibold tracking-tight sm:w-56">
                    {layer.name}
                  </span>
                  <span className="flex-1 text-sm text-muted-foreground">{layer.question}</span>
                  <span
                    className={cn(
                      "inline-block shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
                      m.class,
                    )}
                  >
                    {m.label}
                  </span>
                </div>
              );
            })}
          </Reveal>
          <p className="mt-6 text-sm text-muted-foreground">
            Not on the roadmap for now: pricing, placement, cat modelling, ceded accounting or a
            generic assistant. Cedeon works the recoveries your programme already creates.
          </p>
        </Container>
      </Section>

      {/* -------------------------------------------------------- Who it's for */}
      <Section id="who">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Who it's for"
              title="One desk, seen the way each team needs to see it"
              description="Cedeon produces a single, cited recovery — and surfaces the parts of it that matter to the people who have to sign, book, chase and defend the number."
            />
          </Reveal>
          <div className="mt-12 grid gap-4 sm:grid-cols-2">
            {AUDIENCES.map((a, i) => (
              <Reveal key={a.role} delay={0.04 * i}>
                <div className="flex h-full gap-4 rounded-xl border border-border bg-card p-5 shadow-sm">
                  <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary [&_svg]:size-5">
                    {a.icon}
                  </span>
                  <div>
                    <h3 className="font-semibold tracking-tight">{a.role}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{a.body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </Section>

      {/* ---------------------------------------------------------- Comparison */}
      <Section bordered tint="muted">
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Where it fits"
              title="Not a spreadsheet macro. Not a chatbot."
              description="Cedeon is the layer between your contracts and your ledger — auditable by construction, and always working."
            />
          </Reveal>
          <Reveal delay={0.1} className="mt-10 overflow-x-auto">
            <table className="w-full min-w-160 border-separate border-spacing-0 text-sm">
              <thead>
                <tr>
                  <th className="w-[42%] py-3 text-left font-medium text-muted-foreground" />
                  <th className="rounded-t-lg border border-b-0 border-primary/30 bg-primary/6 px-4 py-3 text-center font-semibold text-primary">
                    Cedeon
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-muted-foreground">
                    Manual bordereau review
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-muted-foreground">
                    Generic AI assistant
                  </th>
                </tr>
              </thead>
              <tbody>
                {COMPARE.map((r, i) => (
                  <tr key={r.row}>
                    <td className="border-t border-border py-3 pr-4 text-foreground">{r.row}</td>
                    <td
                      className={cn(
                        "border-x border-primary/30 bg-primary/6 px-4 py-3 text-center",
                        i === COMPARE.length - 1 && "rounded-b-lg border-b",
                      )}
                    >
                      <Mark value={r.cedeon} />
                    </td>
                    <td className="border-t border-border px-4 py-3 text-center">
                      <Mark value={r.manual} />
                    </td>
                    <td className="border-t border-border px-4 py-3 text-center">
                      <Mark value={r.assistant} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Reveal>
        </Container>
      </Section>

      {/* ------------------------------------------------------- Worked example */}
      <Section id="example">
        <Container className="grid gap-10 lg:grid-cols-[1fr_1.05fr] lg:items-center">
          <Reveal>
            <SectionHeading
              eyebrow="Worked example"
              title="A $58.7M event. An $8.7M recovery. Every number traced."
              description="A property-catastrophe layer of $20M excess of $50M, three reinsurers, one hurricane event of $58.7M across ten claims — through the calculation, then tracked to collection."
            />
            <dl className="mt-8 grid grid-cols-2 gap-4">
              {[
                { k: "Layer", v: "$20M xs $50M", tone: "text-fact" },
                { k: "Event incurred", v: "$58,700,000", tone: "text-fact" },
                { k: "Layer recovery", v: "$8,700,000", tone: "text-calculation" },
                { k: "Reinsurers", v: "3 participations", tone: "text-fact" },
              ].map((s) => (
                <div key={s.k} className="rounded-xl border border-border bg-card p-4 shadow-xs">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {s.k}
                  </dt>
                  <dd className={cn("mt-1 font-mono text-lg font-semibold tracking-tight", s.tone)}>
                    {s.v}
                  </dd>
                </div>
              ))}
            </dl>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="rounded-xl border border-border bg-card p-6 shadow-lg">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                XOL engine · v1.0.0
              </p>
              <div className="mt-4 space-y-3 font-mono text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">event − attachment</span>
                  <span>$58,700,000 − $50,000,000</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">= loss to layer</span>
                  <span>$8,700,000</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">min(loss to layer, limit)</span>
                  <span>min($8.7M, $20M)</span>
                </div>
                <div className="flex items-center justify-between border-t border-border pt-3 text-calculation">
                  <span className="font-sans font-semibold">Layer recovery</span>
                  <span className="font-semibold">$8,700,000.00</span>
                </div>
              </div>
              <div className="mt-5 space-y-2">
                {[
                  { n: "Reinsurer A — 50%", a: "$4,350,000.00", w: 50 },
                  { n: "Reinsurer B — 30%", a: "$2,610,000.00", w: 30 },
                  { n: "Reinsurer C — 20%", a: "$1,740,000.00", w: 20 },
                ].map((p) => (
                  <div key={p.n} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">{p.n}</span>
                      <span className="font-mono">{p.a}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-calculation/70"
                        style={{ width: `${p.w}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-5 border-t border-border pt-3 text-xs text-muted-foreground">
                Each share becomes a tracked recoverable — notified → agreed → billed → collected,
                with a chase action once it ages past its date.
              </p>
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* ------------------------------------------------------------ Security */}
      <Section id="security" bordered tint="muted">
        <Container className="grid gap-10 md:grid-cols-[1fr_1.1fr] md:items-center">
          <Reveal>
            <SectionHeading
              eyebrow="Trust & security"
              title="Auditable by construction"
              description="The guarantees are structural, not aspirational — they come from how the system is built."
            />
            <Button asChild variant="secondary" size="sm" className="mt-6">
              <Link href="/security">
                Read the security overview <ArrowRight className="size-4" />
              </Link>
            </Button>
          </Reveal>
          <Reveal delay={0.1} className="grid gap-3 sm:grid-cols-2">
            {[
              {
                icon: <Landmark />,
                t: "Exact-decimal money",
                b: "Decimal in code, NUMERIC in the database. Never binary floating point. Currency always explicit.",
              },
              {
                icon: <FileText />,
                t: "Provenance on every term",
                b: "Document, page, clause, span, confidence and model — attached before a term is executable.",
              },
              {
                icon: <ShieldCheck />,
                t: "Untrusted documents",
                b: "Uploaded text is data, never instruction. Tenancy enforced server-side; treaty text kept out of logs.",
              },
              {
                icon: <GitBranch />,
                t: "No outbound send",
                b: "The product drafts notices and stops. Nothing is transmitted to reinsurers or brokers.",
              },
            ].map((f) => (
              <div key={f.t} className="rounded-xl border border-border bg-card p-4 shadow-xs">
                <span className="inline-flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary [&_svg]:size-4">
                  {f.icon}
                </span>
                <p className="mt-3 text-sm font-semibold">{f.t}</p>
                <p className="mt-1 text-sm text-muted-foreground">{f.b}</p>
              </div>
            ))}
          </Reveal>
        </Container>
      </Section>

      {/* ------------------------------------------------------- What it is not */}
      <Section>
        <Container className="grid gap-10 md:grid-cols-[0.9fr_1.1fr] md:items-start">
          <Reveal>
            <SectionHeading
              eyebrow="Boundaries"
              title="What Cedeon is not"
              description="The constraints are deliberate. They are why the output is defensible."
            />
          </Reveal>
          <Reveal delay={0.1}>
            <ul className="space-y-3">
              {NOT_LIST.map((item) => (
                <li
                  key={item}
                  className="flex gap-3 rounded-xl border border-border bg-card p-4 text-sm shadow-xs"
                >
                  <span className="mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
                    <X className="size-3" />
                  </span>
                  <span className="text-muted-foreground">{item}</span>
                </li>
              ))}
            </ul>
          </Reveal>
        </Container>
      </Section>

      {/* ---------------------------------------------------------------- FAQ */}
      <Section id="faq" tint="muted" bordered>
        <Container className="grid gap-10 md:grid-cols-[0.8fr_1.2fr]">
          <Reveal>
            <SectionHeading eyebrow="FAQ" title="Questions, answered" />
          </Reveal>
          <Reveal delay={0.1}>
            <Accordion
              type="single"
              collapsible
              className="rounded-xl border border-border bg-card px-5"
            >
              {FAQ.map((item) => (
                <AccordionItem key={item.q} value={item.q}>
                  <AccordionTrigger>{item.q}</AccordionTrigger>
                  <AccordionContent>{item.a}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </Reveal>
        </Container>
      </Section>

      {/* ------------------------------------------------------------ Final CTA */}
      <Section tint="primary" bordered className="py-16">
        <Container className="flex flex-col items-start gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">
              See a recovery Cedeon would surface
            </h2>
            <p className="mt-2 max-w-xl text-muted-foreground">
              A $20M xs $50M property-cat layer, a $58.7M event, an $8.7M recovery — every number
              traced to the treaty, then tracked to cash.
            </p>
          </div>
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
