"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, ScrollText, Sigma, Upload, Waves } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, PageHeader, Stat } from "@/components/ui/page-header";
import {
  getCurrentUser,
  listLossEvents,
  listMembers,
  listRecoveryCandidates,
  listTreaties,
} from "@/lib/api";
import { candidateStatus } from "@/lib/recoveries";

type Task = {
  key: string;
  href: string;
  label: string;
  detail: string;
  tone: "warning" | "info";
};

export function DashboardView() {
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => (await getCurrentUser({ throwOnError: true })).data,
  });
  const members = useQuery({
    queryKey: ["memberships"],
    queryFn: async () => (await listMembers({ throwOnError: true })).data,
  });
  const treaties = useQuery({
    queryKey: ["treaties"],
    queryFn: async () => (await listTreaties({ throwOnError: true })).data.treaties,
  });
  const events = useQuery({
    queryKey: ["loss-events"],
    queryFn: async () => (await listLossEvents({ throwOnError: true })).data.events,
  });
  const recoveries = useQuery({
    queryKey: ["recovery-candidates", ""],
    queryFn: async () => (await listRecoveryCandidates({ throwOnError: true })).data.candidates,
  });

  const count = (q: { data?: unknown[] }) => (q.data ? String(q.data.length) : "—");

  const needsValidation = (treaties.data ?? []).filter(
    (t) => t.current_version?.status === "needs_validation",
  );
  const needsReview = (recoveries.data ?? []).filter((r) =>
    ["needs_review", "in_review"].includes(r.status),
  );

  const tasks: Task[] = [
    ...needsValidation.map((t) => ({
      key: `treaty-${t.id}`,
      href: `/treaties/${t.id}/validate`,
      label: `Validate proposed terms — ${t.name}`,
      detail: `${t.cedent_name} · extracted, awaiting your confirmation`,
      tone: "warning" as const,
    })),
    ...needsReview.map((r) => ({
      key: `recovery-${r.id}`,
      href: `/recovery-candidates/${r.id}`,
      label: "Review a recovery calculation",
      detail: `${candidateStatus(r.status).label} · created ${new Date(r.created_at).toLocaleDateString()}`,
      tone: "info" as const,
    })),
  ];

  const loading = treaties.isLoading || recoveries.isLoading;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Home"
        description={
          me.isLoading
            ? "Loading…"
            : `${me.data?.user.name ?? me.data?.user.email} · ${me.data?.role} · ${me.data?.organization.name}`
        }
      />

      {/* ---------------------------------------------------- Needs your attention */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight">Needs your attention</h2>
          {tasks.length > 0 ? (
            <span className="text-xs text-muted-foreground">{tasks.length} open</span>
          ) : null}
        </div>
        {loading ? (
          <Card>
            <CardContent className="p-5 text-sm text-muted-foreground">Loading…</CardContent>
          </Card>
        ) : tasks.length === 0 ? (
          <EmptyState
            icon={<Check />}
            title="You're all caught up"
            description="Nothing is waiting on you right now."
          />
        ) : (
          <Card>
            <ul className="divide-y divide-border/70">
              {tasks.map((task) => (
                <li key={task.key}>
                  <Link
                    href={task.href}
                    className="group flex items-center gap-3 px-5 py-3.5 transition first:rounded-t-xl last:rounded-b-xl hover:bg-muted/50"
                  >
                    <span
                      className={
                        task.tone === "warning"
                          ? "size-1.5 shrink-0 rounded-full bg-warning"
                          : "size-1.5 shrink-0 rounded-full bg-calculation"
                      }
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{task.label}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {task.detail}
                      </span>
                    </span>
                    <ArrowRight className="size-4 shrink-0 text-muted-foreground/50 transition group-hover:text-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      {/* ---------------------------------------------------------------- At a glance */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-muted-foreground">At a glance</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Treaties" value={count(treaties)} icon={<ScrollText />} tone="fact" />
          <Stat label="Loss events" value={count(events)} icon={<Waves />} tone="fact" />
          <Stat label="Recoveries" value={count(recoveries)} icon={<Sigma />} tone="calculation" />
          <Stat
            label="Needs review"
            value={recoveries.data ? String(needsReview.length) : "—"}
            icon={<Check />}
            tone="human"
          />
        </div>
      </section>

      {/* ------------------------------------------------------------------ Get started */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-muted-foreground">Get started</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <QuickLink
            href="/treaties/new"
            icon={<Upload />}
            title="Set up a treaty"
            body="Upload the wording; Cedeon extracts the terms for you to validate."
          />
          <QuickLink
            href="/loss-imports"
            icon={<Upload />}
            title="Import claims"
            body="Map a claims CSV into a loss event."
          />
          <QuickLink
            href="/recovery-candidates"
            icon={<Sigma />}
            title="Run a recovery"
            body="Pair a validated treaty with a loss event and calculate."
          />
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Team</CardTitle>
        </CardHeader>
        <CardContent>
          {members.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <ul className="divide-y divide-border/70 text-sm">
              {members.data?.members.map((member) => (
                <li key={member.user_id} className="flex items-center justify-between py-2.5">
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

function QuickLink({
  href,
  icon,
  title,
  body,
}: {
  href: string;
  icon: ReactNode;
  title: string;
  body: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Card interactive className="h-full">
        <CardContent className="pt-5">
          <span className="inline-flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary [&_svg]:size-4">
            {icon}
          </span>
          <p className="mt-3 flex items-center gap-1 font-medium">
            {title}
            <ArrowRight className="size-3.5 -translate-x-1 opacity-0 transition group-hover:translate-x-0 group-hover:opacity-100" />
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{body}</p>
        </CardContent>
      </Card>
    </Link>
  );
}
