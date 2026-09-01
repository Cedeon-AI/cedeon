"use client";

import { useQuery } from "@tanstack/react-query";
import { Sparkles, Upload } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BackLink, PageHeader } from "@/components/ui/page-header";
import { getLossEvent, getOccurrenceProposal, listRecoverySuggestions } from "@/lib/api";
import { formatMoney } from "@/lib/utils";

export function LossEventDetailView({ eventId }: { eventId: string }) {
  const detail = useQuery({
    queryKey: ["loss-events", eventId],
    queryFn: async () =>
      (await getLossEvent({ path: { event_id: eventId }, throwOnError: true })).data,
  });

  const suggestions = useQuery({
    queryKey: ["recovery-suggestions", eventId],
    queryFn: async () =>
      (
        await listRecoverySuggestions({
          query: { loss_event_id: eventId },
          throwOnError: true,
        })
      ).data.suggestions,
  });

  const occurrences = useQuery({
    queryKey: ["occurrence-proposal", eventId],
    queryFn: async () =>
      (await getOccurrenceProposal({ path: { event_id: eventId }, throwOnError: true })).data,
  });

  if (detail.isLoading || !detail.data) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  const { event, losses } = detail.data;
  const suggested = suggestions.data ?? [];

  return (
    <div className="space-y-6">
      <BackLink href="/loss-events">Loss events</BackLink>
      <PageHeader
        title={event.name}
        description={`${event.event_identifier ? `${event.event_identifier} · ` : ""}${
          event.date_of_loss_from
            ? `${event.date_of_loss_from} → ${event.date_of_loss_to}`
            : "no dated losses"
        }${event.catastrophe_code ? ` · ${event.catastrophe_code}` : ""}`}
        actions={
          <Button asChild size="sm" variant="secondary">
            <Link href="/loss-imports">
              <Upload /> Import claims
            </Link>
          </Button>
        }
      />

      {event.peril || event.hours_clause_hours ? (
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Occurrence basis</span> —{" "}
          {event.peril ?? "peril not stated"}
          {event.hours_clause_hours ? ` · ${event.hours_clause_hours}-hour clause` : ""}
        </p>
      ) : null}

      {occurrences.data && occurrences.data.occurrences.length > 0 ? (
        <Card className={occurrences.data.splits_the_event ? "border-warning/40 bg-warning/5" : ""}>
          <CardHeader>
            <CardTitle>
              Hours-clause view
              {occurrences.data.splits_the_event
                ? ` — Cedeon sees ${occurrences.data.occurrences.length} occurrences`
                : " — one occurrence"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-muted-foreground">
              Grouping the claims into rolling {occurrences.data.window_days}-day windows (
              {occurrences.data.hours}-hour clause,{" "}
              {occurrences.data.hours_source === "treaty"
                ? "from the event"
                : "peril default — set the clause on the event to override"}
              ). A proposal — the cedent chooses when each window starts.
            </p>
            {occurrences.data.splits_the_event ? (
              <ul className="divide-y divide-border/70">
                {occurrences.data.occurrences.map((o) => (
                  <li key={o.index} className="flex items-baseline justify-between gap-3 py-2">
                    <span>
                      <span className="font-medium">Occurrence {o.index}</span>{" "}
                      <span className="text-muted-foreground">
                        {o.start_date} → {o.end_date} · {o.claim_count} claim
                        {o.claim_count === 1 ? "" : "s"}
                      </span>
                    </span>
                    <span className="font-mono text-xs">
                      {formatMoney(o.gross_incurred, event.currency ?? "USD")}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">
                All {occurrences.data.occurrences[0]?.claim_count ?? 0} claims fall inside one
                window — the event is a single occurrence.
              </p>
            )}
          </CardContent>
        </Card>
      ) : null}

      {suggested.length > 0 ? (
        <Card className="border-calculation/30 bg-calculation/5">
          <CardHeader className="flex-row items-center gap-2">
            <Sparkles className="size-4 text-calculation" />
            <CardTitle>Treaties that may respond</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {suggested.map((s) => (
              <div
                key={s.treaty_id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-background p-3 text-sm"
              >
                <span>
                  <Link
                    href={`/treaties/${s.treaty_id}`}
                    className="font-medium text-primary hover:underline"
                  >
                    {s.treaty_name}
                  </Link>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{s.reason}</span>
                </span>
                <span className="flex items-center gap-3">
                  <span className="font-mono text-xs tabular-nums">
                    ~{formatMoney(s.indicative_recovery, s.currency)}
                  </span>
                  <Button asChild size="sm" variant="secondary">
                    <Link href="/recovery-candidates/new">Open a recovery</Link>
                  </Button>
                </span>
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              A deterministic screen — currency, the treaty window, and gross above the attachment.
              Confirm it by opening the recovery; Cedeon computes the real figure.
            </p>
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-wrap gap-3">
        {event.totals.map((total) => (
          <div
            key={total.currency}
            className="rounded-md border border-calculation/30 bg-calculation/5 p-3"
          >
            <p className="text-xs font-medium uppercase tracking-wide text-calculation">
              Gross incurred · {total.currency}
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-tight">
              {formatMoney(total.gross_incurred, total.currency)}
            </p>
            <p className="text-xs text-muted-foreground">{total.claim_count} claims</p>
          </div>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Claim schedule ({losses.length})</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left uppercase tracking-wide text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">Claim</th>
                <th className="py-2 pr-3 font-medium">Date of loss</th>
                <th className="py-2 pr-3 font-medium">Cause</th>
                <th className="py-2 pr-3 font-medium">Location</th>
                <th className="py-2 pr-3 text-right font-medium">Paid</th>
                <th className="py-2 pr-3 text-right font-medium">Reserve</th>
                <th className="py-2 pr-3 text-right font-medium">Incurred</th>
              </tr>
            </thead>
            <tbody>
              {losses.map((loss) => (
                <tr key={loss.id} className="border-b border-border/60 last:border-0">
                  <td className="py-1.5 pr-3 font-medium">{loss.claim_id}</td>
                  <td className="py-1.5 pr-3 text-muted-foreground">{loss.date_of_loss}</td>
                  <td className="py-1.5 pr-3 text-muted-foreground">{loss.cause_of_loss ?? "—"}</td>
                  <td className="py-1.5 pr-3 text-muted-foreground">{loss.location ?? "—"}</td>
                  <td className="py-1.5 pr-3 text-right text-muted-foreground">
                    {loss.gross_paid ? formatMoney(loss.gross_paid, loss.currency) : "—"}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-muted-foreground">
                    {loss.gross_case_reserve
                      ? formatMoney(loss.gross_case_reserve, loss.currency)
                      : "—"}
                  </td>
                  <td className="py-1.5 pr-3 text-right font-medium">
                    {formatMoney(loss.gross_incurred, loss.currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
