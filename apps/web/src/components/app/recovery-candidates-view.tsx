"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, Sigma } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { EmptyState, PageHeader } from "@/components/ui/page-header";
import type { RecoveryCandidateStatus } from "@/lib/api";
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
      return data.candidates;
    },
  });

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

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Queue</CardTitle>
          <FilterTabs options={CANDIDATE_FILTERS} value={filter} onChange={setFilter} />
        </CardHeader>
        <CardContent>
          {candidates.data && candidates.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">Created</th>
                  <th className="py-2 font-medium">Gross event incurred</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {candidates.data.map((c) => {
                  const s = candidateStatus(c.status);
                  return (
                    <tr key={c.id} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5 text-muted-foreground">
                        {new Date(c.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-2.5">
                        {formatMoney(c.gross_event_incurred, c.currency)}
                        {c.currency_mismatch ? (
                          <Badge tone="warning">currency mismatch</Badge>
                        ) : null}
                      </td>
                      <td className="py-2.5">
                        <Badge tone={s.tone}>{s.label}</Badge>
                      </td>
                      <td className="py-2.5 text-right">
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
