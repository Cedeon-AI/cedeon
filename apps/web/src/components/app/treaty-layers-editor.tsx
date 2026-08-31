"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import type { LayerOut } from "@/lib/api";
import { asProblem, setTreatyLayers } from "@/lib/api";

type Row = { attachment: string; limit: string };

export function TreatyLayersEditor({
  treatyId,
  versionId,
  currency,
  existing,
}: {
  treatyId: string;
  versionId: string;
  currency: string | null;
  existing: LayerOut[];
}) {
  const queryClient = useQueryClient();
  const seed: Row[] =
    existing.length > 0
      ? [...existing]
          .sort((a, b) => a.layer_no - b.layer_no)
          .map((l) => ({ attachment: l.attachment, limit: l.limit }))
      : [{ attachment: "", limit: "" }];
  const [rows, setRows] = useState<Row[]>(seed);
  const [ccy, setCcy] = useState(currency ?? "USD");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const set = (i: number, patch: Partial<Row>) => {
    setRows((r) => r.map((row, j) => (j === i ? { ...row, ...patch } : row)));
    setSaved(false);
  };

  const save = useMutation({
    mutationFn: async () => {
      const layers = rows
        .filter((r) => r.attachment.trim() !== "" && r.limit.trim() !== "")
        .map((r) => ({ attachment: r.attachment.trim(), limit: r.limit.trim() }));
      const result = await setTreatyLayers({
        path: { treaty_id: treatyId, version_id: versionId },
        body: { currency: ccy.trim().toUpperCase() || null, layers },
      });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      setError(null);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["treaties", treatyId] });
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not save the layer stack."),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Layer stack</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          One row per XOL layer, bottom to top. A single event opens a recovery on every layer it
          pierces. Editable until the treaty is validated.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Currency" htmlFor="ls-ccy">
            <Input
              id="ls-ccy"
              value={ccy}
              maxLength={3}
              onChange={(e) => {
                setCcy(e.target.value);
                setSaved(false);
              }}
              className="w-24 uppercase"
            />
          </Field>
        </div>
        <div className="space-y-2">
          {rows.map((row, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: rows are positional
            <div key={i} className="flex items-end gap-2">
              <span className="pb-2 font-mono text-xs text-muted-foreground">L{i + 1}</span>
              <Field label={i === 0 ? "Limit" : ""} htmlFor={`ls-limit-${i}`}>
                <Input
                  id={`ls-limit-${i}`}
                  inputMode="numeric"
                  value={row.limit}
                  onChange={(e) => set(i, { limit: e.target.value })}
                  placeholder="20000000"
                />
              </Field>
              <span className="pb-2 text-xs text-muted-foreground">xs</span>
              <Field label={i === 0 ? "Attachment" : ""} htmlFor={`ls-att-${i}`}>
                <Input
                  id={`ls-att-${i}`}
                  inputMode="numeric"
                  value={row.attachment}
                  onChange={(e) => set(i, { attachment: e.target.value })}
                  placeholder="50000000"
                />
              </Field>
              {rows.length > 1 ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setRows((r) => r.filter((_, j) => j !== i));
                    setSaved(false);
                  }}
                  aria-label={`Remove layer ${i + 1}`}
                >
                  <X />
                </Button>
              ) : null}
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setRows((r) => [...r, { attachment: "", limit: "" }]);
              setSaved(false);
            }}
          >
            <Plus /> Add a layer
          </Button>
          <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save layer stack"}
          </Button>
          {saved ? <span className="text-xs text-human">Saved.</span> : null}
          {error ? <span className="text-sm text-danger">{error}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}
