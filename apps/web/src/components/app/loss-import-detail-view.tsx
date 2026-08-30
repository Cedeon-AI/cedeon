"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/field";
import { BackLink, PageHeader } from "@/components/ui/page-header";
import type { ImportReportOut, ImportRowOut } from "@/lib/api";
import {
  asProblem,
  commitLossImport,
  getLossImport,
  listLossEvents,
  listLossFields,
  setLossImportMapping,
} from "@/lib/api";
import { guessMapping, importStatus, rowTone } from "@/lib/losses";
import { formatMoney } from "@/lib/utils";

const NONE = "";

export function LossImportDetailView({ importId }: { importId: string }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [mapping, setMapping] = useState<Record<string, string> | null>(null);
  const [eventName, setEventName] = useState("");
  const [existingEventId, setExistingEventId] = useState(NONE);
  const [mapError, setMapError] = useState<string | null>(null);

  const detail = useQuery({
    queryKey: ["loss-imports", importId],
    queryFn: async () =>
      (await getLossImport({ path: { import_id: importId }, throwOnError: true })).data,
  });
  const fields = useQuery({
    queryKey: ["loss-fields"],
    queryFn: async () => (await listLossFields({ throwOnError: true })).data.fields,
  });
  const events = useQuery({
    queryKey: ["loss-events"],
    queryFn: async () => (await listLossEvents({ throwOnError: true })).data.events,
  });

  const loss = detail.data?.loss_import;
  const rows = detail.data?.rows ?? [];
  const headers = loss?.header_columns ?? [];
  const committed = loss?.status === "committed";

  // Effective mapping: local edits, else what the server has, else a guess.
  const effectiveMapping = useMemo(() => {
    if (mapping) return mapping;
    if (loss && Object.keys(loss.column_mapping).length > 0) return loss.column_mapping;
    if (loss && fields.data) {
      return guessMapping(
        headers,
        fields.data.map((f) => f.field),
      );
    }
    return {};
  }, [mapping, loss, fields.data, headers]);

  const setField = (field: string, column: string) =>
    setMapping({ ...effectiveMapping, [field]: column });

  const validate = useMutation({
    mutationFn: async () => {
      const cleaned = Object.fromEntries(
        Object.entries(effectiveMapping).filter(([, column]) => column),
      );
      const result = await setLossImportMapping({
        path: { import_id: importId },
        body: { mapping: cleaned },
      });
      if (!result.data) throw result.error;
      return result.data;
    },
    onSuccess: () => {
      setMapError(null);
      setMapping(null);
      queryClient.invalidateQueries({ queryKey: ["loss-imports", importId] });
    },
    onError: (err) => {
      const problem = asProblem(err);
      setMapError(problem?.detail ?? problem?.title ?? "Could not validate the mapping.");
    },
  });

  const commit = useMutation({
    mutationFn: async () => {
      const { data } = await commitLossImport({
        path: { import_id: importId },
        body: {
          event_name: eventName.trim() || null,
          loss_event_id: existingEventId || null,
        },
        throwOnError: true,
      });
      return data;
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["loss-imports"] });
      queryClient.invalidateQueries({ queryKey: ["loss-events"] });
      const eventId = result.loss_event_ids[0];
      if (eventId) router.push(`/loss-events/${eventId}`);
    },
  });

  if (detail.isLoading || !loss) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  const status = importStatus(loss.status);
  const report = loss.report;
  const canCommit = loss.status === "validated" && (report?.committable ?? 0) > 0;

  return (
    <div className="space-y-6">
      <BackLink href="/loss-imports">Loss imports</BackLink>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            {loss.original_filename}
            <Badge tone={status.tone}>{status.label}</Badge>
          </span>
        }
        description={`${loss.row_count} data rows · ${headers.length} columns`}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Column mapping</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {committed ? (
              <p className="text-sm text-muted-foreground">
                This import is committed — the mapping is frozen.
              </p>
            ) : null}
            {(fields.data ?? []).map((f) => (
              <div key={f.field} className="grid grid-cols-2 items-center gap-3">
                <div className="text-sm">
                  <span className="font-medium">{f.label}</span>
                  {f.required ? <span className="ml-1 text-danger">*</span> : null}
                  {f.hint ? (
                    <span className="block text-xs text-muted-foreground">{f.hint}</span>
                  ) : null}
                </div>
                <Select
                  value={effectiveMapping[f.field] ?? NONE}
                  disabled={committed}
                  onChange={(e) => setField(f.field, e.target.value)}
                  className="h-9 px-2"
                >
                  <option value={NONE}>— not mapped —</option>
                  {headers.map((column) => (
                    <option key={column} value={column}>
                      {column}
                    </option>
                  ))}
                </Select>
              </div>
            ))}
            {!committed ? (
              <div className="flex items-center gap-3 pt-1">
                <Button onClick={() => validate.mutate()} disabled={validate.isPending}>
                  {validate.isPending ? "Validating…" : "Validate rows"}
                </Button>
                {mapError ? <span className="text-sm text-danger">{mapError}</span> : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-4">
          {report ? <ReportPanel report={report} /> : null}

          {canCommit ? (
            <Card>
              <CardHeader>
                <CardTitle>Commit to underlying losses</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  {report?.committable} valid row(s) become immutable underlying losses. Rows with
                  errors are skipped and stay on the import for correction.
                </p>
                <Field label="New loss event name (optional)" htmlFor="evtname">
                  <Input
                    id="evtname"
                    value={eventName}
                    disabled={existingEventId !== NONE}
                    onChange={(e) => setEventName(e.target.value)}
                    placeholder={report?.distinct_events[0] ?? "Hurricane Demo 2027"}
                  />
                </Field>
                {(events.data ?? []).length > 0 ? (
                  <Field label="…or add to an existing event" htmlFor="evtexisting">
                    <Select
                      id="evtexisting"
                      value={existingEventId}
                      onChange={(e) => setExistingEventId(e.target.value)}
                    >
                      <option value={NONE}>New event(s) from the CSV</option>
                      {events.data?.map((evt) => (
                        <option key={evt.id} value={evt.id}>
                          {evt.name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                ) : null}
                <Button onClick={() => commit.mutate()} disabled={commit.isPending}>
                  {commit.isPending ? "Committing…" : "Commit losses"}
                </Button>
                {commit.isError ? (
                  <p className="text-sm text-danger">Commit failed. Re-validate and try again.</p>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {committed ? (
            <Card>
              <CardContent className="py-6 text-center text-sm">
                <p className="font-medium text-human">Committed.</p>
                <Link
                  href="/loss-events"
                  className="mt-1 inline-block text-primary hover:underline"
                >
                  View loss events →
                </Link>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Rows ({rows.length})</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <RowsTable rows={rows} headers={headers} />
        </CardContent>
      </Card>
    </div>
  );
}

function ReportPanel({ report }: { report: ImportReportOut }) {
  const tiles: { label: string; value: number; tone: string }[] = [
    { label: "OK", value: report.ok, tone: "text-human" },
    { label: "Warnings", value: report.warnings, tone: "text-warning" },
    { label: "Errors", value: report.errors, tone: "text-danger" },
    { label: "Committable", value: report.committable, tone: "text-foreground" },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Validation report</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-4 gap-2 text-center">
          {tiles.map((tile) => (
            <div key={tile.label} className="rounded-md border border-border p-2">
              <p className={`text-lg font-semibold ${tile.tone}`}>{tile.value}</p>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                {tile.label}
              </p>
            </div>
          ))}
        </div>

        <dl className="space-y-1 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Currencies</dt>
            <dd>{report.currencies.join(", ") || "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Distinct events</dt>
            <dd className="text-right">{report.distinct_events.join(", ") || "—"}</dd>
          </div>
          {Object.entries(report.gross_incurred_by_currency).map(([currency, total]) => (
            <div key={currency} className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Gross incurred ({currency})</dt>
              <dd className="font-medium">{formatMoney(total, currency)}</dd>
            </div>
          ))}
        </dl>

        {report.issues.length > 0 ? (
          <ul className="max-h-48 space-y-1 overflow-auto text-xs">
            {report.issues.map((issue, index) => (
              <li
                // biome-ignore lint/suspicious/noArrayIndexKey: issues have no stable id
                key={index}
                className={issue.level === "error" ? "text-danger" : "text-warning"}
              >
                Row {issue.row_number}
                {issue.field ? ` · ${issue.field}` : ""}: {issue.message}
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

function RowsTable({ rows, headers }: { rows: ImportRowOut[]; headers: string[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No rows.</p>;
  }
  return (
    <table className="w-full text-xs">
      <thead className="text-left uppercase tracking-wide text-muted-foreground">
        <tr className="border-b border-border">
          <th className="py-2 pr-3 font-medium">#</th>
          <th className="py-2 pr-3 font-medium">Status</th>
          {headers.map((column) => (
            <th key={column} className="py-2 pr-3 font-medium">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.row_number} className="border-b border-border/60 last:border-0">
            <td className="py-1.5 pr-3 text-muted-foreground">{row.row_number}</td>
            <td className="py-1.5 pr-3">
              <Badge tone={rowTone(row.status)}>{row.status}</Badge>
            </td>
            {headers.map((column) => (
              <td key={column} className="py-1.5 pr-3">
                {row.raw[column] ?? ""}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
