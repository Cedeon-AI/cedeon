"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Info, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ChangeEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/field";
import { BackLink, PageHeader } from "@/components/ui/page-header";
import { Stepper } from "@/components/ui/stepper";
import {
  asProblem,
  commitLossImport,
  createLossEvent,
  createRecoveryCandidate,
  getLossImport,
  listLossEvents,
  listLossFields,
  listTreaties,
  setLossImportMapping,
} from "@/lib/api";
import { guessMapping, uploadLossImportFile } from "@/lib/losses";
import { formatMoney } from "@/lib/utils";

const STEPS = [
  { key: "event", label: "Loss event" },
  { key: "claims", label: "Claims" },
  { key: "treaty", label: "Responding treaty" },
  { key: "calc", label: "Calculate" },
] as const;

export function NewRecoveryWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [eventId, setEventId] = useState<string | null>(null);
  const [treatyId, setTreatyId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const calc = useMutation({
    mutationFn: async () => {
      const result = await createRecoveryCandidate({
        body: { treaty_id: treatyId, loss_event_id: eventId as string },
      });
      if (!result.data) throw result.error;
      return result.data;
    },
    onSuccess: (rec) => router.push(`/recovery-candidates/${rec.id}`),
    onError: (err) => {
      const p = asProblem(err);
      setError(p?.detail ?? p?.title ?? "Could not run the recovery.");
    },
  });

  return (
    <div className="space-y-6">
      <BackLink href="/recovery-candidates">Recoveries</BackLink>
      <PageHeader
        title="Start a recovery"
        description="Pair a loss event with the treaty that responds; Cedeon computes the recovery."
      />
      <Stepper steps={STEPS} current={step} />

      {step === 0 ? (
        <EventStep
          onReady={(id) => {
            setEventId(id);
            setStep(1);
          }}
        />
      ) : null}

      {step === 1 && eventId ? (
        <ClaimsStep eventId={eventId} onReady={() => setStep(2)} onBack={() => setStep(0)} />
      ) : null}

      {step === 2 ? (
        <TreatyStep
          value={treatyId}
          onChange={setTreatyId}
          onBack={() => setStep(1)}
          onReady={() => setStep(3)}
        />
      ) : null}

      {step === 3 ? (
        <Card>
          <CardContent className="space-y-4 pt-5">
            <p className="text-sm text-muted-foreground">
              Cedeon will run the deterministic engine over the validated treaty terms and the
              committed claims. The figure is code, not an LLM — you review and confirm it next.
            </p>
            {error ? <p className="text-sm text-danger">{error}</p> : null}
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button onClick={() => calc.mutate()} disabled={calc.isPending}>
                {calc.isPending ? "Calculating…" : "Calculate the recovery"} <ArrowRight />
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ step 0 */

function EventStep({ onReady }: { onReady: (id: string) => void }) {
  const events = useQuery({
    queryKey: ["loss-events"],
    queryFn: async () => (await listLossEvents({ throwOnError: true })).data.events,
  });
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const [existingId, setExistingId] = useState("");
  const [form, setForm] = useState({
    name: "",
    catastrophe_code: "",
    peril: "",
    hours_clause_hours: "",
  });
  const [error, setError] = useState<string | null>(null);

  const hasEvents = (events.data ?? []).length > 0;
  const effectiveMode = hasEvents ? mode : "new";

  const create = useMutation({
    mutationFn: async () => {
      const { data } = await createLossEvent({
        body: {
          name: form.name.trim(),
          catastrophe_code: form.catastrophe_code.trim() || null,
          peril: form.peril.trim() || null,
          hours_clause_hours: form.hours_clause_hours ? Number(form.hours_clause_hours) : null,
        },
        throwOnError: true,
      });
      return data;
    },
    onSuccess: (evt) => onReady(evt.id),
    onError: (err) => {
      const p = asProblem(err);
      setError(p?.detail ?? p?.title ?? "Could not create the loss event.");
    },
  });

  return (
    <Card>
      <CardContent className="space-y-5 pt-5">
        <div className="flex gap-3 rounded-lg border border-fact/20 bg-fact/5 p-3 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-fact" />
          <p className="text-muted-foreground">
            The <strong>occurrence basis</strong> is your decision: which hours clause applies
            (typically 168h for a named windstorm, 72h otherwise) and the date range. It determines
            which claims aggregate into one occurrence. Recorded here for the file — the engine does
            not yet apply it.
          </p>
        </div>

        {hasEvents ? (
          <div className="flex gap-2 text-sm">
            <ModeButton active={mode === "existing"} onClick={() => setMode("existing")}>
              Existing event
            </ModeButton>
            <ModeButton active={mode === "new"} onClick={() => setMode("new")}>
              New event
            </ModeButton>
          </div>
        ) : null}

        {effectiveMode === "existing" ? (
          <Field label="Loss event" htmlFor="w-evt">
            <Select id="w-evt" value={existingId} onChange={(e) => setExistingId(e.target.value)}>
              <option value="">Select an event…</option>
              {events.data?.map((evt) => (
                <option key={evt.id} value={evt.id}>
                  {evt.name}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Event name" htmlFor="w-evt-name">
              <Input
                id="w-evt-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Hurricane Béatrice 2027"
              />
            </Field>
            <Field label="Catastrophe code (optional)" htmlFor="w-evt-code">
              <Input
                id="w-evt-code"
                value={form.catastrophe_code}
                onChange={(e) => setForm({ ...form, catastrophe_code: e.target.value })}
                placeholder="PCS 2027-XX"
              />
            </Field>
            <Field label="Peril (optional)" htmlFor="w-evt-peril">
              <Input
                id="w-evt-peril"
                value={form.peril}
                onChange={(e) => setForm({ ...form, peril: e.target.value })}
                placeholder="Named windstorm"
              />
            </Field>
            <Field label="Hours clause (optional)" htmlFor="w-evt-hours">
              <Input
                id="w-evt-hours"
                type="number"
                inputMode="numeric"
                value={form.hours_clause_hours}
                onChange={(e) => setForm({ ...form, hours_clause_hours: e.target.value })}
                placeholder="168"
              />
            </Field>
          </div>
        )}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex justify-end">
          {effectiveMode === "existing" ? (
            <Button disabled={!existingId} onClick={() => onReady(existingId)}>
              Continue <ArrowRight />
            </Button>
          ) : (
            <Button
              disabled={!form.name.trim() || create.isPending}
              onClick={() => create.mutate()}
            >
              {create.isPending ? "Creating…" : "Create & continue"} <ArrowRight />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ step 1 */

function ClaimsStep({
  eventId,
  onReady,
  onBack,
}: {
  eventId: string;
  onReady: () => void;
  onBack: () => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [importId, setImportId] = useState<string | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [showMapping, setShowMapping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const event = useQuery({
    queryKey: ["loss-events"],
    queryFn: async () => (await listLossEvents({ throwOnError: true })).data.events,
  });
  const thisEvent = (event.data ?? []).find((e) => e.id === eventId);
  const eventClaims = thisEvent?.totals.reduce((n, t) => n + t.claim_count, 0) ?? 0;

  const fields = useQuery({
    queryKey: ["loss-fields"],
    queryFn: async () => (await listLossFields({ throwOnError: true })).data.fields,
  });

  const imp = useQuery({
    queryKey: ["loss-imports", importId],
    enabled: Boolean(importId),
    queryFn: async () =>
      (await getLossImport({ path: { import_id: importId as string }, throwOnError: true })).data,
  });

  const headers = imp.data?.loss_import.header_columns ?? [];
  const report = imp.data?.loss_import.report;
  const committed = imp.data?.loss_import.status === "committed";

  // seed the mapping from a guess once headers + fields are known
  const fieldList = fields.data;
  const headerKey = headers.join("|");
  useEffect(() => {
    if (!headerKey || !fieldList) return;
    setMapping((prev) =>
      Object.keys(prev).length > 0
        ? prev
        : guessMapping(
            headerKey.split("|"),
            fieldList.map((f) => f.field),
          ),
    );
  }, [headerKey, fieldList]);

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const result = await uploadLossImportFile(file);
      if (!result.data) throw result.error;
      return result.data;
    },
    onSuccess: (data) => {
      setError(null);
      setImportId(data.id);
      setMapping({});
    },
    onError: () => setError("Upload failed. CSV only, up to 25 MB, with a header row."),
  });

  const validate = useMutation({
    mutationFn: async () => {
      const clean = Object.fromEntries(Object.entries(mapping).filter(([, c]) => c));
      const result = await setLossImportMapping({
        path: { import_id: importId as string },
        body: { mapping: clean },
      });
      if (!result.data) throw result.error;
    },
    onSuccess: () => {
      setError(null);
      imp.refetch();
    },
    onError: (err) => {
      const p = asProblem(err);
      setError(p?.detail ?? p?.title ?? "Could not validate the mapping.");
    },
  });

  const commit = useMutation({
    mutationFn: async () => {
      const { data } = await commitLossImport({
        path: { import_id: importId as string },
        body: { loss_event_id: eventId, event_name: null },
        throwOnError: true,
      });
      return data;
    },
    onSuccess: onReady,
    onError: (err) => {
      const p = asProblem(err);
      setError(p?.detail ?? p?.title ?? "Commit failed. Re-validate and try again.");
    },
  });

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) upload.mutate(file);
  }

  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <input
          ref={fileRef}
          type="file"
          accept="text/csv,.csv"
          onChange={onFileChange}
          className="hidden"
        />

        {eventClaims > 0 ? (
          <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm">
            <span>
              {thisEvent?.name} already has <strong>{eventClaims}</strong> committed claim(s).
            </span>
            <Button size="sm" variant="secondary" onClick={onReady}>
              Use existing claims
            </Button>
          </div>
        ) : null}

        {!importId ? (
          <div className="rounded-lg border border-dashed border-border-strong bg-muted/30 px-6 py-10 text-center">
            <p className="text-sm font-medium">Add the claims for this event</p>
            <p className="mt-1 text-sm text-muted-foreground">
              A claims schedule as CSV, with a header row.
            </p>
            <Button
              className="mt-4"
              onClick={() => fileRef.current?.click()}
              disabled={upload.isPending}
            >
              <Upload /> {upload.isPending ? "Uploading…" : "Choose CSV"}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{imp.data?.loss_import.original_filename}</span>
              <span className="text-muted-foreground">
                {imp.data?.loss_import.row_count} rows · {headers.length} columns
              </span>
            </div>

            <button
              type="button"
              onClick={() => setShowMapping((v) => !v)}
              className="text-xs font-medium text-primary hover:underline"
            >
              {showMapping ? "Hide column mapping" : "Review column mapping"}
            </button>

            {showMapping ? (
              <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-3">
                {(fields.data ?? []).map((f) => (
                  <div key={f.field} className="grid grid-cols-2 items-center gap-3 text-sm">
                    <span>
                      {f.label}
                      {f.required ? <span className="ml-1 text-danger">*</span> : null}
                    </span>
                    <Select
                      value={mapping[f.field] ?? ""}
                      onChange={(e) => setMapping({ ...mapping, [f.field]: e.target.value })}
                      className="h-9 px-2"
                    >
                      <option value="">— not mapped —</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </Select>
                  </div>
                ))}
              </div>
            ) : null}

            {report ? (
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge tone="success">{report.ok} ok</Badge>
                {report.warnings > 0 ? (
                  <Badge tone="warning">{report.warnings} warnings</Badge>
                ) : null}
                {report.errors > 0 ? <Badge tone="danger">{report.errors} errors</Badge> : null}
                {Object.entries(report.gross_incurred_by_currency).map(([ccy, total]) => (
                  <span key={ccy} className="text-muted-foreground">
                    {formatMoney(total, ccy)}
                  </span>
                ))}
              </div>
            ) : null}

            {error ? <p className="text-sm text-danger">{error}</p> : null}

            <div className="flex flex-wrap gap-2">
              {!report || validate.isPending ? (
                <Button
                  size="sm"
                  onClick={() => validate.mutate()}
                  disabled={validate.isPending || Object.keys(mapping).length === 0}
                >
                  {validate.isPending ? "Validating…" : "Validate rows"}
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={() => validate.mutate()}
                  variant="secondary"
                  disabled={validate.isPending}
                >
                  Re-validate
                </Button>
              )}
              <Button
                size="sm"
                onClick={() => commit.mutate()}
                disabled={
                  !report || (report.committable ?? 0) === 0 || commit.isPending || committed
                }
              >
                {commit.isPending ? "Committing…" : `Commit ${report?.committable ?? 0} claim(s)`}
              </Button>
              <Button asChild size="sm" variant="ghost">
                <Link href={`/loss-imports/${importId}`}>Open full import screen</Link>
              </Button>
            </div>
          </div>
        )}

        <div className="flex justify-between border-t border-border/60 pt-3">
          <Button variant="ghost" onClick={onBack}>
            Back
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ step 2 */

function TreatyStep({
  value,
  onChange,
  onBack,
  onReady,
}: {
  value: string;
  onChange: (id: string) => void;
  onBack: () => void;
  onReady: () => void;
}) {
  const treaties = useQuery({
    queryKey: ["treaties"],
    queryFn: async () => (await listTreaties({ throwOnError: true })).data.treaties,
  });
  const validated = (treaties.data ?? []).filter(
    (t) => t.current_version?.status === "validated" || t.current_version?.status === "active",
  );

  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <Field label="Responding treaty" htmlFor="w-rec-treaty">
          <Select id="w-rec-treaty" value={value} onChange={(e) => onChange(e.target.value)}>
            <option value="">Select a validated treaty…</option>
            {validated.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} — {t.cedent_name}
              </option>
            ))}
          </Select>
        </Field>
        {validated.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No validated treaties yet.{" "}
            <Link href="/treaties/new" className="text-primary hover:underline">
              Set one up
            </Link>{" "}
            first.
          </p>
        ) : null}
        <div className="flex justify-between">
          <Button variant="ghost" onClick={onBack}>
            Back
          </Button>
          <Button disabled={!value} onClick={onReady}>
            Continue <ArrowRight />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ shared */

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "rounded-md border border-primary/40 bg-primary/10 px-2.5 py-1 font-medium text-primary"
          : "rounded-md border border-border px-2.5 py-1 text-muted-foreground hover:text-foreground"
      }
    >
      {children}
    </button>
  );
}
