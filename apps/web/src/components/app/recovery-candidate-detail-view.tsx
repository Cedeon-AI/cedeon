"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RecoveryCalculationOut, ReviewDecision } from "@/lib/api";
import {
  getRecoveryCandidate,
  recalculateRecoveryCandidate,
  reviewRecoveryCandidate,
} from "@/lib/api";
import { candidateStatus } from "@/lib/recoveries";
import { formatShare } from "@/lib/treaties";
import { formatMoney } from "@/lib/utils";

export function RecoveryCandidateDetailView({ candidateId }: { candidateId: string }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");

  const detail = useQuery({
    queryKey: ["recovery-candidates", candidateId],
    queryFn: async () =>
      (await getRecoveryCandidate({ path: { candidate_id: candidateId }, throwOnError: true }))
        .data,
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

  const { candidate, current_calculation: calc, calculations, reviews } = detail.data;
  const status = candidateStatus(candidate.status);
  const open = candidate.status === "needs_review" || candidate.status === "in_review";

  return (
    <div className="space-y-6">
      <div>
        <Link href="/recovery-candidates" className="text-sm text-muted-foreground hover:underline">
          ← Recovery candidates
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">Recovery candidate</h1>
          <Badge tone={status.tone}>{status.label}</Badge>
          {candidate.currency_mismatch ? <Badge tone="warning">currency mismatch</Badge> : null}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Gross event incurred {formatMoney(candidate.gross_event_incurred, candidate.currency)} ·{" "}
          <Link
            href={`/loss-events/${candidate.loss_event_id}`}
            className="text-primary hover:underline"
          >
            loss event
          </Link>{" "}
          ·{" "}
          <Link href={`/treaties/${candidate.treaty_id}`} className="text-primary hover:underline">
            treaty
          </Link>
        </p>
      </div>

      {candidate.currency_mismatch ? (
        <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
          Some underlying losses are in a currency other than {candidate.currency}. Only{" "}
          {candidate.currency} losses are included in the gross — there is no FX conversion.
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        {calc ? (
          <CalculationCard calc={calc} />
        ) : (
          <Card>
            <CardContent className="py-8 text-sm text-muted-foreground">
              No calculation on this candidate.
            </CardContent>
          </Card>
        )}

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Review</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-muted-foreground">
                The calculation is deterministic. Confirm it once you have checked it against the
                treaty terms and the claim schedule.
              </p>
              {open ? (
                <>
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Optional note (recorded with the decision)"
                    className="min-h-16 w-full rounded-md border border-input bg-background p-2 text-sm"
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
                  <div key={r.created_at} className="border-b border-border/60 pb-2 last:border-0">
                    <span className="font-medium capitalize">{r.decision.replace("_", " ")}</span>{" "}
                    <span className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleString()}
                    </span>
                    {r.reason ? <p className="text-xs text-muted-foreground">{r.reason}</p> : null}
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
                    <span className="font-medium">{formatMoney(c.layer_recovery, c.currency)}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
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
          <p className="mt-1 text-2xl font-semibold tracking-tight">
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
