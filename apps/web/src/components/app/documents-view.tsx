"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Upload } from "lucide-react";
import Link from "next/link";
import { type ChangeEvent, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { EmptyState, PageHeader } from "@/components/ui/page-header";
import { type DocumentKind, listDocuments } from "@/lib/api";
import { isProcessing, statusLabel, statusTone, uploadDocumentFile } from "@/lib/documents";

const KINDS: DocumentKind[] = [
  "treaty",
  "endorsement",
  "slip",
  "loss_advice",
  "correspondence",
  "other",
];

export function DocumentsView() {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<DocumentKind>("treaty");
  const [error, setError] = useState<string | null>(null);

  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: async () => {
      const { data } = await listDocuments({ throwOnError: true });
      return data.documents;
    },
    refetchInterval: (query) =>
      (query.state.data ?? []).some((d) => isProcessing(d.status)) ? 2000 : false,
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const result = await uploadDocumentFile(file, kind);
      if (!result.data) throw new Error("upload failed");
      return result.data;
    },
    onSuccess: () => {
      setError(null);
      if (fileRef.current) fileRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: () => setError("Upload failed. PDFs only, up to 50 MB."),
  });

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) upload.mutate(file);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Documents"
        description="Upload treaty PDFs. Cedeon parses them into pages and clause-aware chunks — the evidence base for term extraction."
      />

      <Card>
        <CardHeader>
          <CardTitle>Upload a document</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Select
            value={kind}
            onChange={(e) => setKind(e.target.value as DocumentKind)}
            className="w-auto capitalize"
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k.replace("_", " ")}
              </option>
            ))}
          </Select>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={onFileChange}
            className="hidden"
          />
          <Button onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
            <Upload /> {upload.isPending ? "Uploading…" : "Choose PDF"}
          </Button>
          {error ? <span className="text-sm text-danger">{error}</span> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Library</CardTitle>
        </CardHeader>
        <CardContent>
          {documents.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : documents.data && documents.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">File</th>
                  <th className="py-2 font-medium">Kind</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium">Size</th>
                </tr>
              </thead>
              <tbody>
                {documents.data.map((doc) => (
                  <tr key={doc.id} className="border-b border-border/60 last:border-0">
                    <td className="py-2.5">
                      <Link
                        href={`/documents/${doc.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {doc.original_filename}
                      </Link>
                    </td>
                    <td className="py-2.5 capitalize text-muted-foreground">
                      {doc.kind.replace("_", " ")}
                    </td>
                    <td className="py-2.5">
                      <Badge tone={statusTone(doc.status)}>{statusLabel(doc.status)}</Badge>
                    </td>
                    <td className="py-2.5 text-muted-foreground">
                      {(doc.byte_size / 1024).toFixed(0)} KB
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon={<FileText />}
              title="No documents yet"
              description="Upload a treaty PDF to get started."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
