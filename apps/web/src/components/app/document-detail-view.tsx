"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getDocument, getDocumentChunks, getDocumentPages } from "@/lib/api";
import { isProcessing, statusLabel, statusTone } from "@/lib/documents";

export function DocumentDetailView({ documentId }: { documentId: string }) {
  const [activePage, setActivePage] = useState(1);

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
      <div>
        <Link href="/documents" className="text-sm text-muted-foreground hover:underline">
          ← Documents
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">
            {doc?.original_filename ?? "Document"}
          </h1>
          {doc ? <Badge tone={statusTone(doc.status)}>{statusLabel(doc.status)}</Badge> : null}
        </div>
        {detail.data?.current_parse ? (
          <p className="mt-1 text-sm text-muted-foreground">
            Parsed with {detail.data.current_parse.parser_name}{" "}
            {detail.data.current_parse.parser_version} · {detail.data.current_parse.page_count}{" "}
            pages
          </p>
        ) : null}
        {doc?.status === "parse_failed" && detail.data?.current_parse?.error ? (
          <p className="mt-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
            {detail.data.current_parse.error}
          </p>
        ) : null}
      </div>

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
                <div className="flex items-center gap-1 text-xs">
                  {pages.data.map((p) => (
                    <button
                      key={p.page_number}
                      type="button"
                      onClick={() => setActivePage(p.page_number)}
                      className={
                        p.page_number === (page?.page_number ?? 1)
                          ? "rounded bg-primary px-2 py-1 text-primary-foreground"
                          : "rounded px-2 py-1 text-muted-foreground hover:bg-muted"
                      }
                    >
                      {p.page_number}
                    </button>
                  ))}
                </div>
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
