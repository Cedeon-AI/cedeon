"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, FileText, Upload } from "lucide-react";
import Link from "next/link";
import { type ChangeEvent, type ReactNode, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/field";
import { BackLink, PageHeader } from "@/components/ui/page-header";
import { Stepper } from "@/components/ui/stepper";
import {
  asProblem,
  createCedent,
  createProgram,
  createTreaty,
  getDocument,
  getTreaty,
  listCedents,
  listPrograms,
} from "@/lib/api";
import { uploadDocumentFile } from "@/lib/documents";
import { isBusy, versionStatus } from "@/lib/treaties";

const STEPS = [
  { key: "upload", label: "Upload wording" },
  { key: "details", label: "Program & name" },
  { key: "extract", label: "Extract & validate" },
] as const;

export function NewTreatyWizard() {
  const [step, setStep] = useState(0);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [treatyId, setTreatyId] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <BackLink href="/treaties">Treaties</BackLink>
      <PageHeader
        title="Set up a treaty"
        description="Upload the contract wording; Cedeon extracts the terms and hands them to you to confirm."
      />
      <Stepper steps={STEPS} current={step} />

      {step === 0 ? (
        <UploadStep documentId={documentId} onUploaded={setDocumentId} onReady={() => setStep(1)} />
      ) : null}
      {step === 1 && documentId ? (
        <DetailsStep
          documentId={documentId}
          onCreated={(id) => {
            setTreatyId(id);
            setStep(2);
          }}
          onBack={() => setStep(0)}
        />
      ) : null}
      {step === 2 && treatyId ? <ExtractStep treatyId={treatyId} /> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ step 0 */

function UploadStep({
  documentId,
  onUploaded,
  onReady,
}: {
  documentId: string | null;
  onUploaded: (id: string) => void;
  onReady: () => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const result = await uploadDocumentFile(file, "treaty");
      if (!result.data) throw result.error;
      return result.data;
    },
    onSuccess: (doc) => {
      setError(null);
      onUploaded(doc.id);
    },
    onError: () => setError("Upload failed. PDFs only, up to 50 MB."),
  });

  const doc = useQuery({
    queryKey: ["documents", documentId],
    enabled: Boolean(documentId),
    queryFn: async () =>
      (await getDocument({ path: { document_id: documentId as string }, throwOnError: true })).data
        .document,
    refetchInterval: (q) =>
      q.state.data && (q.state.data.status === "uploaded" || q.state.data.status === "parsing")
        ? 1500
        : false,
  });

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) upload.mutate(file);
  }

  const status = doc.data?.status;

  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,.pdf"
          onChange={onFileChange}
          className="hidden"
        />

        {!documentId ? (
          <div className="rounded-lg border border-dashed border-border-strong bg-muted/30 px-6 py-10 text-center">
            <span className="mx-auto flex size-11 items-center justify-center rounded-full border border-border bg-card text-muted-foreground">
              <FileText className="size-5" />
            </span>
            <p className="mt-3 text-sm font-medium">Upload the treaty wording</p>
            <p className="mt-1 text-sm text-muted-foreground">A PDF of the contract or slip.</p>
            <Button
              className="mt-4"
              onClick={() => fileRef.current?.click()}
              disabled={upload.isPending}
            >
              <Upload /> {upload.isPending ? "Uploading…" : "Choose PDF"}
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
            <div className="flex items-center gap-3 text-sm">
              <FileText className="size-4 text-muted-foreground" />
              <span>
                {status === "parsed"
                  ? "Parsed — page and clause structure extracted"
                  : status === "parse_failed"
                    ? "Could not parse this PDF"
                    : "Parsing the document…"}
              </span>
            </div>
            {status === "parsed" ? (
              <Check className="size-4 text-human" />
            ) : status === "parse_failed" ? (
              <Button size="sm" variant="secondary" onClick={() => fileRef.current?.click()}>
                Try another
              </Button>
            ) : (
              <span className="size-4 animate-spin rounded-full border-2 border-border border-t-primary" />
            )}
          </div>
        )}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex justify-end">
          <Button onClick={onReady} disabled={status !== "parsed"}>
            Continue <ArrowRight />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ step 1 */

function DetailsStep({
  documentId,
  onCreated,
  onBack,
}: {
  documentId: string;
  onCreated: (treatyId: string) => void;
  onBack: () => void;
}) {
  const programs = useQuery({
    queryKey: ["programs"],
    queryFn: async () => (await listPrograms({ throwOnError: true })).data.programs,
  });
  const cedents = useQuery({
    queryKey: ["cedents"],
    queryFn: async () => (await listCedents({ throwOnError: true })).data.cedents,
  });

  const [programMode, setProgramMode] = useState<"existing" | "new">("existing");
  const [cedentMode, setCedentMode] = useState<"existing" | "new">("existing");
  const [form, setForm] = useState({
    program_id: "",
    cedent_id: "",
    cedent_name: "",
    program_name: "",
    treaty_year: String(new Date().getFullYear() + 1),
    treaty_name: "",
  });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (v: string) => setForm((p) => ({ ...p, [k]: v }));

  const hasPrograms = (programs.data ?? []).length > 0;
  const effectiveProgramMode = hasPrograms ? programMode : "new";

  const create = useMutation({
    mutationFn: async () => {
      let programId = form.program_id;
      if (effectiveProgramMode === "new") {
        let cedentId = form.cedent_id;
        if (cedentMode === "new" || (cedents.data ?? []).length === 0) {
          const c = await createCedent({
            body: { name: form.cedent_name.trim() },
            throwOnError: true,
          });
          cedentId = c.data.id;
        }
        const p = await createProgram({
          body: {
            cedent_id: cedentId,
            name: form.program_name.trim(),
            treaty_year: Number(form.treaty_year),
          },
          throwOnError: true,
        });
        programId = p.data.id;
      }
      const t = await createTreaty({
        body: {
          program_id: programId,
          name: form.treaty_name.trim(),
          source_document_id: documentId,
        },
        throwOnError: true,
      });
      return t.data;
    },
    onSuccess: (treaty) => onCreated(treaty.id),
    onError: (err) => {
      const p = asProblem(err);
      setError(p?.detail ?? p?.title ?? "Could not create the treaty.");
    },
  });

  const ready =
    form.treaty_name.trim() &&
    (effectiveProgramMode === "existing"
      ? form.program_id
      : form.program_name.trim() &&
        (cedentMode === "existing" && (cedents.data ?? []).length > 0
          ? form.cedent_id
          : form.cedent_name.trim()));

  return (
    <Card>
      <CardContent className="space-y-5 pt-5">
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (ready) create.mutate();
          }}
        >
          {hasPrograms ? (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Reinsurance program</legend>
              <div className="flex gap-2 text-sm">
                <ModeButton
                  active={programMode === "existing"}
                  onClick={() => setProgramMode("existing")}
                >
                  Existing
                </ModeButton>
                <ModeButton active={programMode === "new"} onClick={() => setProgramMode("new")}>
                  New
                </ModeButton>
              </div>
              {programMode === "existing" ? (
                <Select value={form.program_id} onChange={(e) => set("program_id")(e.target.value)}>
                  <option value="">Select a program…</option>
                  {programs.data?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} — {p.cedent_name}
                    </option>
                  ))}
                </Select>
              ) : null}
            </fieldset>
          ) : null}

          {effectiveProgramMode === "new" ? (
            <div className="grid gap-4 rounded-lg border border-border bg-muted/20 p-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <p className="text-sm font-medium">Cedent</p>
                {(cedents.data ?? []).length > 0 ? (
                  <div className="mb-2 mt-1 flex gap-2 text-sm">
                    <ModeButton
                      active={cedentMode === "existing"}
                      onClick={() => setCedentMode("existing")}
                    >
                      Existing
                    </ModeButton>
                    <ModeButton active={cedentMode === "new"} onClick={() => setCedentMode("new")}>
                      New
                    </ModeButton>
                  </div>
                ) : null}
                {cedentMode === "existing" && (cedents.data ?? []).length > 0 ? (
                  <Select value={form.cedent_id} onChange={(e) => set("cedent_id")(e.target.value)}>
                    <option value="">Select a cedent…</option>
                    {cedents.data?.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Input
                    value={form.cedent_name}
                    onChange={(e) => set("cedent_name")(e.target.value)}
                    placeholder="Atlantic Specialty Insurance Company"
                  />
                )}
              </div>
              <Field label="Program name" htmlFor="w-prog">
                <Input
                  id="w-prog"
                  value={form.program_name}
                  onChange={(e) => set("program_name")(e.target.value)}
                  placeholder="2027 Property Catastrophe Program"
                />
              </Field>
              <Field label="Treaty year" htmlFor="w-year">
                <Input
                  id="w-year"
                  type="number"
                  value={form.treaty_year}
                  onChange={(e) => set("treaty_year")(e.target.value)}
                />
              </Field>
            </div>
          ) : null}

          <Field label="Treaty name" htmlFor="w-treaty">
            <Input
              id="w-treaty"
              value={form.treaty_name}
              onChange={(e) => set("treaty_name")(e.target.value)}
              placeholder="2027 Property Cat XOL"
            />
          </Field>

          {error ? <p className="text-sm text-danger">{error}</p> : null}

          <div className="flex justify-between">
            <Button type="button" variant="ghost" onClick={onBack}>
              Back
            </Button>
            <Button type="submit" disabled={!ready || create.isPending}>
              {create.isPending ? "Creating…" : "Create & extract"} <ArrowRight />
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

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

/* ------------------------------------------------------------------ step 2 */

function ExtractStep({ treatyId }: { treatyId: string }) {
  const treaty = useQuery({
    queryKey: ["treaties", treatyId],
    queryFn: async () =>
      (await getTreaty({ path: { treaty_id: treatyId }, throwOnError: true })).data,
    refetchInterval: (q) => {
      const s = q.state.data?.current_version?.status;
      return s && (isBusy(s) || s === "draft") ? 2500 : false;
    },
  });

  const version = treaty.data?.current_version;
  const status = version?.status;
  const done = status === "needs_validation" || status === "validated" || status === "active";

  return (
    <Card>
      <CardContent className="space-y-4 pt-5">
        <div className="flex items-center gap-3">
          {done ? (
            <span className="flex size-8 items-center justify-center rounded-full bg-human/10 text-human">
              <Check className="size-4" />
            </span>
          ) : (
            <span className="size-8 shrink-0 animate-spin rounded-full border-2 border-border border-t-primary" />
          )}
          <div>
            <p className="text-sm font-medium">
              {done ? "Terms extracted" : "Reading the wording…"}
            </p>
            <p className="text-xs text-muted-foreground">
              {status ? versionStatus(status).label : "Starting…"}
              {!done
                ? " — this runs on the worker and usually takes under a minute."
                : " — every term has a citation and a confidence score."}
            </p>
          </div>
        </div>

        {done ? (
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href={`/treaties/${treatyId}/validate`}>
                Validate the proposed terms <ArrowRight />
              </Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href={`/treaties/${treatyId}`}>Go to the treaty</Link>
            </Button>
          </div>
        ) : status === "draft" ? (
          <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            Extraction hasn&rsquo;t started yet. If this persists, the document may still be parsing
            — check back in a moment.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
