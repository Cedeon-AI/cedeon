"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Wallet } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/field";
import { EmptyState } from "@/components/ui/page-header";
import type { RecoverableOut, RecoverableStatus } from "@/lib/api";
import {
  asProblem,
  listRecoverablesForCandidate,
  materializeRecoverables,
  updateRecoverable,
} from "@/lib/api";
import { AGING_LABEL, nextStatus, RECOVERABLE_STATUSES, recoverableStatus } from "@/lib/collection";
import { formatMoney } from "@/lib/utils";

export function RecoveryCollectionSection({
  candidateId,
  canTrack,
}: {
  candidateId: string;
  canTrack: boolean;
}) {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["recoverables", candidateId] });

  const recoverables = useQuery({
    queryKey: ["recoverables", candidateId],
    enabled: canTrack,
    queryFn: async () =>
      (
        await listRecoverablesForCandidate({
          path: { candidate_id: candidateId },
          throwOnError: true,
        })
      ).data.recoverables,
  });

  const materialize = useMutation({
    mutationFn: async () => {
      const result = await materializeRecoverables({ path: { candidate_id: candidateId } });
      if (!result.data) throw result.error;
    },
    onSuccess: invalidate,
  });

  if (!canTrack) {
    return (
      <EmptyState
        icon={<Wallet />}
        title="Collection tracking is not open yet"
        description="Confirm the recovery, then track each reinsurer's leg from notified to cash collected."
      />
    );
  }

  const rows = recoverables.data ?? [];
  const num = (v: string | null | undefined) => Number(v ?? 0);
  const totals = rows.reduce(
    (acc, r) => ({
      expected: acc.expected + num(r.expected_amount),
      collected: acc.collected + num(r.collected_amount),
      outstanding: acc.outstanding + num(r.outstanding),
    }),
    { expected: 0, collected: 0, outstanding: 0 },
  );
  const currency = rows[0]?.currency ?? "USD";

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight">Collection</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          One leg per reinsurer, from the confirmed calculation. Expected is a fact; agreed, billed
          and collected are yours to record.
        </p>
      </div>

      {recoverables.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Wallet />}
          title="No recoverables yet"
          description="Create one leg per reinsurer from this recovery's allocation."
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() => materialize.mutate()}
              disabled={materialize.isPending}
            >
              {materialize.isPending ? "Creating…" : "Start collection tracking"}
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            {[
              { k: "Expected", v: totals.expected, tone: "text-fact" },
              { k: "Collected", v: totals.collected, tone: "text-human" },
              { k: "Outstanding", v: totals.outstanding, tone: "text-calculation" },
            ].map((s) => (
              <div key={s.k} className="rounded-lg border border-border bg-card p-3 shadow-xs">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {s.k}
                </p>
                <p className={`mt-1 font-mono text-lg font-semibold tracking-tight ${s.tone}`}>
                  {formatMoney(s.v, currency)}
                </p>
              </div>
            ))}
          </div>

          <Card>
            <CardContent className="overflow-x-auto p-0">
              <table className="w-full min-w-208 text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr className="border-b border-border">
                    <th className="px-4 py-2.5 font-medium">Reinsurer</th>
                    <th className="px-2 py-2.5 font-medium">Status</th>
                    <th className="px-2 py-2.5 text-right font-medium">Expected</th>
                    <th className="px-2 py-2.5 text-right font-medium">Collected</th>
                    <th className="px-2 py-2.5 text-right font-medium">Outstanding</th>
                    <th className="px-2 py-2.5 font-medium">Due</th>
                    <th className="px-2 py-2.5 font-medium">Next</th>
                    <th className="px-4 py-2.5" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <RecoverableRow key={r.id} recoverable={r} onUpdated={invalidate} />
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function RecoverableRow({
  recoverable: r,
  onUpdated,
}: {
  recoverable: RecoverableOut;
  onUpdated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ agreed_amount: "", collect: "", due_date: "", note: "" });
  const [error, setError] = useState<string | null>(null);
  const s = recoverableStatus(r.status);
  const advance = nextStatus(r.status);
  const overdue = r.days_overdue > 0;

  const update = useMutation({
    mutationFn: async (body: Record<string, string>) => {
      const result = await updateRecoverable({ path: { recoverable_id: r.id }, body });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      setError(null);
      setForm({ agreed_amount: "", collect: "", due_date: "", note: "" });
      setOpen(false);
      onUpdated();
    },
    onError: (err) => {
      const p = asProblem(err);
      setError(p?.detail ?? p?.title ?? "Could not update the recoverable.");
    },
  });

  const submitForm = () => {
    const body: Record<string, string> = {};
    if (form.agreed_amount.trim()) body.agreed_amount = form.agreed_amount.trim();
    if (form.collect.trim()) body.collect = form.collect.trim();
    if (form.due_date) body.due_date = form.due_date;
    if (form.note.trim()) body.note = form.note.trim();
    if (Object.keys(body).length === 0) return;
    update.mutate(body);
  };

  return (
    <>
      <tr className="border-b border-border/60 last:border-0">
        <td className="px-4 py-2.5 font-medium">{r.reinsurer_name}</td>
        <td className="px-2 py-2.5">
          <Badge tone={s.tone}>{s.label}</Badge>
        </td>
        <td className="px-2 py-2.5 text-right font-mono text-xs">
          {formatMoney(r.expected_amount, r.currency)}
        </td>
        <td className="px-2 py-2.5 text-right font-mono text-xs">
          {formatMoney(r.collected_amount, r.currency)}
        </td>
        <td className="px-2 py-2.5 text-right font-mono text-xs">
          {formatMoney(r.outstanding, r.currency)}
        </td>
        <td className="px-2 py-2.5 text-xs">
          {r.due_date ? (
            <span className={overdue ? "text-danger" : "text-muted-foreground"}>
              {r.due_date}
              {overdue ? ` · ${AGING_LABEL[r.aging_bucket]}` : ""}
            </span>
          ) : (
            <span className="text-muted-foreground/50">—</span>
          )}
        </td>
        <td className="px-2 py-2.5 text-xs">
          {r.next_action !== "done" ? (
            <span className={r.next_action_urgent ? "text-danger" : "text-muted-foreground"}>
              {r.next_action_text}
            </span>
          ) : null}
        </td>
        <td className="px-4 py-2.5 text-right">
          <div className="flex justify-end gap-1.5">
            {advance ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => update.mutate({ status: advance })}
                disabled={update.isPending}
              >
                Mark {recoverableStatus(advance).label.toLowerCase()}
              </Button>
            ) : null}
            <Button size="sm" variant="ghost" onClick={() => setOpen((v) => !v)}>
              {open ? "Close" : "Update"}
            </Button>
          </div>
        </td>
      </tr>
      {r.reconciliation.length > 0 ? (
        <tr className="border-b border-border/60">
          <td colSpan={8} className="px-4 pb-2.5">
            <div className="rounded-md border-l-2 border-danger/50 bg-danger/5 px-3 py-2 text-xs">
              <span className="font-semibold text-danger">Doesn't reconcile</span>
              <ul className="mt-1 space-y-0.5 text-muted-foreground">
                {r.reconciliation.map((f) => (
                  <li key={f.kind}>{f.text}</li>
                ))}
              </ul>
            </div>
          </td>
        </tr>
      ) : null}
      {open ? (
        <tr className="border-b border-border/60 bg-muted/30">
          <td colSpan={8} className="px-4 py-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Agreed amount" htmlFor={`ag-${r.id}`}>
                <Input
                  id={`ag-${r.id}`}
                  inputMode="decimal"
                  value={form.agreed_amount}
                  onChange={(e) => setForm({ ...form, agreed_amount: e.target.value })}
                  placeholder={r.agreed_amount ?? r.expected_amount}
                />
              </Field>
              <Field label="Record a collection" htmlFor={`co-${r.id}`}>
                <Input
                  id={`co-${r.id}`}
                  inputMode="decimal"
                  value={form.collect}
                  onChange={(e) => setForm({ ...form, collect: e.target.value })}
                  placeholder="amount received"
                />
              </Field>
              <Field label="Due date" htmlFor={`du-${r.id}`}>
                <Input
                  id={`du-${r.id}`}
                  type="date"
                  value={form.due_date}
                  onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                />
              </Field>
              <Field label="Set status" htmlFor={`st-${r.id}`}>
                <Select
                  id={`st-${r.id}`}
                  value=""
                  onChange={(e) => e.target.value && update.mutate({ status: e.target.value })}
                >
                  <option value="">— unchanged —</option>
                  {RECOVERABLE_STATUSES.map((st) => (
                    <option key={st} value={st}>
                      {recoverableStatus(st as RecoverableStatus).label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Note" htmlFor={`no-${r.id}`}>
                <Input
                  id={`no-${r.id}`}
                  value={form.note}
                  onChange={(e) => setForm({ ...form, note: e.target.value })}
                  placeholder={r.note ?? "internal note"}
                />
              </Field>
            </div>
            {error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
            <div className="mt-3">
              <Button size="sm" onClick={submitForm} disabled={update.isPending}>
                {update.isPending ? "Saving…" : "Save"}
              </Button>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}
