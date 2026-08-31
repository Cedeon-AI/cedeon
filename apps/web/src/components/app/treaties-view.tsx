"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ScrollText } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/field";
import { EmptyState, PageHeader } from "@/components/ui/page-header";
import { createTreaty, listDocuments, listPrograms, listTreaties } from "@/lib/api";
import { isBusy, versionStatus } from "@/lib/treaties";

export function TreatiesView() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ program_id: "", name: "", source_document_id: "" });

  const treaties = useQuery({
    queryKey: ["treaties"],
    queryFn: async () => (await listTreaties({ throwOnError: true })).data.treaties,
    refetchInterval: (q) =>
      (q.state.data ?? []).some((t) => t.current_version && isBusy(t.current_version.status))
        ? 2500
        : false,
  });
  const programs = useQuery({
    queryKey: ["programs"],
    queryFn: async () => (await listPrograms({ throwOnError: true })).data.programs,
  });
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: async () => (await listDocuments({ throwOnError: true })).data.documents,
  });

  const parsedTreatyDocs = (documents.data ?? []).filter(
    (d) => d.kind === "treaty" && d.status === "parsed",
  );

  const add = useMutation({
    mutationFn: async () => {
      const { data } = await createTreaty({
        body: {
          program_id: form.program_id,
          name: form.name,
          source_document_id: form.source_document_id || null,
        },
        throwOnError: true,
      });
      return data;
    },
    onSuccess: () => {
      setForm({ program_id: "", name: "", source_document_id: "" });
      queryClient.invalidateQueries({ queryKey: ["treaties"] });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Treaties"
        description="Create a treaty from a parsed treaty document. Cedeon extracts the terms; you validate them."
      />

      <Card>
        <CardHeader>
          <CardTitle>New treaty</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-3 md:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (form.program_id && form.name.trim()) add.mutate();
            }}
          >
            <Field label="Program" htmlFor="tprogram">
              <Select
                id="tprogram"
                value={form.program_id}
                onChange={(e) => setForm({ ...form, program_id: e.target.value })}
              >
                <option value="">Select…</option>
                {programs.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Treaty name" htmlFor="tname">
              <Input
                id="tname"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="2027 Property Cat XOL"
              />
            </Field>
            <Field label="Source document" htmlFor="tdoc">
              <Select
                id="tdoc"
                value={form.source_document_id}
                onChange={(e) => setForm({ ...form, source_document_id: e.target.value })}
              >
                <option value="">None (add later)</option>
                {parsedTreatyDocs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.original_filename}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="md:col-span-3">
              <Button type="submit" disabled={add.isPending}>
                <Plus /> {add.isPending ? "Creating…" : "Create treaty"}
              </Button>
              {parsedTreatyDocs.length === 0 ? (
                <span className="ml-3 text-xs text-muted-foreground">
                  Upload &amp; parse a treaty PDF in Documents first.
                </span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Treaties</CardTitle>
        </CardHeader>
        <CardContent>
          {treaties.data && treaties.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">Treaty</th>
                  <th className="py-2 font-medium">Cedent</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {treaties.data.map((t) => {
                  const s = t.current_version ? versionStatus(t.current_version.status) : null;
                  return (
                    <tr key={t.id} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5">
                        <Link
                          href={`/treaties/${t.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {t.name}
                        </Link>
                      </td>
                      <td className="py-2.5 text-muted-foreground">{t.cedent_name}</td>
                      <td className="py-2.5">{s ? <Badge tone={s.tone}>{s.label}</Badge> : "—"}</td>
                      <td className="py-2.5 text-right">
                        {t.current_version?.status === "needs_validation" ? (
                          <Link
                            href={`/treaties/${t.id}/validate`}
                            className="text-sm font-medium text-primary hover:underline"
                          >
                            Validate →
                          </Link>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon={<ScrollText />}
              title="No treaties yet"
              description="Create one from a parsed treaty document above."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
