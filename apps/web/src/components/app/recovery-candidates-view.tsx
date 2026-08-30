"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import type { RecoveryCandidateStatus } from "@/lib/api";
import {
  asProblem,
  createRecoveryCandidate,
  listLossEvents,
  listRecoveryCandidates,
  listTreaties,
} from "@/lib/api";
import { CANDIDATE_FILTERS, candidateStatus } from "@/lib/recoveries";
import { formatMoney } from "@/lib/utils";

export function RecoveryCandidatesView() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [filter, setFilter] = useState<RecoveryCandidateStatus | "">("");
  const [form, setForm] = useState({ treaty_id: "", loss_event_id: "" });
  const [error, setError] = useState<string | null>(null);

  const candidates = useQuery({
    queryKey: ["recovery-candidates", filter],
    queryFn: async () => {
      const { data } = await listRecoveryCandidates({
        query: filter ? { status: filter } : undefined,
        throwOnError: true,
      });
      return data.candidates;
    },
  });
  const treaties = useQuery({
    queryKey: ["treaties"],
    queryFn: async () => (await listTreaties({ throwOnError: true })).data.treaties,
  });
  const events = useQuery({
    queryKey: ["loss-events"],
    queryFn: async () => (await listLossEvents({ throwOnError: true })).data.events,
  });

  const validatedTreaties = (treaties.data ?? []).filter(
    (t) => t.current_version?.status === "validated" || t.current_version?.status === "active",
  );

  const create = useMutation({
    mutationFn: async () => {
      const result = await createRecoveryCandidate({
        body: { treaty_id: form.treaty_id, loss_event_id: form.loss_event_id },
      });
      if (!result.data) throw result.error;
      return result.data;
    },
    onSuccess: (candidate) => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["recovery-candidates"] });
      router.push(`/recovery-candidates/${candidate.id}`);
    },
    onError: (err) => {
      const problem = asProblem(err);
      setError(problem?.detail ?? problem?.title ?? "Could not create the candidate.");
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Recovery candidates</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          A validated treaty plus a loss event, run through the deterministic engine. The number is
          code, not an LLM — you review and confirm it.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New recovery candidate</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-3 md:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (form.treaty_id && form.loss_event_id) create.mutate();
            }}
          >
            <Field label="Validated treaty" htmlFor="rc-treaty">
              <select
                id="rc-treaty"
                value={form.treaty_id}
                onChange={(e) => setForm({ ...form, treaty_id: e.target.value })}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">Select…</option>
                {validatedTreaties.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Loss event" htmlFor="rc-event">
              <select
                id="rc-event"
                value={form.loss_event_id}
                onChange={(e) => setForm({ ...form, loss_event_id: e.target.value })}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">Select…</option>
                {events.data?.map((evt) => (
                  <option key={evt.id} value={evt.id}>
                    {evt.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="flex items-end">
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Calculating…" : "Create & calculate"}
              </Button>
            </div>
            {validatedTreaties.length === 0 ? (
              <p className="text-xs text-muted-foreground md:col-span-3">
                No validated treaties yet — validate one in the Treaty Library first.
              </p>
            ) : null}
            {error ? <p className="text-sm text-danger md:col-span-3">{error}</p> : null}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Queue</CardTitle>
          <div className="flex gap-1 text-xs">
            {CANDIDATE_FILTERS.map((f) => (
              <button
                key={f.value || "all"}
                type="button"
                onClick={() => setFilter(f.value)}
                className={
                  filter === f.value
                    ? "rounded bg-primary px-2 py-1 text-primary-foreground"
                    : "rounded px-2 py-1 text-muted-foreground hover:bg-muted"
                }
              >
                {f.label}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {candidates.data && candidates.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">Created</th>
                  <th className="py-2 font-medium">Gross event incurred</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {candidates.data.map((c) => {
                  const s = candidateStatus(c.status);
                  return (
                    <tr key={c.id} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5 text-muted-foreground">
                        {new Date(c.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-2.5">
                        {formatMoney(c.gross_event_incurred, c.currency)}
                        {c.currency_mismatch ? (
                          <Badge tone="warning">currency mismatch</Badge>
                        ) : null}
                      </td>
                      <td className="py-2.5">
                        <Badge tone={s.tone}>{s.label}</Badge>
                      </td>
                      <td className="py-2.5 text-right">
                        <Link
                          href={`/recovery-candidates/${c.id}`}
                          className="text-sm font-medium text-primary hover:underline"
                        >
                          Open →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">No recovery candidates in this view.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
