"use client";

import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const LIFECYCLE = ["Placement", "Contract", "Claims", "Recovery", "Settlement", "Renewal"] as const;

const PIPELINE: { title: string; body: string; kind: Kind }[] = [
  {
    title: "Treaty document",
    body: "Upload the PDF or DOCX. Cedeon parses it with page, section and clause structure intact.",
    kind: "fact",
  },
  {
    title: "Validated terms",
    body: "AI proposes each term with an exact citation and a confidence score. A human confirms before anything becomes executable.",
    kind: "human",
  },
  {
    title: "Deterministic recovery",
    body: "A versioned, unit-tested engine computes attachment, layer recovery and each reinsurer's share. No LLM touches the math.",
    kind: "calculation",
  },
  {
    title: "AI investigation",
    body: "A bounded, read-only agent checks applicability, relevant clauses, missing evidence and notice obligations — every finding cited.",
    kind: "ai",
  },
  {
    title: "Recovery packet",
    body: "An evidence-backed artifact that keeps fact, calculation, AI interpretation and human decision visibly separate.",
    kind: "fact",
  },
  {
    title: "Human review",
    body: "Confirm, edit, reject or request more information. Every decision is attributed and audited.",
    kind: "human",
  },
];

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

export function Landing() {
  const reduce = useReducedMotion();
  const rise = (delay = 0) =>
    reduce
      ? {}
      : {
          initial: { opacity: 0, y: 16 },
          whileInView: { opacity: 1, y: 0 },
          viewport: { once: true, margin: "-80px" },
          transition: { duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] as const },
        };

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[520px] grid-backdrop" />

      {/* Hero */}
      <section className="relative mx-auto w-full max-w-6xl px-6 pt-20 pb-16 sm:pt-28">
        <motion.p
          {...(reduce
            ? {}
            : {
                initial: { opacity: 0, y: 10 },
                animate: { opacity: 1, y: 0 },
                transition: { duration: 0.5 },
              })}
          className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Cedeon Recovery Intelligence
        </motion.p>

        <motion.h1
          {...(reduce
            ? {}
            : {
                initial: { opacity: 0, y: 18 },
                animate: { opacity: 1, y: 0 },
                transition: { duration: 0.6, delay: 0.05, ease: [0.22, 1, 0.36, 1] },
              })}
          className="max-w-3xl text-balance text-4xl font-semibold leading-[1.1] tracking-tight sm:text-6xl"
        >
          Reinsurance intelligence from <span className="text-primary">contract to recovery</span>.
        </motion.h1>

        <motion.p
          {...(reduce
            ? {}
            : {
                initial: { opacity: 0, y: 18 },
                animate: { opacity: 1, y: 0 },
                transition: { duration: 0.6, delay: 0.12 },
              })}
          className="mt-6 max-w-2xl text-lg text-muted-foreground"
        >
          Upload your reinsurance treaties and loss data. Cedeon understands the contracts, monitors
          the losses, identifies potential recoveries, explains why the treaty responds, and
          prepares an evidence-backed recovery package for human review.
        </motion.p>

        <motion.div
          {...(reduce
            ? {}
            : {
                initial: { opacity: 0, y: 18 },
                animate: { opacity: 1, y: 0 },
                transition: { duration: 0.6, delay: 0.19 },
              })}
          className="mt-8 flex flex-wrap items-center gap-3"
        >
          <Link href="/login">
            <Button size="lg">Request access</Button>
          </Link>
          <Link href="/login">
            <Button size="lg" variant="secondary">
              Sign in
            </Button>
          </Link>
        </motion.div>

        <LifecycleStrip reduce={Boolean(reduce)} />
      </section>

      {/* Principle */}
      <section className="border-y border-border/60 bg-muted/40">
        <div className="mx-auto grid w-full max-w-6xl gap-8 px-6 py-14 md:grid-cols-[1.1fr_1fr] md:items-center">
          <motion.div {...rise()}>
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              LLMs interpret. Deterministic code calculates. Humans approve.
            </h2>
            <p className="mt-4 text-muted-foreground">
              An LLM is never the source of truth for a financial figure. Every extracted term
              carries its document, page, clause, supporting text and confidence — and a person
              validates it before it can feed a calculation. Money is exact decimal arithmetic,
              versioned and unit-tested.
            </p>
          </motion.div>
          <motion.div {...rise(0.1)} className="grid grid-cols-2 gap-3">
            {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
              <div
                key={k}
                className={cn("rounded-lg border px-4 py-3 text-sm font-medium", KIND_CLASS[k])}
              >
                {KIND_LABEL[k]}
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Pipeline */}
      <section className="mx-auto w-full max-w-6xl px-6 py-16 sm:py-24">
        <motion.h2
          {...rise()}
          className="max-w-2xl text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          One vertical thread, done properly
        </motion.h2>
        <motion.p {...rise(0.05)} className="mt-3 max-w-2xl text-muted-foreground">
          From a real-shaped excess-of-loss treaty and a loss dataset to a potential recovery,
          explained with exact treaty citations and deterministic calculations.
        </motion.p>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PIPELINE.map((step, i) => (
            <motion.div
              key={step.title}
              {...rise(0.05 * i)}
              className="group relative rounded-lg border border-border bg-card p-5"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-muted-foreground">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[11px] font-medium",
                    KIND_CLASS[step.kind],
                  )}
                >
                  {KIND_LABEL[step.kind]}
                </span>
              </div>
              <h3 className="mt-3 font-semibold tracking-tight">{step.title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{step.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border/60 bg-primary/5">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-start gap-6 px-6 py-16 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">
              See a recovery Cedeon would surface
            </h2>
            <p className="mt-2 text-muted-foreground">
              A $20M xs $50M property-cat layer, a $58.7M event, an $8.7M recovery — every number
              traced to the treaty.
            </p>
          </div>
          <Link href="/login">
            <Button size="lg">Request access</Button>
          </Link>
        </div>
      </section>
    </div>
  );
}

function LifecycleStrip({ reduce }: { reduce: boolean }) {
  return (
    <div className="mt-16 rounded-xl border border-border bg-card/60 p-4 sm:p-6">
      <p className="mb-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        The reinsurance lifecycle — Cedeon starts at recovery
      </p>
      <div className="flex flex-wrap items-center gap-x-1 gap-y-3">
        {LIFECYCLE.map((stage, i) => (
          <Segment key={stage} active={stage === "Recovery"} reduce={reduce} index={i}>
            {stage}
            {i < LIFECYCLE.length - 1 ? (
              <span className="mx-1 text-muted-foreground/50">→</span>
            ) : null}
          </Segment>
        ))}
      </div>
    </div>
  );
}

function Segment({
  children,
  active,
  reduce,
  index,
}: {
  children: ReactNode;
  active: boolean;
  reduce: boolean;
  index: number;
}) {
  return (
    <motion.span
      {...(reduce
        ? {}
        : {
            initial: { opacity: 0, y: 6 },
            whileInView: { opacity: 1, y: 0 },
            viewport: { once: true },
            transition: { duration: 0.4, delay: 0.05 * index },
          })}
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-1 text-sm font-medium",
        active ? "bg-primary text-primary-foreground" : "text-muted-foreground",
      )}
    >
      {children}
    </motion.span>
  );
}
