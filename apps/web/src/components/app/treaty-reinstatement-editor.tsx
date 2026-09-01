"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import type { LayerOut } from "@/lib/api";
import { asProblem, setLayerReinstatementTerms } from "@/lib/api";
import { formatMoney } from "@/lib/utils";

function LayerReinstatement({
  treatyId,
  versionId,
  layer,
}: {
  treatyId: string;
  versionId: string;
  layer: LayerOut;
}) {
  const queryClient = useQueryClient();
  const [deposit, setDeposit] = useState(layer.deposit_premium ?? "");
  const [rates, setRates] = useState((layer.reinstatement_rates ?? []).join(", "));
  const [basis, setBasis] = useState(layer.reinstatement_basis ?? "flat");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = useMutation({
    mutationFn: async (clear: boolean) => {
      const parsed = clear
        ? []
        : rates
            .split(/[,\s]+/)
            .map((s) => s.trim())
            .filter(Boolean);
      const result = await setLayerReinstatementTerms({
        path: { treaty_id: treatyId, version_id: versionId, layer_no: layer.layer_no },
        body: {
          deposit_premium: clear || !deposit.trim() ? null : deposit.trim(),
          rates: parsed,
          basis,
        },
      });
      if (result.error) throw result.error;
      return clear;
    },
    onSuccess: (cleared) => {
      setError(null);
      setSaved(true);
      if (cleared) {
        setDeposit("");
        setRates("");
      }
      queryClient.invalidateQueries({ queryKey: ["treaties", treatyId] });
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not save the reinstatement terms."),
  });

  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-sm font-medium">
        <span className="mr-2 font-mono text-xs text-muted-foreground">L{layer.layer_no}</span>
        {formatMoney(layer.limit, layer.currency)} xs{" "}
        {formatMoney(layer.attachment, layer.currency)}
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <Field label="Deposit premium" htmlFor={`rp-dep-${layer.layer_no}`}>
          <Input
            id={`rp-dep-${layer.layer_no}`}
            inputMode="numeric"
            value={deposit}
            placeholder="2000000"
            onChange={(e) => {
              setDeposit(e.target.value);
              setSaved(false);
            }}
          />
        </Field>
        <Field label="Rates (per reinstatement)" htmlFor={`rp-rates-${layer.layer_no}`}>
          <Input
            id={`rp-rates-${layer.layer_no}`}
            value={rates}
            placeholder="1, 1"
            onChange={(e) => {
              setRates(e.target.value);
              setSaved(false);
            }}
          />
        </Field>
        <Field label="Basis" htmlFor={`rp-basis-${layer.layer_no}`}>
          <select
            id={`rp-basis-${layer.layer_no}`}
            value={basis}
            onChange={(e) => {
              setBasis(e.target.value);
              setSaved(false);
            }}
            className="h-9 rounded-md border border-border bg-background px-2 text-sm"
          >
            <option value="flat">Flat</option>
            <option value="pro_rata_time">Pro-rata as to time</option>
          </select>
        </Field>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => save.mutate(false)} disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save"}
        </Button>
        {layer.reinstatement_rates && layer.reinstatement_rates.length > 0 ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => save.mutate(true)}
            disabled={save.isPending}
          >
            Clear
          </Button>
        ) : null}
        {saved ? <span className="text-xs text-human">Saved.</span> : null}
        {error ? <span className="text-sm text-danger">{error}</span> : null}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Rates are per reinstatement — <span className="font-mono">1</span> = at 100%,{" "}
        <span className="font-mono">0</span> = free. One value per reinstatement, e.g.{" "}
        <span className="font-mono">1, 1</span> for two reinstatements at 100%.
      </p>
    </div>
  );
}

export function TreatyReinstatementEditor({
  treatyId,
  versionId,
  layers,
}: {
  treatyId: string;
  versionId: string;
  layers: LayerOut[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Reinstatement terms</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          The deposit premium and reinstatement rates a human validated. When a loss erodes the
          layer, Cedeon computes the reinstatement premium due — deterministically, never an LLM.
          Editable until the treaty is validated.
        </p>
        {[...layers]
          .sort((a, b) => a.layer_no - b.layer_no)
          .map((layer) => (
            <LayerReinstatement
              key={layer.layer_no}
              treatyId={treatyId}
              versionId={versionId}
              layer={layer}
            />
          ))}
      </CardContent>
    </Card>
  );
}
