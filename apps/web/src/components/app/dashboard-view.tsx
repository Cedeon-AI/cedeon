"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getCurrentUser, listMembers } from "@/lib/api";

const PIPELINE_METRICS = [
  { label: "Treaties", phase: "Phase 3" },
  { label: "Loss events", phase: "Phase 5" },
  { label: "Recovery candidates", phase: "Phase 6" },
  { label: "Needs review", phase: "Phase 8" },
];

export function DashboardView() {
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const { data } = await getCurrentUser({ throwOnError: true });
      return data;
    },
  });

  const members = useQuery({
    queryKey: ["memberships"],
    queryFn: async () => {
      const { data } = await listMembers({ throwOnError: true });
      return data;
    },
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {me.isLoading
            ? "Loading…"
            : `Signed in as ${me.data?.user.name ?? me.data?.user.email} · ${me.data?.role}`}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-muted-foreground">Organization</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{me.data?.organization.name ?? "—"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-muted-foreground">Members</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">
              {members.data ? members.data.members.length : "—"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-muted-foreground">Your role</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold capitalize">{me.data?.role ?? "—"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-muted-foreground">Session expires</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium text-muted-foreground">
              {me.data ? new Date(me.data.session.expires_at).toLocaleString() : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="text-sm font-semibold tracking-tight text-muted-foreground">
          Recovery pipeline
        </h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PIPELINE_METRICS.map((metric) => (
            <Card key={metric.label} className="border-dashed">
              <CardHeader>
                <CardTitle className="text-muted-foreground">{metric.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold text-muted-foreground/50">—</p>
                <p className="mt-1 text-xs text-muted-foreground">Arrives in {metric.phase}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
        </CardHeader>
        <CardContent>
          {members.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <ul className="divide-y divide-border text-sm">
              {members.data?.members.map((member) => (
                <li key={member.user_id} className="flex items-center justify-between py-2">
                  <span>
                    <span className="font-medium">{member.name}</span>{" "}
                    <span className="text-muted-foreground">{member.email}</span>
                  </span>
                  <span className="capitalize text-muted-foreground">{member.role}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
