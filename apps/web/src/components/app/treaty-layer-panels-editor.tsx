"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import type { LayerOut } from "@/lib/api";
import { asProblem, setLayerParticipations } from "@/lib/api";
import { formatMoney } from "@/lib/utils";

type PanelRow = { reinsurer_name: string; placed_share_percent: string };

function LayerPanel({
  treatyId,
  versionId,
  layer,
}: {
  treatyId: string;
  versionId: string;
  layer: LayerOut;
}) {
  const queryClient = useQueryClient();
  const seed: PanelRow[] =
    layer.participations.length > 0
      ? layer.participations.map((p) => ({
          reinsurer_name: p.reinsurer_name,
          placed_share_percent: String(Math.round(Number(p.placed_share) * 1000) / 10),
        }))
      : [{ reinsurer_name: "", placed_share_percent: "" }];
  const [rows, setRows] = useState<PanelRow[]>(seed);
  const [open, setOpen] = useState(layer.participations.length > 0);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = useMutation({
    mutationFn: async (clear: boolean) => {
      const panel = clear
        ? []
        : rows
            .filter((r) => r.reinsurer_name.trim() !== "" && r.placed_share_percent.trim() !== "")
            .map((r) => ({
              reinsurer_name: r.reinsurer_name.trim(),
              placed_share_percent: r.placed_share_percent.trim(),
            }));
      const result = await setLayerParticipations({
        path: { treaty_id: treatyId, version_id: versionId, layer_no: layer.layer_no },
        body: { panel },
      });
      if (result.error) throw result.error;
      return clear;
    },
    onSuccess: (cleared) => {
      setError(null);
      setSaved(true);
      if (cleared) {
        setRows([{ reinsurer_name: "", placed_share_percent: "" }]);
        setOpen(false);
      }
      queryClient.invalidateQueries({ queryKey: ["treaties", treatyId] });
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not save the layer panel."),
  });

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">
          <span className="mr-2 font-mono text-xs text-muted-foreground">L{layer.layer_no}</span>
          {formatMoney(layer.limit, layer.currency)} xs{" "}
          {formatMoney(layer.attachment, layer.currency)}
        </p>
        {!open ? (
          <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
            Give this layer its own panel
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">overrides the programme panel</span>
        )}
      </div>

      {open ? (
        <div className="mt-3 space-y-2">
          {rows.map((row, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: positional rows
            <div key={i} className="flex items-center gap-2">
              <Input
                aria-label={`Reinsurer ${i + 1}`}
                value={row.reinsurer_name}
                placeholder="Reinsurer name"
                onChange={(e) => {
                  const v = e.target.value;
                  setRows((r) => r.map((x, j) => (j === i ? { ...x, reinsurer_name: v } : x)));
                  setSaved(false);
                }}
              />
              <Input
                aria-label={`Share percent ${i + 1}`}
                className="w-24"
                inputMode="decimal"
                value={row.placed_share_percent}
                placeholder="%"
                onChange={(e) => {
                  const v = e.target.value;
                  setRows((r) =>
                    r.map((x, j) => (j === i ? { ...x, placed_share_percent: v } : x)),
                  );
                  setSaved(false);
                }}
              />
              {rows.length > 1 ? (
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Remove row ${i + 1}`}
                  onClick={() => setRows((r) => r.filter((_, j) => j !== i))}
                >
                  <X />
                </Button>
              ) : null}
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                setRows((r) => [...r, { reinsurer_name: "", placed_share_percent: "" }])
              }
            >
              <Plus /> Reinsurer
            </Button>
            <Button size="sm" onClick={() => save.mutate(false)} disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save panel"}
            </Button>
            {layer.participations.length > 0 ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => save.mutate(true)}
                disabled={save.isPending}
              >
                Clear (use programme panel)
              </Button>
            ) : null}
            {saved ? <span className="text-xs text-human">Saved.</span> : null}
            {error ? <span className="text-sm text-danger">{error}</span> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function TreatyLayerPanelsEditor({
  treatyId,
  versionId,
  layers,
}: {
  treatyId: string;
  versionId: string;
  layers: LayerOut[];
}) {
  if (layers.length < 2) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Layer panels</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          By default every layer is placed with the programme panel below. Give a layer its own
          panel when it was placed with a different market. Editable until the treaty is validated.
        </p>
        {[...layers]
          .sort((a, b) => a.layer_no - b.layer_no)
          .map((layer) => (
            <LayerPanel
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
