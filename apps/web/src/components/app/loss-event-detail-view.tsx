"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BackLink, PageHeader } from "@/components/ui/page-header";
import { getLossEvent } from "@/lib/api";
import { formatMoney } from "@/lib/utils";

export function LossEventDetailView({ eventId }: { eventId: string }) {
  const detail = useQuery({
    queryKey: ["loss-events", eventId],
    queryFn: async () =>
      (await getLossEvent({ path: { event_id: eventId }, throwOnError: true })).data,
  });

  if (detail.isLoading || !detail.data) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  const { event, losses } = detail.data;

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
      />

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
