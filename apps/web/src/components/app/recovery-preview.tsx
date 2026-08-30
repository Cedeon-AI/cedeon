"use client";

import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import { previewRecovery } from "@/lib/api";
import { formatShare } from "@/lib/treaties";
import { formatMoney } from "@/lib/utils";

export function RecoveryPreview({ treatyId }: { treatyId: string }) {
  const [gross, setGross] = useState("58700000.00");

  const preview = useMutation({
    mutationFn: async () => {
      const { data } = await previewRecovery({
        path: { treaty_id: treatyId },
        body: { gross_loss: gross },
        throwOnError: true,
      });
      return data;
    },
  });

  const r = preview.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recovery preview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Deterministic — the versioned engine, not an LLM. Nothing is saved.
        </p>
        <form
          className="flex items-end gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            preview.mutate();
          }}
        >
          <Field label="Gross event incurred" htmlFor="gross">
            <Input id="gross" value={gross} onChange={(e) => setGross(e.target.value)} />
          </Field>
          <Button type="submit" disabled={preview.isPending}>
            {preview.isPending ? "Computing…" : "Compute"}
          </Button>
        </form>

        {preview.isError ? (
          <p className="text-sm text-danger">
            Could not compute — the treaty must be validated first.
          </p>
        ) : null}

        {r ? (
          <div className="space-y-3">
            <div className="rounded-md border border-calculation/30 bg-calculation/5 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-calculation">
                Calculation
              </p>
              <p className="mt-1 text-2xl font-semibold tracking-tight">
                {formatMoney(r.layer_recovery, r.currency)}
              </p>
              <p className="text-xs text-muted-foreground">
                layer recovery · engine {r.engine_version}
              </p>
            </div>

            <ol className="space-y-1 text-sm">
              {r.trace.map((step) => (
                <li key={step.label} className="flex justify-between gap-4">
                  <span className="text-muted-foreground">{step.label}</span>
                  <span className="font-mono text-xs">
                    {step.expression} = {step.result}
                  </span>
                </li>
              ))}
            </ol>

            {r.allocations.length > 0 ? (
              <table className="w-full text-sm">
                <tbody>
                  {r.allocations.map((a) => (
                    <tr key={a.reinsurer_id} className="border-t border-border/60">
                      <td className="py-1.5">{a.reinsurer_name}</td>
                      <td className="py-1.5 text-muted-foreground">{formatShare(a.share)}</td>
                      <td className="py-1.5 text-right font-medium">
                        {formatMoney(a.amount, r.currency)}
                      </td>
                    </tr>
                  ))}
                  {Number(r.cedent_retention) > 0 ? (
                    <tr className="border-t border-border/60 text-muted-foreground">
                      <td className="py-1.5">Cedent retention</td>
                      <td />
                      <td className="py-1.5 text-right">
                        {formatMoney(r.cedent_retention, r.currency)}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
