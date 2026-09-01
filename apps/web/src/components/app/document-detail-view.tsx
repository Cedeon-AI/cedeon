"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { BackLink, PageHeader } from "@/components/ui/page-header";
import { getDocument, getDocumentChunks, getDocumentPages } from "@/lib/api";
import { isProcessing, statusLabel, statusTone } from "@/lib/documents";

export function DocumentDetailView({ documentId }: { documentId: string }) {
  const searchParams = useSearchParams();
  const [activePage, setActivePage] = useState(() => {
    const p = Number(searchParams.get("page"));
    return Number.isFinite(p) && p >= 1 ? p : 1;
  });

  const detail = useQuery({
    queryKey: ["documents", documentId],
    queryFn: async () => {
      const { data } = await getDocument({
        path: { document_id: documentId },
        throwOnError: true,
      });
      return data;
    },
    refetchInterval: (query) =>
      query.state.data && isProcessing(query.state.data.document.status) ? 2000 : false,
  });

  const parsed = detail.data?.document.status === "parsed";

  const pages = useQuery({
    queryKey: ["documents", documentId, "pages"],
    enabled: parsed,
    queryFn: async () => {
      const { data } = await getDocumentPages({
        path: { document_id: documentId },
        throwOnError: true,
      });
      return data.pages;
    },
  });

  const chunks = useQuery({
    queryKey: ["documents", documentId, "chunks"],
    enabled: parsed,
    queryFn: async () => {
      const { data } = await getDocumentChunks({
        path: { document_id: documentId },
        throwOnError: true,
      });
      return data.chunks;
    },
  });

  const doc = detail.data?.document;
  const page = pages.data?.find((p) => p.page_number === activePage) ?? pages.data?.[0];

  return (
    <div className="space-y-6">
      <BackLink href="/documents">Documents</BackLink>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            {doc?.original_filename ?? "Document"}
            {doc ? <Badge tone={statusTone(doc.status)}>{statusLabel(doc.status)}</Badge> : null}
          </span>
        }
        description={
          detail.data?.current_parse
            ? `Parsed with ${detail.data.current_parse.parser_name} ${detail.data.current_parse.parser_version} · ${detail.data.current_parse.page_count} pages`
            : undefined
        }
      />
      {doc?.status === "parse_failed" && detail.data?.current_parse?.error ? (
        <p className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {detail.data.current_parse.error}
        </p>
      ) : null}

      {!parsed ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {doc && isProcessing(doc.status)
              ? "Parsing in progress — this page updates automatically."
              : "No parse output available."}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Page text</CardTitle>
              {pages.data && pages.data.length > 1 ? (
                <FilterTabs
                  options={pages.data.map((p) => ({
                    label: String(p.page_number),
                    value: String(p.page_number),
                  }))}
                  value={String(page?.page_number ?? 1)}
                  onChange={(v) => setActivePage(Number(v))}
                />
              ) : null}
            </CardHeader>
            <CardContent>
              <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                {page?.text ?? "—"}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Chunks ({chunks.data?.length ?? 0})</CardTitle>
            </CardHeader>
            <CardContent className="max-h-[30rem] space-y-3 overflow-auto">
              {chunks.data?.map((chunk) => (
                <div key={chunk.ordinal} className="rounded-md border border-border p-3">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-mono">#{chunk.ordinal}</span>
                    <span>
                      p.{chunk.page_from}
                      {chunk.page_to !== chunk.page_from ? `–${chunk.page_to}` : ""}
                    </span>
                  </div>
                  {chunk.section_path ? (
                    <p className="mt-1 text-xs font-medium text-calculation">
                      {chunk.section_path}
                    </p>
                  ) : null}
                  <p className="mt-1.5 line-clamp-4 text-sm text-muted-foreground">{chunk.text}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
