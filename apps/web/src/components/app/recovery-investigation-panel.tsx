"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RecoveryInvestigationOut } from "@/lib/api";
import { asProblem, investigateRecoveryCandidate } from "@/lib/api";
import { applicability, findingKind } from "@/lib/recoveries";

export function RecoveryInvestigationPanel({
  candidateId,
  investigations,
}: {
  candidateId: string;
  investigations: RecoveryInvestigationOut[];
}) {
  const queryClient = useQueryClient();
  const current = investigations.find((i) => !i.superseded) ?? investigations[0] ?? null;
  const running = investigations.some((i) => i.status === "running");

  const investigate = useMutation({
    mutationFn: async () => {
      const result = await investigateRecoveryCandidate({
        path: { candidate_id: candidateId },
      });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      // The job runs on the worker; poll the detail until a result lands.
      queryClient.invalidateQueries({ queryKey: ["recovery-candidates", candidateId] });
    },
    onError: () => {},
  });

  const problem = asProblem(investigate.error);
  const app = current ? applicability(current.applicability_assessment) : null;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          AI investigation <Badge tone="ai">AI interpretation</Badge>
        </CardTitle>
        <Button
          size="sm"
          variant={current ? "ghost" : "primary"}
          onClick={() => investigate.mutate()}
          disabled={investigate.isPending || running}
        >
          {running || investigate.isPending
            ? "Investigating…"
            : current
              ? "Investigate again"
              : "Investigate"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          A bounded, read-only agent. It explains whether the treaty responds and cites the wording
          — it never computes the recovery figure. A human reviews every statement.
        </p>

        {problem ? <p className="text-sm text-danger">{problem.detail ?? problem.title}</p> : null}

        {!current ? (
          running ? (
            <p className="text-sm text-muted-foreground">
              Investigation queued — this updates when the worker finishes.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">Not investigated yet.</p>
          )
        ) : current.status === "failed" ? (
          <p className="text-sm text-danger">The investigation failed. Try again.</p>
        ) : current.status === "running" ? (
          <p className="text-sm text-muted-foreground">Investigation in progress…</p>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              {app ? <Badge tone={app.tone}>{app.label}</Badge> : null}
              {current.out_of_scope ? <Badge tone="warning">out of scope</Badge> : null}
              {current.suspected_prompt_injection ? (
                <Badge tone="danger">suspected injection</Badge>
              ) : null}
              {current.confidence !== null ? (
                <span className="text-xs text-muted-foreground">
                  confidence {(current.confidence * 100).toFixed(0)}%
                </span>
              ) : null}
            </div>

            {current.suspected_prompt_injection ? (
              <p className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
                The agent flagged text in the treaty document that tried to instruct it. Its
                analysis continued from the genuine wording.
              </p>
            ) : null}

            {current.summary ? (
              <p className="rounded-md border-l-2 border-ai/40 bg-ai/5 px-3 py-2 text-sm">
                {current.summary}
              </p>
            ) : null}

            <ul className="space-y-2">
              {current.findings.map((f) => {
                const k = findingKind(f.kind);
                return (
                  <li key={f.ordinal} className="rounded-md border border-border p-2.5 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <Badge tone={k.tone}>{k.label}</Badge>
                      {f.confidence !== null ? (
                        <span className="text-[11px] text-muted-foreground">
                          {(f.confidence * 100).toFixed(0)}%
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1.5">{f.text}</p>
                    {f.citation ? (
                      <p className="mt-1 border-l-2 border-ai/40 bg-ai/5 px-2 py-1 text-xs text-muted-foreground">
                        <span className="font-medium text-ai">
                          p.{f.citation.page_number}
                          {f.citation.section ? ` · ${f.citation.section}` : ""}
                        </span>
                        <span className="mt-0.5 block italic">“{f.citation.quoted_text}”</span>
                      </p>
                    ) : null}
                  </li>
                );
              })}
            </ul>

            {current.unresolved_questions.length > 0 ? (
              <div className="text-sm">
                <p className="font-medium">Unresolved questions</p>
                <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                  {current.unresolved_questions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
