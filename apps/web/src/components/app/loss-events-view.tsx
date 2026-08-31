"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Upload, Waves } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import { EmptyState, PageHeader } from "@/components/ui/page-header";
import { createLossEvent, listLossEvents } from "@/lib/api";
import { formatMoney } from "@/lib/utils";

export function LossEventsView() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    catastrophe_code: "",
    peril: "",
    hours_clause_hours: "",
  });

  const events = useQuery({
    queryKey: ["loss-events"],
    queryFn: async () => (await listLossEvents({ throwOnError: true })).data.events,
  });

  const add = useMutation({
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
    onSuccess: () => {
      setForm({ name: "", catastrophe_code: "", peril: "", hours_clause_hours: "" });
      queryClient.invalidateQueries({ queryKey: ["loss-events"] });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Loss events"
        description="A loss event groups claims from one occurrence. Import a claims CSV to create or extend one, or create it here and commit into it."
        actions={
          <Button asChild size="sm" variant="secondary">
            <Link href="/loss-imports">
              <Upload /> Import claims
            </Link>
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>New loss event</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-3 md:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (form.name.trim()) add.mutate();
            }}
          >
            <Field label="Name" htmlFor="evtname">
              <Input
                id="evtname"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Hurricane Demo 2027"
              />
            </Field>
            <Field label="Catastrophe code (optional)" htmlFor="evtcode">
              <Input
                id="evtcode"
                value={form.catastrophe_code}
                onChange={(e) => setForm({ ...form, catastrophe_code: e.target.value })}
                placeholder="PCS 2027-XX"
              />
            </Field>
            <Field label="Peril (optional)" htmlFor="evtperil">
              <Input
                id="evtperil"
                value={form.peril}
                onChange={(e) => setForm({ ...form, peril: e.target.value })}
                placeholder="Named windstorm"
              />
            </Field>
            <Field label="Hours clause (optional)" htmlFor="evthours">
              <Input
                id="evthours"
                type="number"
                inputMode="numeric"
                value={form.hours_clause_hours}
                onChange={(e) => setForm({ ...form, hours_clause_hours: e.target.value })}
                placeholder="168"
              />
            </Field>
            <div className="md:col-span-3">
              <Button type="submit" disabled={add.isPending}>
                <Plus /> {add.isPending ? "Creating…" : "Create event"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Events</CardTitle>
        </CardHeader>
        <CardContent>
          {events.data && events.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">Event</th>
                  <th className="py-2 font-medium">Dates</th>
                  <th className="py-2 font-medium">Claims</th>
                  <th className="py-2 text-right font-medium">Gross incurred</th>
                </tr>
              </thead>
              <tbody>
                {events.data.map((evt) => {
                  const claims = evt.totals.reduce((sum, t) => sum + t.claim_count, 0);
                  return (
                    <tr key={evt.id} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5">
                        <Link
                          href={`/loss-events/${evt.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {evt.name}
                        </Link>
                      </td>
                      <td className="py-2.5 text-muted-foreground">
                        {evt.date_of_loss_from
                          ? `${evt.date_of_loss_from} → ${evt.date_of_loss_to}`
                          : "—"}
                      </td>
                      <td className="py-2.5 text-muted-foreground">{claims}</td>
                      <td className="py-2.5 text-right font-medium">
                        {evt.totals.length > 0
                          ? evt.totals
                              .map((t) => formatMoney(t.gross_incurred, t.currency))
                              .join(" · ")
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon={<Waves />}
              title="No loss events yet"
              description="Create one above, or commit a loss import."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
