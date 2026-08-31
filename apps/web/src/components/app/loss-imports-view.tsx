"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileSpreadsheet, Upload } from "lucide-react";
import Link from "next/link";
import { type ChangeEvent, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BackLink, EmptyState, PageHeader } from "@/components/ui/page-header";
import { listLossImports } from "@/lib/api";
import { importStatus, uploadLossImportFile } from "@/lib/losses";

export function LossImportsView() {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const imports = useQuery({
    queryKey: ["loss-imports"],
    queryFn: async () => (await listLossImports({ throwOnError: true })).data.imports,
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const result = await uploadLossImportFile(file);
      if (!result.data) throw new Error("upload failed");
      return result.data;
    },
    onSuccess: () => {
      setError(null);
      if (fileRef.current) fileRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["loss-imports"] });
    },
    onError: () => setError("Upload failed. CSV only, up to 25 MB, with a header row."),
  });

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) upload.mutate(file);
  }

  return (
    <div className="space-y-6">
      <BackLink href="/loss-events">Loss events</BackLink>
      <PageHeader
        title="Import claims"
        description="Upload a claim schedule as CSV. Cedeon keeps the raw file and every row, you map the columns to canonical fields, and validated rows commit to an immutable claim record. No AI touches this pipeline."
      />

      <Card>
        <CardHeader>
          <CardTitle>Upload a claim CSV</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept="text/csv,.csv"
            onChange={onFileChange}
            className="hidden"
          />
          <Button onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
            <Upload /> {upload.isPending ? "Uploading…" : "Choose CSV"}
          </Button>
          {error ? <span className="text-sm text-danger">{error}</span> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Imports</CardTitle>
        </CardHeader>
        <CardContent>
          {imports.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : imports.data && imports.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">File</th>
                  <th className="py-2 font-medium">Rows</th>
                  <th className="py-2 font-medium">Valid</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {imports.data.map((imp) => {
                  const s = importStatus(imp.status);
                  return (
                    <tr key={imp.id} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5">
                        <Link
                          href={`/loss-imports/${imp.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {imp.original_filename}
                        </Link>
                      </td>
                      <td className="py-2.5 text-muted-foreground">{imp.row_count}</td>
                      <td className="py-2.5 text-muted-foreground">
                        {imp.report ? `${imp.report.committable} / ${imp.report.total_rows}` : "—"}
                      </td>
                      <td className="py-2.5">
                        <Badge tone={s.tone}>{s.label}</Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon={<FileSpreadsheet />}
              title="No imports yet"
              description="Upload a claim CSV to get started."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
