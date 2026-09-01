"use client";

import { useQuery } from "@tanstack/react-query";
import { Layers, Plus, Sigma } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { EmptyState, PageHeader } from "@/components/ui/page-header";
import type { RecoveryCandidateOut, RecoveryCandidateStatus, RecoveryProgramme } from "@/lib/api";
import { listRecoveryCandidates } from "@/lib/api";
import { CANDIDATE_FILTERS, candidateStatus } from "@/lib/recoveries";
import { formatMoney } from "@/lib/utils";

export function RecoveryCandidatesView() {
  const [filter, setFilter] = useState<RecoveryCandidateStatus | "">("");

  const candidates = useQuery({
    queryKey: ["recovery-candidates", filter],
    queryFn: async () => {
      const { data } = await listRecoveryCandidates({
        query: filter ? { status: filter } : undefined,
        throwOnError: true,
      });
      return data;
    },
  });

  const rows = candidates.data?.candidates ?? [];
  const programmes = candidates.data?.programmes ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Recoveries"
        description="A validated treaty plus a loss event, run through the deterministic engine. The number is code, not an LLM — you review and confirm it."
        actions={
          <Button asChild size="sm">
            <Link href="/recovery-candidates/new">
              <Plus /> Start a recovery
            </Link>
          </Button>
        }
      />

      {programmes.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Programmes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              One loss, several layers of the same tower. Each layer is its own reviewable recovery.
            </p>
            {programmes.map((p) => (
              <ProgrammeCard key={`${p.treaty_version_id}-${p.loss_event_id}`} programme={p} />
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Queue</CardTitle>
          <FilterTabs options={CANDIDATE_FILTERS} value={filter} onChange={setFilter} />
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {rows.length > 0 ? (
            <table className="w-full min-w-192 text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-4 py-2.5 font-medium">Treaty</th>
                  <th className="px-2 py-2.5 font-medium">Event</th>
                  <th className="px-2 py-2.5 font-medium">Layer</th>
                  <th className="px-2 py-2.5 text-right font-medium">Recovery</th>
                  <th className="px-2 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => {
                  const s = candidateStatus(c.status);
                  return (
                    <tr key={c.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2.5 font-medium">
                        {c.treaty_name ?? "—"}
                        {c.currency_mismatch ? (
                          <Badge tone="warning">currency mismatch</Badge>
                        ) : null}
                      </td>
                      <td className="px-2 py-2.5 text-muted-foreground">
                        {c.loss_event_name ?? "—"}
                      </td>
                      <td className="px-2 py-2.5 text-muted-foreground">
                        {c.layer_no ? `L${c.layer_no}` : "—"}
                      </td>
                      <td className="px-2 py-2.5 text-right font-mono text-xs">
                        {c.layer_recovery
                          ? formatMoney(c.layer_recovery, c.currency)
                          : formatMoney(c.gross_event_incurred, c.currency)}
                      </td>
                      <td className="px-2 py-2.5">
                        <Badge tone={s.tone}>{s.label}</Badge>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Link
                          href={`/recovery-candidates/${c.id}`}
                          className="text-sm font-medium text-primary hover:underline"
                        >
                          Open →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon={<Sigma />}
              title="No recoveries in this view"
              description="Start a recovery — pick a loss event and the treaty that responds."
              action={
                <Button asChild size="sm" variant="secondary">
                  <Link href="/recovery-candidates/new">Start a recovery</Link>
                </Button>
              }
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ProgrammeCard({ programme }: { programme: RecoveryProgramme }) {
  const total = programme.candidates.reduce((sum, c) => sum + Number(c.layer_recovery ?? 0), 0);
  return (
    <div className="rounded-xl border border-border">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/70 px-4 py-2.5">
        <span className="flex items-center gap-2 text-sm font-semibold">
          <Layers className="size-4 text-muted-foreground" />
          {programme.treaty_name ?? "Treaty"} · {programme.loss_event_name ?? "Event"}
        </span>
        <span className="font-mono text-xs text-muted-foreground">
          {formatMoney(String(total), programme.currency)} across {programme.candidates.length}{" "}
          layers
        </span>
      </div>
      <ul className="divide-y divide-border/70">
        {programme.candidates.map((c) => (
          <ProgrammeRow key={c.id} candidate={c} />
        ))}
      </ul>
    </div>
  );
}

function ProgrammeRow({ candidate: c }: { candidate: RecoveryCandidateOut }) {
  const s = candidateStatus(c.status);
  return (
    <li>
      <Link
        href={`/recovery-candidates/${c.id}`}
        className="flex items-center gap-3 px-4 py-2.5 transition hover:bg-muted/50"
      >
        <span className="w-8 shrink-0 font-mono text-xs text-muted-foreground">L{c.layer_no}</span>
        <span className="min-w-0 flex-1 text-sm">
          {c.layer_limit && c.layer_attachment ? (
            <span className="text-muted-foreground">
              {formatMoney(c.layer_limit, c.currency)} xs{" "}
              {formatMoney(c.layer_attachment, c.currency)}
            </span>
          ) : null}
        </span>
        <span className="shrink-0 font-mono text-xs tabular-nums">
          {c.layer_recovery ? formatMoney(c.layer_recovery, c.currency) : "—"}
        </span>
        <Badge tone={s.tone}>{s.label}</Badge>
      </Link>
    </li>
  );
}
