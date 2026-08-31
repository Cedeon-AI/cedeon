"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/field";
import type { DeadlineBasis, NoticeTrigger, TermOut } from "@/lib/api";
import { asProblem, setTreatyNoticeTerm } from "@/lib/api";

type NoticeValue = {
  value?: string;
  days?: number;
  trigger?: NoticeTrigger;
  basis?: DeadlineBasis;
};

export function NoticeProvisionEditor({
  treatyId,
  versionId,
  term,
}: {
  treatyId: string;
  versionId: string;
  term: TermOut | undefined;
}) {
  const queryClient = useQueryClient();
  const v = (term?.value ?? {}) as NoticeValue;
  const [text, setText] = useState(v.value ?? "");
  const [days, setDays] = useState(v.days ? String(v.days) : "");
  const [trigger, setTrigger] = useState<NoticeTrigger | "">(v.trigger ?? "");
  const [basis, setBasis] = useState<DeadlineBasis>(v.basis ?? "calendar");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = useMutation({
    mutationFn: async () => {
      const structured = days.trim() !== "" && trigger !== "";
      const result = await setTreatyNoticeTerm({
        path: { treaty_id: treatyId, version_id: versionId },
        body: {
          provision_text: text.trim(),
          period_days: structured ? Number(days) : null,
          trigger: structured ? (trigger as NoticeTrigger) : null,
          basis,
        },
      });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      setError(null);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["treaties", treatyId] });
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not save the notice provision."),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notice provision</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          The clause as written, plus — where you can state it — the deadline in structured form.
          Cedeon computes the actual date against each loss; it never guesses it.
        </p>
        <Field label="Clause (as written)" htmlFor="np-text">
          <Input
            id="np-text"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setSaved(false);
            }}
            placeholder="Notice within 30 days of knowledge of a loss likely to involve the reinsurers"
          />
        </Field>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Period (days)" htmlFor="np-days">
            <Input
              id="np-days"
              type="number"
              inputMode="numeric"
              value={days}
              onChange={(e) => {
                setDays(e.target.value);
                setSaved(false);
              }}
              placeholder="30"
            />
          </Field>
          <Field label="From" htmlFor="np-trigger">
            <Select
              id="np-trigger"
              value={trigger}
              onChange={(e) => {
                setTrigger(e.target.value as NoticeTrigger | "");
                setSaved(false);
              }}
            >
              <option value="">— pick a trigger —</option>
              <option value="loss_occurrence">Date of loss</option>
              <option value="knowledge_of_loss">Date of knowledge</option>
              <option value="claim_advice">First claim advice</option>
            </Select>
          </Field>
          <Field label="Counted in" htmlFor="np-basis">
            <Select
              id="np-basis"
              value={basis}
              onChange={(e) => {
                setBasis(e.target.value as DeadlineBasis);
                setSaved(false);
              }}
            >
              <option value="calendar">Calendar days</option>
              <option value="business">Business days</option>
            </Select>
          </Field>
        </div>
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <div className="flex items-center gap-3">
          <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending || !text.trim()}>
            {save.isPending ? "Saving…" : "Save notice provision"}
          </Button>
          {saved ? <span className="text-xs text-human">Saved.</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}
