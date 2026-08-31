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
  getTreaty,
  listTermCandidates,
  reviewTermCandidate,
  validateTreatyVersion,
} from "@/lib/api";
import { candidateTone, termLabel } from "@/lib/treaties";

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

  const review = useMutation({
    mutationFn: async (args: { candidateId: string; decision: ReviewDecision; value?: string }) => {
      await reviewTermCandidate({
        path: {
          treaty_id: treatyId,
          version_id: versionId as string,
          candidate_id: args.candidateId,
        },
        body: { decision: args.decision, value: args.value ?? null },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["term-candidates", versionId] });
    },
  });

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

  const scalar = (workspace.data?.candidates ?? []).filter((c) => c.key !== "participation");
  const participations = (workspace.data?.candidates ?? []).filter(
    (c) => c.key === "participation",
  );
  const page = useMemo(
    () =>
      workspace.data?.pages.find((p) => p.page_number === activePage) ?? workspace.data?.pages[0],
    [workspace.data, activePage],
  );

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
          {scalar.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              onReview={(decision, value) =>
                review.mutate({ candidateId: candidate.id, decision, value })
              }
              onJumpToPage={setActivePage}
            />
          ))}

          {participations.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Participations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {participations.map((p) => {
                  const data = (p.normalized_value ?? {}) as {
                    reinsurer_name?: string;
                    placed_share_percent?: number;
                  };
                  return (
                    <div
                      key={p.id}
                      className="flex items-center justify-between rounded-md border border-border p-2.5 text-sm"
                    >
                      <span>
                        <span className="font-medium">{data.reinsurer_name}</span>{" "}
                        <span className="text-muted-foreground">{data.placed_share_percent}%</span>
                        {p.resolution === "confirmed" ? (
                          <Badge tone="success">confirmed</Badge>
                        ) : null}
                      </span>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => review.mutate({ candidateId: p.id, decision: "confirm" })}
                        >
                          Confirm
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => review.mutate({ candidateId: p.id, decision: "reject" })}
                        >
                          Reject
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function CandidateCard({
  candidate,
  onReview,
  onJumpToPage,
}: {
  candidate: TermCandidateOut;
  onReview: (decision: ReviewDecision, value?: string) => void;
  onJumpToPage: (page: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(
    (candidate.normalized_value as { value?: string } | null)?.value ?? candidate.raw_value ?? "",
  );
  const confirmed = candidate.resolution === "confirmed";
  const rejected = candidate.resolution === "rejected";

  return (
    <Card className={confirmed ? "border-human/40" : rejected ? "opacity-60" : undefined}>
      <CardContent className="space-y-2 py-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">{termLabel(candidate.key)}</span>
          <div className="flex items-center gap-2">
            <Badge tone={candidateTone(candidate.status)}>{candidate.status}</Badge>
            {candidate.confidence !== null ? (
              <span className="text-xs text-muted-foreground">
                {(candidate.confidence * 100).toFixed(0)}%
              </span>
            ) : null}
          </div>
        </div>

        {editing ? (
          <Input value={value} onChange={(e) => setValue(e.target.value)} />
        ) : (
          <p className="font-mono text-sm">
            {(candidate.normalized_value as { value?: string } | null)?.value ??
              candidate.raw_value ??
              "— not found —"}
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

        <div className="flex flex-wrap gap-1.5 pt-1">
          {editing ? (
            <>
              <Button size="sm" onClick={() => onReview("edit", value)}>
                Save &amp; confirm
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button size="sm" onClick={() => onReview("confirm")}>
                Confirm
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button size="sm" variant="ghost" onClick={() => onReview("reject")}>
                Reject
              </Button>
              <Button size="sm" variant="ghost" onClick={() => onReview("mark_ambiguous")}>
                Ambiguous
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
