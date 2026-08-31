"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import { Check, FileSearch, FileText, Landmark, Mail, Sigma, Wallet } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { RecoveryCollectionSection } from "@/components/app/recovery-collection-section";
import { RecoveryInvestigationPanel } from "@/components/app/recovery-investigation-panel";
import { RecoveryNoticesView } from "@/components/app/recovery-notices-view";
import { RecoveryPacketView } from "@/components/app/recovery-packet-view";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/field";
import { BackLink, EmptyState, PageHeader } from "@/components/ui/page-header";
import type { NoticeObligationOut, RecoveryCalculationOut, ReviewDecision } from "@/lib/api";
import {
  getLossEvent,
  getRecoveryCandidate,
  recalculateRecoveryCandidate,
  reviewRecoveryCandidate,
  setRecoveryKnowledgeDate,
} from "@/lib/api";
import { deadlineChip } from "@/lib/obligations";
import { candidateStatus } from "@/lib/recoveries";
import { formatShare } from "@/lib/treaties";
import { cn, formatMoney } from "@/lib/utils";

type Section = "loss-basis" | "calculation" | "investigation" | "packet" | "notice" | "collection";

const RAIL: { key: Section; label: string; icon: LucideIcon }[] = [
  { key: "loss-basis", label: "Loss basis", icon: Landmark },
  { key: "calculation", label: "Calculation", icon: Sigma },
  { key: "investigation", label: "Investigation", icon: FileSearch },
  { key: "packet", label: "Packet", icon: FileText },
  { key: "notice", label: "Notice", icon: Mail },
  { key: "collection", label: "Collection", icon: Wallet },
];

const KEYS = new Set<Section>(RAIL.map((r) => r.key));

export function RecoveryCandidateDetailView({ candidateId }: { candidateId: string }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const searchParams = useSearchParams();
  const raw = searchParams.get("section") as Section | null;
  const section: Section = raw && KEYS.has(raw) ? raw : "calculation";

  const detail = useQuery({
    queryKey: ["recovery-candidates", candidateId],
    queryFn: async () =>
      (await getRecoveryCandidate({ path: { candidate_id: candidateId }, throwOnError: true }))
        .data,
    refetchInterval: (query) =>
      (query.state.data?.investigations ?? []).some((i) => i.status === "running") ? 2500 : false,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["recovery-candidates"] });
  };

  const review = useMutation({
    mutationFn: async (decision: ReviewDecision) => {
      await reviewRecoveryCandidate({
        path: { candidate_id: candidateId },
        body: { decision, reason: reason.trim() || null },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      setReason("");
      invalidate();
    },
  });

  const recalculate = useMutation({
    mutationFn: async () => {
      await recalculateRecoveryCandidate({
        path: { candidate_id: candidateId },
        throwOnError: true,
      });
    },
    onSuccess: invalidate,
  });

  if (detail.isLoading || !detail.data) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  const {
    candidate,
    current_calculation: calc,
    calculations,
    reviews,
    investigations,
    notice_obligation: obligation,
  } = detail.data;
  const status = candidateStatus(candidate.status);
  const open = candidate.status === "needs_review" || candidate.status === "in_review";
  const canNotice = candidate.status === "confirmed" || candidate.status === "notice_drafted";
  const hasInvestigation = investigations.some((i) => !i.superseded && i.status === "completed");

  const railState: Partial<Record<Section, "done" | "locked">> = {
    "loss-basis": "done",
    calculation: calc ? "done" : undefined,
    investigation: hasInvestigation ? "done" : undefined,
    notice: canNotice ? undefined : "locked",
    collection: canNotice ? undefined : "locked",
  };

  return (
    <div className="space-y-6">
      <BackLink href="/recovery-candidates">Recoveries</BackLink>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            Recovery
            <Badge tone={status.tone}>{status.label}</Badge>
            {candidate.currency_mismatch ? <Badge tone="warning">currency mismatch</Badge> : null}
          </span>
        }
        description={
          <>
            {formatMoney(candidate.gross_event_incurred, candidate.currency)} event ·{" "}
            <Link
              href={`/loss-events/${candidate.loss_event_id}`}
              className="text-primary hover:underline"
            >
              loss event
            </Link>{" "}
            ·{" "}
            <Link
              href={`/treaties/${candidate.treaty_id}`}
              className="text-primary hover:underline"
            >
              treaty
            </Link>
          </>
        }
      />

      {candidate.currency_mismatch ? (
        <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
          Some claims are in a currency other than {candidate.currency}. Only {candidate.currency}{" "}
          claims are included in the gross — there is no FX conversion.
        </p>
      ) : null}

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* rail */}
        <nav className="shrink-0 lg:w-48">
          <ul className="flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:gap-0.5 lg:pb-0">
            {RAIL.map((item) => {
              const state = railState[item.key];
              const active = section === item.key;
              const Icon = item.icon;
              const locked = state === "locked";
              return (
                <li key={item.key} className="shrink-0">
                  <Link
                    href={`?section=${item.key}`}
                    scroll={false}
                    aria-disabled={locked}
                    className={cn(
                      "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition",
                      active && "bg-primary/10 font-medium text-primary",
                      !active &&
                        !locked &&
                        "text-muted-foreground hover:bg-muted hover:text-foreground",
                      locked && "pointer-events-none text-muted-foreground/40",
                    )}
                  >
                    <Icon className="size-4 shrink-0" />
                    <span className="flex-1">{item.label}</span>
                    {item.key === "notice" &&
                    obligation?.deadline &&
                    !obligation.satisfied &&
                    obligation.days_until !== null &&
                    obligation.days_until !== undefined &&
                    obligation.days_until <= 30 ? (
                      <span
                        className={cn(
                          "rounded px-1 text-[10px] font-semibold",
                          obligation.days_until <= 7
                            ? "bg-danger/15 text-danger"
                            : "bg-warning/15 text-warning",
                        )}
                      >
                        {obligation.days_until < 0
                          ? `${Math.abs(obligation.days_until)}d`
                          : `${obligation.days_until}d`}
                      </span>
                    ) : state === "done" ? (
                      <Check className="size-3.5 text-human" />
                    ) : null}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* content */}
        <div className="min-w-0 flex-1 space-y-4">
          {section === "loss-basis" ? (
            <Card>
              <CardHeader>
                <CardTitle>Loss basis</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <Row
                  k="Gross event incurred"
                  v={formatMoney(candidate.gross_event_incurred, candidate.currency)}
                />
                <Row k="Currency" v={candidate.currency} />
                <OccurrenceBasisRow eventId={candidate.loss_event_id} />
                <p className="pt-1 text-muted-foreground">
                  The claims and treaty layer that feed the calculation.{" "}
                  <Link
                    href={`/loss-events/${candidate.loss_event_id}`}
                    className="text-primary hover:underline"
                  >
                    Open the loss event
                  </Link>{" "}
                  ·{" "}
                  <Link
                    href={`/treaties/${candidate.treaty_id}`}
                    className="text-primary hover:underline"
                  >
                    open the treaty
                  </Link>
                  .
                </p>
              </CardContent>
            </Card>
          ) : null}

          {section === "calculation" ? (
            <>
              {candidate.drifted_at ? (
                <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
                  <span className="font-medium">The number moved.</span> Claims developed and Cedeon
                  recalculated
                  {candidate.pre_drift_recovery
                    ? ` — ${formatMoney(candidate.pre_drift_recovery, candidate.currency)} → ${
                        calc ? formatMoney(calc.layer_recovery, calc.currency) : "?"
                      }`
                    : ""}
                  . Re-review and confirm the new figure.
                </p>
              ) : null}
              {calc ? (
                <CalculationCard calc={calc} />
              ) : (
                <EmptyState
                  icon={<Sigma />}
                  title="No calculation on this recovery yet"
                  description="Recalculate to run the engine."
                />
              )}

              <Card>
                <CardHeader>
                  <CardTitle>Review</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    The calculation is deterministic. Confirm it once you have checked it against
                    the treaty terms and the claim schedule.
                  </p>
                  {open ? (
                    <>
                      <Textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Optional note (recorded with the decision)"
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          onClick={() => review.mutate("confirm")}
                          disabled={review.isPending}
                        >
                          Confirm
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => review.mutate("request_info")}
                          disabled={review.isPending}
                        >
                          Request info
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => review.mutate("reject")}
                          disabled={review.isPending}
                        >
                          Reject
                        </Button>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm">
                      {status.label}
                      {candidate.reviewed_at
                        ? ` · ${new Date(candidate.reviewed_at).toLocaleString()}`
                        : ""}
                    </p>
                  )}
                  <div className="pt-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => recalculate.mutate()}
                      disabled={recalculate.isPending}
                    >
                      {recalculate.isPending ? "Recalculating…" : "Recalculate"}
                    </Button>
                    <span className="ml-2 text-xs text-muted-foreground">
                      re-runs the engine; a new calculation is stored only if inputs changed
                    </span>
                  </div>
                </CardContent>
              </Card>

              {reviews.length > 0 ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Review history</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {reviews.map((r) => (
                      <div
                        key={r.created_at}
                        className="border-b border-border/60 pb-2 last:border-0"
                      >
                        <span className="font-medium capitalize">
                          {r.decision.replace("_", " ")}
                        </span>{" "}
                        <span className="text-xs text-muted-foreground">
                          {new Date(r.created_at).toLocaleString()}
                        </span>
                        {r.reason ? (
                          <p className="text-xs text-muted-foreground">{r.reason}</p>
                        ) : null}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}

              {calculations.length > 1 ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Calculation history ({calculations.length})</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1 text-sm">
                    {calculations.map((c) => (
                      <div key={c.id} className="flex justify-between gap-4">
                        <span className="text-muted-foreground">
                          {new Date(c.created_at).toLocaleString()}
                          {c.id === candidate.current_calculation_id ? " · current" : ""}
                        </span>
                        <span className="font-medium">
                          {formatMoney(c.layer_recovery, c.currency)}
                        </span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}
            </>
          ) : null}

          {section === "investigation" ? (
            <RecoveryInvestigationPanel candidateId={candidateId} investigations={investigations} />
          ) : null}

          {section === "packet" ? <RecoveryPacketView candidateId={candidateId} embedded /> : null}

          {section === "notice" ? (
            <>
              {obligation ? (
                <NoticeObligationCard
                  candidateId={candidateId}
                  obligation={obligation}
                  onChange={invalidate}
                />
              ) : null}
              <RecoveryNoticesView candidateId={candidateId} embedded />
            </>
          ) : null}

          {section === "collection" ? (
            <RecoveryCollectionSection candidateId={candidateId} canTrack={canNotice} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-medium tabular-nums">{v}</span>
    </div>
  );
}

function NoticeObligationCard({
  candidateId,
  obligation,
  onChange,
}: {
  candidateId: string;
  obligation: NoticeObligationOut;
  onChange: () => void;
}) {
  const [knowledge, setKnowledge] = useState(obligation.reference_date ?? "");
  const chip = deadlineChip(obligation);

  const save = useMutation({
    mutationFn: async (value: string) => {
      await setRecoveryKnowledgeDate({
        path: { candidate_id: candidateId },
        body: { knowledge_date: value || null },
        throwOnError: true,
      });
    },
    onSuccess: onChange,
  });

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Notice obligation</CardTitle>
        <Badge tone={chip.tone}>{chip.text}</Badge>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {obligation.provision_text ? (
          <p className="border-l-2 border-fact/40 bg-fact/5 px-3 py-2 text-muted-foreground">
            “{obligation.provision_text}”
          </p>
        ) : null}

        {obligation.has_structured_term && obligation.deadline ? (
          <div className="space-y-1">
            <Row k="Deadline" v={obligation.deadline} />
            <Row
              k="Period"
              v={`${obligation.period_days} ${obligation.basis === "business" ? "business " : ""}days`}
            />
            {obligation.reference_label ? (
              <Row
                k="Counted from"
                v={`${obligation.reference_label}${
                  obligation.reference_date ? ` (${obligation.reference_date})` : ""
                }`}
              />
            ) : null}
          </div>
        ) : (
          <p className="text-muted-foreground">
            No structured deadline yet. Set the period, trigger and basis on the{" "}
            <span className="font-medium text-foreground">treaty's notice provision</span> and
            Cedeon will compute the date here.
          </p>
        )}

        {obligation.note ? (
          <p className="rounded-md border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
            {obligation.note}
          </p>
        ) : null}

        {obligation.trigger === "knowledge_of_loss" ? (
          <div className="flex flex-wrap items-end gap-2 border-t border-border/60 pt-3">
            <Field label="Date of knowledge" htmlFor="obl-knowledge">
              <Input
                id="obl-knowledge"
                type="date"
                value={knowledge}
                onChange={(e) => setKnowledge(e.target.value)}
                className="w-auto"
              />
            </Field>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => save.mutate(knowledge)}
              disabled={save.isPending}
            >
              {save.isPending ? "Saving…" : "Set date"}
            </Button>
          </div>
        ) : null}

        <p className="text-xs text-muted-foreground">
          The date is computed by deterministic code from the validated clause — the AI never sets a
          deadline. Cedeon never sends the notice.
        </p>
      </CardContent>
    </Card>
  );
}

function OccurrenceBasisRow({ eventId }: { eventId: string }) {
  const event = useQuery({
    queryKey: ["loss-events", eventId],
    queryFn: async () =>
      (await getLossEvent({ path: { event_id: eventId }, throwOnError: true })).data.event,
  });
  const e = event.data;
  if (!e || (!e.peril && !e.hours_clause_hours)) return null;
  return (
    <Row
      k="Occurrence basis"
      v={`${e.peril ?? "—"}${e.hours_clause_hours ? ` · ${e.hours_clause_hours}h clause` : ""}`}
    />
  );
}

function CalculationCard({ calc }: { calc: RecoveryCalculationOut }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Calculation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-md border border-calculation/30 bg-calculation/5 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-calculation">
            Layer recovery
          </p>
          <p className="mt-1 font-mono text-2xl font-semibold tracking-tight">
            {formatMoney(calc.layer_recovery, calc.currency)}
          </p>
          <p className="text-xs text-muted-foreground">
            engine {calc.engine_version} · {calc.input_hash.slice(0, 12)}…
          </p>
        </div>

        <ol className="space-y-1 text-sm">
          {calc.trace.map((step) => (
            <li key={step.label} className="flex justify-between gap-4">
              <span className="text-muted-foreground">{step.label}</span>
              <span className="font-mono text-xs">
                {step.expression} = {step.result}
              </span>
            </li>
          ))}
        </ol>

        <table className="w-full text-sm">
          <tbody>
            {calc.allocations.map((a) => (
              <tr key={a.reinsurer_id} className="border-t border-border/60">
                <td className="py-1.5">{a.reinsurer_name}</td>
                <td className="py-1.5 text-muted-foreground">
                  {formatShare(a.participation_share)}
                </td>
                <td className="py-1.5 text-right font-medium">
                  {formatMoney(a.allocated_recovery, calc.currency)}
                </td>
              </tr>
            ))}
            {Number(calc.cedent_retention) > 0 ? (
              <tr className="border-t border-border/60 text-muted-foreground">
                <td className="py-1.5">Cedent retention</td>
                <td />
                <td className="py-1.5 text-right">
                  {formatMoney(calc.cedent_retention, calc.currency)}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
