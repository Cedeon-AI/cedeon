import {
  ArrowRight,
  Boxes,
  Check,
  ClipboardCheck,
  Coins,
  FileSearch,
  FileText,
  GitBranch,
  Landmark,
  LineChart,
  Minus,
  ScrollText,
  ShieldCheck,
  Sigma,
  UserCheck,
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
    body: "A versioned, unit-tested engine computes attachment, layer recovery and each reinsurer's share. No LLM touches the math.",
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
    title: "Human review",
    body: "Confirm, edit, reject or request more information. Every decision is attributed and audited.",
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
    body: "Attachment, exhaustion, layer recovery and per-reinsurer allocation are versioned, unit-tested code. Exact decimal arithmetic — never floating point.",
    icon: <Sigma />,
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
  {
    title: "Audit & observability",
    body: "An append-only trail of every agent run, tool call, token and human decision. Per-agent and per-day spend roll-ups.",
    icon: <ShieldCheck />,
  },
];

const AUDIENCES: { role: string; body: string; icon: ReactNode }[] = [
  {
    role: "Ceded reinsurance managers",
    body: "See which treaties respond to a loss, why, and what each reinsurer owes — with the clauses to back it up.",
    icon: <ScrollText />,
  },
  {
    role: "Reinsurance accounting",
    body: "Turn a validated contract and committed losses into a recoverable you can book, traced to its inputs.",
    icon: <Coins />,
  },
  {
    role: "Finance & capital teams",
    body: "A defensible view of expected recoveries, separate from the claims system's estimates.",
    icon: <LineChart />,
  },
  {
    role: "Claims & recovery leads",
    body: "Catch notice obligations and missing evidence early, before they cost a recovery.",
    icon: <ClipboardCheck />,
  },
];

const NOT_LIST: string[] = [
  "A system of record. Cedeon reads from your systems; it does not replace claims, reinsurance administration or the general ledger.",
  "An autonomous agent. Nothing is sent, filed or booked without a person deciding.",
  "A generic AI assistant. It does one thing — reinsurance recovery — end to end, with provenance.",
  "A model that guesses at money. Every figure is deterministic code over validated inputs.",
];

type Cell = boolean | "partial" | string;
const COMPARE: { row: string; cedeon: Cell; manual: Cell; assistant: Cell }[] = [
  {
    row: "Exact treaty citations on every term",
    cedeon: true,
    manual: "partial",
    assistant: false,
  },
  { row: "Deterministic, unit-tested math", cedeon: true, manual: "partial", assistant: false },
  { row: "No financial figure authored by an LLM", cedeon: true, manual: true, assistant: false },
  {
    row: "Human sign-off gate before values are trusted",
    cedeon: true,
    manual: "partial",
    assistant: false,
  },
  { row: "Per-reinsurer allocation", cedeon: true, manual: "partial", assistant: false },
  { row: "Immutable audit trail of every decision", cedeon: true, manual: false, assistant: false },
  { row: "Scales past a handful of treaties", cedeon: true, manual: false, assistant: "partial" },
];

const FAQ: { q: string; a: string }[] = [
  {
    q: "Does an LLM ever calculate the recovery figure?",
    a: "No. Extraction and drafting use language models; every financial calculation runs in a versioned, unit-tested engine using exact decimal arithmetic. The investigator agent is handed the deterministic figure as a fact and cannot overwrite it.",
  },
  {
    q: "Where does the recovery number come from, then?",
    a: "From validated treaty terms and committed loss data, run through the XOL engine. Attachment, exhaustion, layer recovery and each reinsurer's share are computed in code and traceable to their inputs.",
  },
  {
    q: "What does a person actually have to approve?",
    a: "Material interpretations. A human validates each extracted term before it can feed a calculation, and reviews the recovery packet before it is considered final. Confirm, edit, reject or request more information — every action is attributed and audited.",
  },
  {
    q: "Does Cedeon send notices to reinsurers or brokers?",
    a: "No. The notice drafter produces a draft from approved facts and stops there. There is deliberately no send action anywhere in the product. Sending stays in your systems, with your people.",
  },
  {
    q: "How does Cedeon fit with our existing claims and reinsurance systems?",
    a: "It sits beside them as a financial-intelligence layer. Cedeon reads treaties and loss data, identifies and explains potential recoveries, and hands back an evidence-backed packet. It does not replace your system of record.",
  },
  {
    q: "How are uploaded documents handled?",
    a: "Every uploaded document is treated as untrusted input. Document text is data, never instruction. Tenancy is enforced server-side and treaty text is kept out of ordinary logs.",
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
              Reinsurance recovery intelligence
            </Eyebrow>
            <h1 className="mt-6 text-balance text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
              Reinsurance intelligence from{" "}
              <span className="text-gradient">contract to recovery</span>.
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg text-muted-foreground">
              Upload your reinsurance treaties and loss data. Cedeon understands the contracts,
              monitors the losses, identifies potential recoveries, explains why the treaty
              responds, and prepares an evidence-backed recovery package for human review.
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
            <ProductMockup className="mx-auto max-w-4xl" />
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

      {/* ------------------------------------------------------------ Principle */}
      <Section>
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

      {/* --------------------------------------------------------- How it works */}
      <Section id="how-it-works" tint="muted" bordered>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="How it works"
              title="One vertical thread, done properly"
              description="From a real-shaped excess-of-loss treaty and a loss dataset to a potential recovery — explained with exact treaty citations and deterministic calculations."
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
              description="Six components, each with a single responsibility and a clear boundary between what a model may do and what only code and people may do."
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

      {/* -------------------------------------------------------- Who it's for */}
      <Section id="who" tint="muted" bordered>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Who it's for"
              title="One recovery, seen the way each team needs to see it"
              description="Cedeon produces a single, cited recovery — and presents the parts of it that matter to the people who have to sign, book and defend the number."
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
      <Section bordered>
        <Container>
          <Reveal>
            <SectionHeading
              eyebrow="Where it fits"
              title="Not a spreadsheet macro. Not a chatbot."
              description="Cedeon is the layer between your contracts and your ledger — auditable by construction."
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
      <Section id="example" tint="muted" bordered>
        <Container className="grid gap-10 lg:grid-cols-[1fr_1.05fr] lg:items-center">
          <Reveal>
            <SectionHeading
              eyebrow="Worked example"
              title="A $58.7M event. An $8.7M recovery. Every number traced."
              description="A property-catastrophe layer of $20M excess of $50M, three reinsurers, one hurricane event of $58.7M across ten claims."
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
            </div>
          </Reveal>
        </Container>
      </Section>

      {/* ------------------------------------------------------------ Security */}
      <Section id="security" bordered>
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
      <Section tint="muted" bordered>
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
      <Section id="faq">
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
              traced to the treaty.
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
