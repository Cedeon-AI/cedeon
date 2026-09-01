"use client";

import { useQuery } from "@tanstack/react-query";
import { Wallet } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { EmptyState, PageHeader, Stat } from "@/components/ui/page-header";
import type { RecoverableStatus } from "@/lib/api";
import { getRecoverablesSummary, listRecoverables } from "@/lib/api";
import { AGING_LABEL, recoverableStatus } from "@/lib/collection";
import { formatMoney } from "@/lib/utils";

const FILTERS: { label: string; value: RecoverableStatus | "" | "overdue" }[] = [
  { label: "All", value: "" },
  { label: "Overdue", value: "overdue" },
  { label: "Notified", value: "notified" },
  { label: "Agreed", value: "agreed" },
  { label: "Billed", value: "billed" },
  { label: "Disputed", value: "disputed" },
  { label: "Collected", value: "collected" },
];

const AGING_ORDER = ["current", "1_30", "31_60", "61_90", "90_plus"] as const;

export function RecoverablesView() {
  const [filter, setFilter] = useState<RecoverableStatus | "" | "overdue">("");

  const summary = useQuery({
    queryKey: ["recoverables", "summary"],
    queryFn: async () => (await getRecoverablesSummary({ throwOnError: true })).data,
  });

  const list = useQuery({
    queryKey: ["recoverables", "portfolio", filter],
    queryFn: async () => {
      const status = filter && filter !== "overdue" ? filter : undefined;
      return (
        await listRecoverables({ query: status ? { status } : undefined, throwOnError: true })
      ).data.recoverables;
    },
  });

  const rows = (list.data ?? [])
    .filter((r) => (filter === "overdue" ? r.days_overdue > 0 : true))
    .sort(
      (a, b) => b.days_overdue - a.days_overdue || Number(b.outstanding) - Number(a.outstanding),
    );

  const s = summary.data;
  const currency = s?.currency ?? "USD";
  const maxAging = s ? Math.max(...Object.values(s.by_aging).map(Number), 1) : 1;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Recoverables"
        description="Every reinsurer's leg of every confirmed recovery — what is expected, what is collected, and how overdue the rest is."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Open recoverable"
          value={s ? formatMoney(s.total_outstanding, currency) : "—"}
          icon={<Wallet />}
          tone="calculation"
        />
        <Stat
          label="Collected"
          value={s ? formatMoney(s.total_collected, currency) : "—"}
          tone="human"
        />
        <Stat
          label="Overdue"
          value={s ? formatMoney(s.overdue_outstanding, currency) : "—"}
          hint={s && s.overdue_count > 0 ? `${s.overdue_count} legs` : "none overdue"}
          tone="fact"
        />
        <Stat label="Legs tracked" value={s ? String(s.count) : "—"} tone="fact" />
      </div>

      {s && s.count > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Aging of what's outstanding</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {AGING_ORDER.map((bucket) => {
              const amount = Number(s.by_aging[bucket] ?? 0);
              return (
                <div key={bucket} className="flex items-center gap-3 text-sm">
                  <span className="w-24 shrink-0 text-muted-foreground">{AGING_LABEL[bucket]}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className={
                        bucket === "current"
                          ? "h-full rounded-full bg-calculation/60"
                          : "h-full rounded-full bg-warning/70"
                      }
                      style={{ width: `${(amount / maxAging) * 100}%` }}
                    />
                  </div>
                  <span className="w-32 shrink-0 text-right font-mono text-xs">
                    {formatMoney(amount, currency)}
                  </span>
                </div>
              );
            })}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Legs</CardTitle>
          <FilterTabs options={FILTERS} value={filter} onChange={setFilter} />
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {list.isLoading ? (
            <p className="p-5 text-sm text-muted-foreground">Loading…</p>
          ) : rows.length === 0 ? (
            <EmptyState
              icon={<Wallet />}
              title="Nothing here"
              description="Confirm a recovery and start collection tracking to see recoverables."
            />
          ) : (
            <table className="w-full min-w-192 text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-4 py-2.5 font-medium">Reinsurer</th>
                  <th className="px-2 py-2.5 font-medium">Status</th>
                  <th className="px-2 py-2.5 text-right font-medium">Expected</th>
                  <th className="px-2 py-2.5 text-right font-medium">Outstanding</th>
                  <th className="px-2 py-2.5 font-medium">Due</th>
                  <th className="px-2 py-2.5 font-medium">Next</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const st = recoverableStatus(r.status);
                  return (
                    <tr key={r.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2.5 font-medium">
                        {r.reinsurer_name}
                        {r.reconciliation.length > 0 ? (
                          <span
                            className="ml-1.5 align-middle text-danger"
                            title={r.reconciliation.map((f) => f.text).join("\n")}
                          >
                            ⚠
                          </span>
                        ) : null}
                      </td>
                      <td className="px-2 py-2.5">
                        <Badge tone={st.tone}>{st.label}</Badge>
                      </td>
                      <td className="px-2 py-2.5 text-right font-mono text-xs">
                        {formatMoney(r.expected_amount, r.currency)}
                      </td>
                      <td className="px-2 py-2.5 text-right font-mono text-xs">
                        {formatMoney(r.outstanding, r.currency)}
                      </td>
                      <td className="px-2 py-2.5 text-xs">
                        {r.due_date ? (
                          <span
                            className={r.days_overdue > 0 ? "text-danger" : "text-muted-foreground"}
                          >
                            {r.due_date}
                            {r.days_overdue > 0 ? ` · ${r.days_overdue}d` : ""}
                          </span>
                        ) : (
                          <span className="text-muted-foreground/50">—</span>
                        )}
                      </td>
                      <td className="px-2 py-2.5 text-xs">
                        <span
                          className={r.next_action_urgent ? "text-danger" : "text-muted-foreground"}
                        >
                          {r.next_action_text}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Link
                          href={`/recovery-candidates/${r.recovery_candidate_id}?section=collection`}
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
          )}
        </CardContent>
      </Card>
    </div>
  );
}
