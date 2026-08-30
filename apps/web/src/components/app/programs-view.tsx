"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderTree, Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/field";
import { EmptyState, PageHeader } from "@/components/ui/page-header";
import { createCedent, createProgram, listCedents, listPrograms } from "@/lib/api";

export function ProgramsView() {
  const queryClient = useQueryClient();
  const [cedentName, setCedentName] = useState("");
  const [form, setForm] = useState({ cedent_id: "", name: "", treaty_year: "2027" });

  const cedents = useQuery({
    queryKey: ["cedents"],
    queryFn: async () => (await listCedents({ throwOnError: true })).data.cedents,
  });
  const programs = useQuery({
    queryKey: ["programs"],
    queryFn: async () => (await listPrograms({ throwOnError: true })).data.programs,
  });

  const addCedent = useMutation({
    mutationFn: async (name: string) => {
      const { data } = await createCedent({ body: { name }, throwOnError: true });
      return data;
    },
    onSuccess: () => {
      setCedentName("");
      queryClient.invalidateQueries({ queryKey: ["cedents"] });
    },
  });

  const addProgram = useMutation({
    mutationFn: async () => {
      const { data } = await createProgram({
        body: {
          cedent_id: form.cedent_id,
          name: form.name,
          treaty_year: Number(form.treaty_year),
        },
        throwOnError: true,
      });
      return data;
    },
    onSuccess: () => {
      setForm({ cedent_id: "", name: "", treaty_year: "2027" });
      queryClient.invalidateQueries({ queryKey: ["programs"] });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Programs"
        description="A reinsurance program groups a cedent's treaties for a treaty year."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Add a cedent</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="flex gap-2"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                if (cedentName.trim()) addCedent.mutate(cedentName.trim());
              }}
            >
              <Input
                value={cedentName}
                onChange={(e) => setCedentName(e.target.value)}
                placeholder="Atlantic Specialty Insurance Company"
              />
              <Button type="submit" disabled={addCedent.isPending}>
                Add
              </Button>
            </form>
            <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
              {cedents.data?.map((c) => (
                <li key={c.id}>{c.name}</li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Add a program</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                if (form.cedent_id && form.name.trim()) addProgram.mutate();
              }}
            >
              <Field label="Cedent" htmlFor="cedent">
                <Select
                  id="cedent"
                  value={form.cedent_id}
                  onChange={(e) => setForm({ ...form, cedent_id: e.target.value })}
                >
                  <option value="">Select a cedent…</option>
                  {cedents.data?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Program name" htmlFor="pname">
                <Input
                  id="pname"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="2027 Property Catastrophe Program"
                />
              </Field>
              <Field label="Treaty year" htmlFor="pyear">
                <Input
                  id="pyear"
                  type="number"
                  value={form.treaty_year}
                  onChange={(e) => setForm({ ...form, treaty_year: e.target.value })}
                />
              </Field>
              <Button type="submit" disabled={addProgram.isPending}>
                <Plus /> {addProgram.isPending ? "Creating…" : "Create program"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Programs</CardTitle>
        </CardHeader>
        <CardContent>
          {programs.data && programs.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">Program</th>
                  <th className="py-2 font-medium">Cedent</th>
                  <th className="py-2 font-medium">Year</th>
                  <th className="py-2 font-medium">Treaties</th>
                </tr>
              </thead>
              <tbody>
                {programs.data.map((p) => (
                  <tr key={p.id} className="border-b border-border/60 last:border-0">
                    <td className="py-2.5 font-medium">{p.name}</td>
                    <td className="py-2.5 text-muted-foreground">{p.cedent_name}</td>
                    <td className="py-2.5 text-muted-foreground">{p.treaty_year}</td>
                    <td className="py-2.5 text-muted-foreground">{p.treaty_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon={<FolderTree />}
              title="No programs yet"
              description="Add a cedent, then create a program above."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
