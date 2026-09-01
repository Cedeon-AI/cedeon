"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Scale, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import { EmptyState, PageHeader } from "@/components/ui/page-header";
import { asProblem, createReinsurerStatement, listReinsurerStatements } from "@/lib/api";

type LineDraft = {
  reinsurer_name: string;
  reference: string;
  their_agreed: string;
  their_paid: string;
};

const emptyLine: LineDraft = {
  reinsurer_name: "",
  reference: "",
  their_agreed: "",
  their_paid: "",
};

export function StatementsView() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [lines, setLines] = useState<LineDraft[]>([{ ...emptyLine }]);
  const [error, setError] = useState<string | null>(null);

  const statements = useQuery({
    queryKey: ["reinsurer-statements"],
    queryFn: async () => (await listReinsurerStatements({ throwOnError: true })).data.statements,
  });

  const create = useMutation({
    mutationFn: async () => {
      const body = {
        label: label.trim(),
        currency: currency.trim().toUpperCase(),
        lines: lines
          .filter((l) => l.reinsurer_name.trim() !== "")
          .map((l) => ({
            reinsurer_name: l.reinsurer_name.trim(),
            reference: l.reference.trim() || null,
            their_agreed: l.their_agreed.trim() || null,
            their_paid: l.their_paid.trim() || null,
          })),
      };
      const result = await createReinsurerStatement({ body });
      if (result.error) throw result.error;
      return result.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["reinsurer-statements"] });
      if (data) router.push(`/statements/${data.id}`);
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not reconcile the statement."),
  });

  const rows = statements.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reinsurer statements"
        description="Enter the figures a reinsurer stated — agreed, paid — and Cedeon reconciles each line against what it holds."
        actions={
          <Button size="sm" onClick={() => setOpen((v) => !v)}>
            <Plus /> New statement
          </Button>
        }
      />

      {open ? (
        <Card>
          <CardHeader>
            <CardTitle>Reconcile a statement</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-3">
              <Field label="Label" htmlFor="st-label">
                <Input
                  id="st-label"
                  value={label}
                  placeholder="Reinsurer Alpha — Q3 account"
                  onChange={(e) => setLabel(e.target.value)}
                />
              </Field>
              <Field label="Currency" htmlFor="st-ccy">
                <Input
                  id="st-ccy"
                  value={currency}
                  maxLength={3}
                  className="w-24 uppercase"
                  onChange={(e) => setCurrency(e.target.value)}
                />
              </Field>
            </div>
            <div className="space-y-2">
              {lines.map((line, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: positional rows
                <div key={i} className="flex flex-wrap items-end gap-2">
                  <Field label={i === 0 ? "Reinsurer" : ""} htmlFor={`st-r-${i}`}>
                    <Input
                      id={`st-r-${i}`}
                      value={line.reinsurer_name}
                      placeholder="Reinsurer Alpha"
                      onChange={(e) =>
                        setLines((r) =>
                          r.map((x, j) => (j === i ? { ...x, reinsurer_name: e.target.value } : x)),
                        )
                      }
                    />
                  </Field>
                  <Field label={i === 0 ? "Reference (optional)" : ""} htmlFor={`st-ref-${i}`}>
                    <Input
                      id={`st-ref-${i}`}
                      value={line.reference}
                      placeholder="recovery / claim ref"
                      onChange={(e) =>
                        setLines((r) =>
                          r.map((x, j) => (j === i ? { ...x, reference: e.target.value } : x)),
                        )
                      }
                    />
                  </Field>
                  <Field label={i === 0 ? "Their agreed" : ""} htmlFor={`st-a-${i}`}>
                    <Input
                      id={`st-a-${i}`}
                      className="w-32"
                      inputMode="decimal"
                      value={line.their_agreed}
                      onChange={(e) =>
                        setLines((r) =>
                          r.map((x, j) => (j === i ? { ...x, their_agreed: e.target.value } : x)),
                        )
                      }
                    />
                  </Field>
                  <Field label={i === 0 ? "Their paid" : ""} htmlFor={`st-p-${i}`}>
                    <Input
                      id={`st-p-${i}`}
                      className="w-32"
                      inputMode="decimal"
                      value={line.their_paid}
                      onChange={(e) =>
                        setLines((r) =>
                          r.map((x, j) => (j === i ? { ...x, their_paid: e.target.value } : x)),
                        )
                      }
                    />
                  </Field>
                  {lines.length > 1 ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={`Remove line ${i + 1}`}
                      onClick={() => setLines((r) => r.filter((_, j) => j !== i))}
                    >
                      <X />
                    </Button>
                  ) : null}
                </div>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setLines((r) => [...r, { ...emptyLine }])}
              >
                <Plus /> Line
              </Button>
              <Button size="sm" onClick={() => create.mutate()} disabled={create.isPending}>
                {create.isPending ? "Reconciling…" : "Reconcile"}
              </Button>
              {error ? <span className="text-sm text-danger">{error}</span> : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {rows.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-4 py-2.5 font-medium">Statement</th>
                  <th className="px-2 py-2.5 font-medium">Lines</th>
                  <th className="px-2 py-2.5 font-medium">Open</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-2.5 font-medium">
                      {s.label}
                      <span className="ml-2 text-xs text-muted-foreground">
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td className="px-2 py-2.5 text-muted-foreground">{s.line_count}</td>
                    <td className="px-2 py-2.5">
                      {s.open_discrepancies > 0 ? (
                        <Badge tone="danger">{s.open_discrepancies}</Badge>
                      ) : (
                        <Badge tone="success">clean</Badge>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Link
                        href={`/statements/${s.id}`}
                        className="text-sm font-medium text-primary hover:underline"
                      >
                        Open →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          icon={<Scale />}
          title="No statements yet"
          description="Reconcile a reinsurer's stated figures against Cedeon's — new statement."
        />
      )}
    </div>
  );
}
