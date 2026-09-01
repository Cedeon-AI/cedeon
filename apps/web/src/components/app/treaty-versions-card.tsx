"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GitBranch } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import type { TreatyVersionSummary } from "@/lib/api";
import { asProblem, createTreatyVersion } from "@/lib/api";
import { versionStatus } from "@/lib/treaties";

export function TreatyVersionsCard({
  treatyId,
  versions,
  currentVersionId,
  currentStatus,
}: {
  treatyId: string;
  versions: TreatyVersionSummary[];
  currentVersionId: string | undefined;
  currentStatus: string | undefined;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const canOpenNew = currentStatus === "validated" || currentStatus === "active";
  const sorted = [...versions].sort((a, b) => b.version_no - a.version_no);

  const create = useMutation({
    mutationFn: async () => {
      const result = await createTreatyVersion({
        path: { treaty_id: treatyId },
        body: { note: note.trim(), source_document_id: null },
      });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      setError(null);
      setNote("");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["treaties", treatyId] });
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not open a new version."),
  });

  if (sorted.length <= 1 && !canOpenNew) return null;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Versions</CardTitle>
        {canOpenNew && !open ? (
          <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
            <GitBranch /> New version
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="divide-y divide-border/70 text-sm">
          {sorted.map((v) => {
            const st = versionStatus(v.status);
            return (
              <li key={v.id} className="flex items-center justify-between py-2">
                <span className="flex items-center gap-2">
                  <span className="font-mono text-xs text-muted-foreground">v{v.version_no}</span>
                  <Badge tone={st.tone}>{st.label}</Badge>
                  {v.id === currentVersionId ? (
                    <span className="text-xs text-muted-foreground">current</span>
                  ) : null}
                </span>
                {v.source_document_id ? (
                  <Link
                    href={`/documents/${v.source_document_id}`}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Source document →
                  </Link>
                ) : null}
              </li>
            );
          })}
        </ul>

        {open ? (
          <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-3">
            <p className="text-xs text-muted-foreground">
              An endorsement or revised wording opens a new version. The current terms, layers and
              participations copy forward — edit only what changed, then re-validate. Open
              recoveries against the old version are flagged for re-review.
            </p>
            <Field label="What changed" htmlFor="tv-note">
              <Input
                id="tv-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Endorsement 3 — revised occurrence limit"
              />
            </Field>
            {error ? <p className="text-sm text-danger">{error}</p> : null}
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => create.mutate()}
                disabled={create.isPending || !note.trim()}
              >
                {create.isPending ? "Opening…" : "Open new version"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
