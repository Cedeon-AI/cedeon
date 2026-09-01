"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { BackLink, PageHeader } from "@/components/ui/page-header";
import type { StatementLineOut } from "@/lib/api";
import { getReinsurerStatement, resolveStatementLine } from "@/lib/api";
import { formatMoney } from "@/lib/utils";

const KIND_LABEL: Record<string, string> = {
  clean: "Reconciles",
  no_match: "No match",
  currency_mismatch: "Currency mismatch",
  their_agreed_below_ours: "They agreed less than we recorded",
  their_agreed_above_ours: "They agreed more than we recorded",
  their_agreed_below_expected: "They agreed below the calculated figure",
  they_paid_short: "They paid less than we recorded collected",
  they_paid_over: "They paid more than we recorded collected",
};

export function StatementDetailView({ statementId }: { statementId: string }) {
  const queryClient = useQueryClient();
  const detail = useQuery({
    queryKey: ["reinsurer-statements", statementId],
    queryFn: async () =>
      (await getReinsurerStatement({ path: { statement_id: statementId }, throwOnError: true }))
        .data,
  });

  const resolve = useMutation({
    mutationFn: async (rowNumber: number) => {
      await resolveStatementLine({
        path: { statement_id: statementId, row_number: rowNumber },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reinsurer-statements"] });
    },
  });

  if (detail.isLoading || !detail.data) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  const s = detail.data;

  return (
    <div className="space-y-6">
      <BackLink href="/statements">Statements</BackLink>
      <PageHeader
        title={s.label}
        description={`${s.currency} · ${s.line_count} line${s.line_count === 1 ? "" : "s"} · ${
          s.open_discrepancies
        } open`}
      />

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-4 py-2.5 font-medium">Reinsurer</th>
                <th className="px-2 py-2.5 text-right font-medium">Their agreed</th>
                <th className="px-2 py-2.5 text-right font-medium">Their paid</th>
                <th className="px-2 py-2.5 font-medium">Finding</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {s.lines.map((line) => (
                <LineRow
                  key={line.row_number}
                  line={line}
                  currency={s.currency}
                  onResolve={() => resolve.mutate(line.row_number)}
                  resolving={resolve.isPending}
                />
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function LineRow({
  line,
  currency,
  onResolve,
  resolving,
}: {
  line: StatementLineOut;
  currency: string;
  onResolve: () => void;
  resolving: boolean;
}) {
  const top = line.findings[0];
  const clean = top?.kind === "clean";
  return (
    <tr className="border-b border-border/60 align-top last:border-0">
      <td className="px-4 py-2.5 font-medium">
        {line.reinsurer_name}
        {line.reference ? (
          <span className="ml-1.5 text-xs text-muted-foreground">{line.reference}</span>
        ) : null}
      </td>
      <td className="px-2 py-2.5 text-right font-mono text-xs">
        {line.their_agreed ? formatMoney(line.their_agreed, currency) : "—"}
      </td>
      <td className="px-2 py-2.5 text-right font-mono text-xs">
        {line.their_paid ? formatMoney(line.their_paid, currency) : "—"}
      </td>
      <td className="px-2 py-2.5">
        {line.findings.map((f) => (
          <div key={f.kind + f.text} className="mb-1 last:mb-0">
            <Badge tone={f.kind === "clean" ? "success" : "danger"}>
              {KIND_LABEL[f.kind] ?? f.kind}
            </Badge>
            {f.ours !== null && f.theirs !== null ? (
              <span className="ml-2 font-mono text-xs text-muted-foreground">
                ours {formatMoney(f.ours, currency)} · theirs {formatMoney(f.theirs, currency)}
              </span>
            ) : null}
          </div>
        ))}
      </td>
      <td className="px-4 py-2.5 text-right">
        {clean ? (
          <span className="text-xs text-muted-foreground">—</span>
        ) : line.resolved ? (
          <Badge tone="neutral">resolved</Badge>
        ) : (
          <Button size="sm" variant="ghost" onClick={onResolve} disabled={resolving}>
            Resolve
          </Button>
        )}
      </td>
    </tr>
  );
}
