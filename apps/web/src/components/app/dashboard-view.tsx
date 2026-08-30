"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileText, ScrollText, Sigma, Upload, Waves } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader, Stat } from "@/components/ui/page-header";
import {
  getCurrentUser,
  listDocuments,
  listLossEvents,
  listMembers,
  listRecoveryCandidates,
  listTreaties,
} from "@/lib/api";

export function DashboardView() {
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => (await getCurrentUser({ throwOnError: true })).data,
  });
  const members = useQuery({
    queryKey: ["memberships"],
    queryFn: async () => (await listMembers({ throwOnError: true })).data,
  });
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: async () => (await listDocuments({ throwOnError: true })).data.documents,
  });
  const treaties = useQuery({
    queryKey: ["treaties"],
    queryFn: async () => (await listTreaties({ throwOnError: true })).data.treaties,
  });
  const events = useQuery({
    queryKey: ["loss-events"],
    queryFn: async () => (await listLossEvents({ throwOnError: true })).data.events,
  });
  const candidates = useQuery({
    queryKey: ["recovery-candidates", ""],
    queryFn: async () => (await listRecoveryCandidates({ throwOnError: true })).data.candidates,
  });

  const count = (q: { data?: unknown[] }) => (q.data ? String(q.data.length) : "—");
  const needsReview = candidates.data?.filter((c) =>
    ["needs_review", "in_review"].includes(c.status),
  ).length;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description={
          me.isLoading
            ? "Loading…"
            : `Signed in as ${me.data?.user.name ?? me.data?.user.email} · ${me.data?.role} · ${me.data?.organization.name}`
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Documents"
          value={count(documents)}
          icon={<FileText />}
          tone="fact"
          hint="Uploaded & parsed"
        />
        <Stat
          label="Treaties"
          value={count(treaties)}
          icon={<ScrollText />}
          tone="fact"
          hint="In the library"
        />
        <Stat
          label="Loss events"
          value={count(events)}
          icon={<Waves />}
          tone="fact"
          hint="From committed imports"
        />
        <Stat
          label="Recovery candidates"
          value={count(candidates)}
          icon={<Sigma />}
          tone="calculation"
          hint={
            needsReview !== undefined && needsReview > 0
              ? `${needsReview} awaiting review`
              : "Deterministic calculations"
          }
        />
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-muted-foreground">
          Move through the pipeline
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <QuickLink
            href="/documents"
            icon={<Upload />}
            title="Upload a treaty"
            body="Add a PDF or DOCX and let Cedeon parse its structure."
          />
          <QuickLink
            href="/treaties"
            icon={<ScrollText />}
            title="Validate terms"
            body="Confirm AI-proposed terms with citations before they become executable."
          />
          <QuickLink
            href="/loss-imports"
            icon={<Upload />}
            title="Import losses"
            body="Map a CSV of claims into an underlying loss dataset."
          />
          <QuickLink
            href="/recovery-candidates"
            icon={<Sigma />}
            title="Run a recovery"
            body="Pair a validated treaty with a loss event and calculate."
          />
          <QuickLink
            href="/recovery-candidates"
            icon={<FileText />}
            title="Review a packet"
            body="Check the evidence-backed artifact before it is final."
          />
          <QuickLink
            href="/activity"
            icon={<Waves />}
            title="Audit activity"
            body="Every agent run, tool call and human decision on the record."
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
