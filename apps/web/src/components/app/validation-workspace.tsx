"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { BackLink, EmptyState, PageHeader } from "@/components/ui/page-header";
import type { ReviewDecision, TermCandidateOut } from "@/lib/api";
import {
  asProblem,
  getTermDiff,
  getTreaty,
  listTermCandidates,
  reviewTermCandidate,
  validateTreatyVersion,
} from "@/lib/api";
import { candidateTone, termLabel } from "@/lib/treaties";
import { cn } from "@/lib/utils";

const RESOLUTION_LABEL: Record<string, string> = {
  confirmed: "Confirmed",
  rejected: "Rejected",
  ambiguous: "Ambiguous",
  info_requested: "Info requested",
};

function resolutionTone(resolution: string | null | undefined) {
  if (resolution === "confirmed") return "human" as const;
  if (resolution === "rejected") return "neutral" as const;
  return "warning" as const;
}

export function ValidationWorkspace({ treatyId }: { treatyId: string }) {
  const queryClient = useQueryClient();
  const [activePage, setActivePage] = useState(1);
  const [validateError, setValidateError] = useState<string | null>(null);

  const treaty = useQuery({
    queryKey: ["treaties", treatyId],
    queryFn: async () =>
      (await getTreaty({ path: { treaty_id: treatyId }, throwOnError: true })).data,
  });
  const versionId = treaty.data?.treaty.current_version?.id ?? null;

  const workspace = useQuery({
    queryKey: ["term-candidates", versionId],
    enabled: Boolean(versionId),
    queryFn: async () => {
      const { data } = await listTermCandidates({
        path: { treaty_id: treatyId, version_id: versionId as string },
        throwOnError: true,
      });
      return data;
    },
  });

  const termDiff = useQuery({
    queryKey: ["term-diff", versionId],
    enabled: Boolean(versionId),
    queryFn: async () => {
      const { data } = await getTermDiff({
        path: { treaty_id: treatyId, version_id: versionId as string },
        throwOnError: true,
      });
      return data;
    },
  });

  const invalidateCandidates = () =>
    queryClient.invalidateQueries({ queryKey: ["term-candidates", versionId] });

  /** One review call. Throws the problem body on failure so callers can surface it. */
  async function submitReview(
    candidateId: string,
    decision: ReviewDecision,
    value?: string,
  ): Promise<void> {
    const result = await reviewTermCandidate({
      path: {
        treaty_id: treatyId,
        version_id: versionId as string,
        candidate_id: candidateId,
      },
      body: { decision, value: value ?? null },
    });
    if (result.error) throw result.error;
  }

  const validate = useMutation({
    mutationFn: async () => {
      const result = await validateTreatyVersion({
        path: { treaty_id: treatyId, version_id: versionId as string },
      });
      if (!result.data) throw result.error;
      return result.data;
    },
    onSuccess: () => {
      setValidateError(null);
      queryClient.invalidateQueries({ queryKey: ["treaties", treatyId] });
    },
    onError: (err) => {
      const problem = asProblem(err);
      setValidateError(problem?.detail ?? "Could not validate the treaty yet.");
    },
  });

  const diffRows = (termDiff.data?.entries ?? []).filter(
    (e) => e.change === "changed" || e.change === "new",
  );

  const scalar = (workspace.data?.candidates ?? []).filter((c) => c.key !== "participation");
  const participations = (workspace.data?.candidates ?? []).filter(
    (c) => c.key === "participation",
  );
  const page = useMemo(
    () =>
      workspace.data?.pages.find((p) => p.page_number === activePage) ?? workspace.data?.pages[0],
    [workspace.data, activePage],
  );

  const outstanding = scalar.filter((c) => !c.resolution).length;

  if (treaty.data && treaty.data.treaty.current_version?.status === "validated") {
    return (
      <div className="space-y-4">
        <BackLink href={`/treaties/${treatyId}`}>Back to treaty</BackLink>
        <EmptyState
          title="This treaty version is already validated"
          action={
            <Button asChild size="sm" variant="secondary">
              <Link href={`/treaties/${treatyId}`}>View the treaty</Link>
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <BackLink href={`/treaties/${treatyId}`}>Back to treaty</BackLink>
      <PageHeader
        title="Validation workspace"
        description={`${treaty.data?.treaty.name ?? ""} — confirm each term against the treaty text.`}
        actions={
          <>
            {outstanding > 0 ? (
              <span className="text-sm text-muted-foreground">
                {outstanding} term{outstanding === 1 ? "" : "s"} not yet reviewed
              </span>
            ) : null}
            {validateError ? <span className="text-sm text-danger">{validateError}</span> : null}
            <Button onClick={() => validate.mutate()} disabled={validate.isPending}>
              {validate.isPending ? "Validating…" : "Validate treaty"}
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* LEFT — the treaty document */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Treaty document</CardTitle>
            {workspace.data && workspace.data.pages.length > 1 ? (
              <FilterTabs
                options={workspace.data.pages.map((p) => ({
                  label: String(p.page_number),
                  value: String(p.page_number),
                }))}
                value={String(page?.page_number ?? 1)}
                onChange={(v) => setActivePage(Number(v))}
              />
            ) : null}
          </CardHeader>
          <CardContent>
            <pre className="max-h-[34rem] overflow-auto whitespace-pre-wrap font-sans text-sm leading-relaxed">
              {page?.text ?? "—"}
            </pre>
          </CardContent>
        </Card>

        {/* RIGHT — proposed terms */}
        <div className="space-y-3">
          {diffRows.length > 0 ? (
            <Card className="border-warning/40 bg-warning/5">
              <CardHeader>
                <CardTitle>What the endorsement changed</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="text-muted-foreground">
                  Re-extraction of the endorsement document against the terms carried forward from
                  the previous version. Confirm each below.
                </p>
                <ul className="divide-y divide-border/70">
                  {diffRows.map((e) => (
                    <li key={e.key} className="flex items-baseline justify-between gap-3 py-2">
                      <span className="font-medium">{termLabel(e.key)}</span>
                      <span className="text-right">
                        {e.change === "changed" ? (
                          <>
                            <span className="text-muted-foreground line-through">
                              {e.carried_value}
                            </span>{" "}
                            <span className="font-mono">{e.extracted_value}</span>{" "}
                            <Badge tone="warning">changed</Badge>
                          </>
                        ) : (
                          <>
                            <span className="font-mono">{e.extracted_value}</span>{" "}
                            <Badge tone="info">new</Badge>
                          </>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          {scalar.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              submitReview={submitReview}
              onReviewed={invalidateCandidates}
              onJumpToPage={setActivePage}
            />
          ))}

          {participations.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Participations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {participations.map((p) => (
                  <ParticipationRow
                    key={p.id}
                    candidate={p}
                    submitReview={submitReview}
                    onReviewed={invalidateCandidates}
                  />
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}

type ReviewFn = (id: string, decision: ReviewDecision, value?: string) => Promise<void>;

function useReview(candidateId: string, submitReview: ReviewFn, onReviewed: () => void) {
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: (a: { decision: ReviewDecision; value?: string }) =>
      submitReview(candidateId, a.decision, a.value),
    onMutate: () => setError(null),
    onSuccess: onReviewed,
    onError: (e) => setError(asProblem(e)?.detail ?? "Could not save that review — try again."),
  });
  return { run: mutation.mutate, busy: mutation.isPending, error };
}

function CandidateCard({
  candidate,
  submitReview,
  onReviewed,
  onJumpToPage,
}: {
  candidate: TermCandidateOut;
  submitReview: ReviewFn;
  onReviewed: () => void;
  onJumpToPage: (page: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(
    (candidate.normalized_value as { value?: string } | null)?.value ?? candidate.raw_value ?? "",
  );
  const { run, busy, error } = useReview(candidate.id, submitReview, () => {
    setEditing(false);
    onReviewed();
  });

  const resolution = candidate.resolution ?? null;
  const confirmed = resolution === "confirmed";
  const rejected = resolution === "rejected";
  const shownValue =
    (candidate.normalized_value as { value?: string } | null)?.value ?? candidate.raw_value ?? null;
  const hasValue = shownValue !== null && shownValue !== "";

  return (
    <Card
      data-testid={`term-${candidate.key}`}
      data-resolution={resolution ?? "open"}
      className={cn(
        confirmed && "border-human/50 bg-human/5",
        rejected && "opacity-70",
        busy && "animate-pulse",
      )}
    >
      <CardContent className="space-y-2 py-4">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold">{termLabel(candidate.key)}</span>
          <div className="flex items-center gap-2">
            {resolution ? (
              <Badge tone={resolutionTone(resolution)}>
                {RESOLUTION_LABEL[resolution] ?? resolution}
              </Badge>
            ) : (
              <>
                <Badge tone={candidateTone(candidate.status)}>{candidate.status}</Badge>
                {candidate.confidence !== null ? (
                  <span className="text-xs text-muted-foreground">
                    {(candidate.confidence * 100).toFixed(0)}%
                  </span>
                ) : null}
              </>
            )}
          </div>
        </div>

        {editing ? (
          <Input value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
        ) : (
          <p className="font-mono text-sm">
            {shownValue ?? "— not found —"}
            {candidate.currency ? ` ${candidate.currency}` : ""}
          </p>
        )}

        {candidate.citation ? (
          <button
            type="button"
            onClick={() => onJumpToPage(candidate.citation?.page_number ?? 1)}
            className="block w-full rounded border-l-2 border-calculation/40 bg-calculation/5 px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-calculation/10"
          >
            <span className="font-medium text-calculation">
              p.{candidate.citation.page_number}
              {candidate.citation.section ? ` · ${candidate.citation.section}` : ""}
            </span>
            <span className="mt-0.5 block italic">“{candidate.citation.quoted_text}”</span>
          </button>
        ) : (
          <p className="text-xs text-warning">No citation — verify against the document.</p>
        )}

        {candidate.reasoning ? (
          <p className="text-xs text-muted-foreground">{candidate.reasoning}</p>
        ) : null}

        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          {editing ? (
            <>
              <Button size="sm" disabled={busy} onClick={() => run({ decision: "edit", value })}>
                {busy ? "Saving…" : "Save & confirm"}
              </Button>
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </>
          ) : resolution ? (
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => run({ decision: "confirm" })}
              title="Re-review this term"
            >
              Change decision
            </Button>
          ) : (
            <>
              <Button
                size="sm"
                data-testid={`term-confirm-${candidate.key}`}
                disabled={busy || !hasValue}
                title={hasValue ? undefined : "Add a value with Edit before confirming"}
                onClick={() => run({ decision: "confirm" })}
              >
                {busy ? "…" : "Confirm"}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => setEditing(true)}
              >
                {hasValue ? "Edit" : "Add value"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => run({ decision: "reject" })}
              >
                Reject
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => run({ decision: "mark_ambiguous" })}
              >
                Ambiguous
              </Button>
            </>
          )}
        </div>

        {error ? (
          <p className="rounded-md border border-danger/30 bg-danger/5 px-2 py-1.5 text-xs text-danger">
            {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ParticipationRow({
  candidate,
  submitReview,
  onReviewed,
}: {
  candidate: TermCandidateOut;
  submitReview: ReviewFn;
  onReviewed: () => void;
}) {
  const { run, busy, error } = useReview(candidate.id, submitReview, onReviewed);
  const data = (candidate.normalized_value ?? {}) as {
    reinsurer_name?: string;
    placed_share_percent?: number;
  };
  const resolution = candidate.resolution ?? null;

  return (
    <div
      data-testid="participation-row"
      data-resolution={resolution ?? "open"}
      className={cn(
        "flex items-center justify-between gap-3 rounded-md border border-border p-2.5 text-sm",
        resolution === "confirmed" && "border-human/50 bg-human/5",
        resolution === "rejected" && "opacity-70",
      )}
    >
      <span>
        <span className="font-medium">{data.reinsurer_name}</span>{" "}
        <span className="text-muted-foreground">{data.placed_share_percent}%</span>{" "}
        {resolution ? (
          <Badge tone={resolutionTone(resolution)}>
            {RESOLUTION_LABEL[resolution] ?? resolution}
          </Badge>
        ) : null}
        {error ? <span className="ml-2 text-xs text-danger">{error}</span> : null}
      </span>
      <div className="flex gap-1">
        <Button
          size="sm"
          variant={resolution === "confirmed" ? "ghost" : "secondary"}
          data-testid="participation-confirm"
          disabled={busy}
          onClick={() => run({ decision: "confirm" })}
        >
          {busy ? "…" : resolution === "confirmed" ? "Re-confirm" : "Confirm"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={busy}
          onClick={() => run({ decision: "reject" })}
        >
          Reject
        </Button>
      </div>
    </div>
  );
}
