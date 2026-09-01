"use client";

import { useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import {
  AlarmClock,
  ArrowRight,
  Check,
  FileText,
  FileWarning,
  Hourglass,
  Scale,
  ScrollText,
  Sigma,
  Sparkles,
  TrendingUp,
  Upload,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, PageHeader, Stat } from "@/components/ui/page-header";
import type { AttentionCategory, WorklistItemOut, WorklistKind } from "@/lib/api";
import { getCurrentUser, getWorklist, listMembers } from "@/lib/api";
import { cn, formatMoneyCompact } from "@/lib/utils";
import { CATEGORY_LABEL, CATEGORY_ORDER, worklistClock, worklistKind } from "@/lib/worklist";

const ICON: Record<WorklistKind, LucideIcon> = {
  notice_due: AlarmClock,
  recovery_drift: TrendingUp,
  contract_change: FileWarning,
  reconciliation_mismatch: Scale,
  recovery_review: Sigma,
  suggested_recovery: Sparkles,
  packet_approval: FileText,
  term_validation: ScrollText,
  recoverable_overdue: Hourglass,
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
  const worklist = useQuery({
    queryKey: ["worklist"],
    queryFn: async () => (await getWorklist({ throwOnError: true })).data,
    refetchInterval: 60_000,
  });

  const items = worklist.data?.items ?? [];
  const s = worklist.data?.summary;

  const byCategory = CATEGORY_ORDER.map((cat) => ({
    cat,
    rows: items.filter((i) => i.category === cat),
  })).filter((g) => g.rows.length > 0);
  const showCategoryHeaders = byCategory.length > 1;

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

      {/* ---------------------------------------------------- Needs you */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight">Needs you</h2>
          {items.length > 0 ? (
            <span className="text-xs text-muted-foreground">{items.length} open</span>
          ) : null}
        </div>
        {worklist.isLoading ? (
          <Card>
            <CardContent className="p-5 text-sm text-muted-foreground">Loading…</CardContent>
          </Card>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Check />}
            title="You're all caught up"
            description="Nothing is waiting on you. Recoveries, obligations, and contract changes land here as Cedeon spots them."
          />
        ) : showCategoryHeaders ? (
          <div className="space-y-4">
            {byCategory.map((group) => (
              <div key={group.cat} className="space-y-1.5">
                <CategoryHeader cat={group.cat} count={group.rows.length} />
                <Card>
                  <ul className="divide-y divide-border/70">
                    {group.rows.map((item) => (
                      <WorklistRow key={item.key} item={item} />
                    ))}
                  </ul>
                </Card>
              </div>
            ))}
          </div>
        ) : (
          <Card>
            <ul className="divide-y divide-border/70">
              {items.map((item) => (
                <WorklistRow key={item.key} item={item} />
              ))}
            </ul>
          </Card>
        )}
      </section>

      {/* ---------------------------------------------------------------- At a glance */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-muted-foreground">At a glance</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Open recoverable"
            value={s ? formatMoneyCompact(s.open_recoverable, s.currency) : "—"}
            icon={<Wallet />}
            tone="calculation"
          />
          <Stat
            label="Overdue"
            value={s ? formatMoneyCompact(s.overdue_outstanding, s.currency) : "—"}
            hint={s && Number(s.overdue_outstanding) > 0 ? "past the due date" : "nothing overdue"}
            tone="fact"
          />
          <Stat
            label="Largest open recovery"
            value={
              s?.largest_open_recovery
                ? formatMoneyCompact(s.largest_open_recovery, s.currency)
                : "—"
            }
            icon={<Sigma />}
            tone="calculation"
          />
          <Stat
            label="Needs you"
            value={s ? String(s.open_count) : "—"}
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
            href="/recovery-candidates/new"
            icon={<Sigma />}
            title="Start a recovery"
            body="Event → claims → responding treaty → a deterministic recovery figure."
          />
          <QuickLink
            href="/recoverables"
            icon={<Wallet />}
            title="Recoverables"
            body="Every reinsurer's leg — expected, collected, and how overdue the rest is."
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

function CategoryHeader({ cat, count }: { cat: AttentionCategory; count: number }) {
  return (
    <div className="flex items-center gap-2 px-1">
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
        {CATEGORY_LABEL[cat] ?? cat}
      </span>
      <span className="text-[11px] text-muted-foreground/50">{count}</span>
    </div>
  );
}

function WorklistRow({ item }: { item: WorklistItemOut }) {
  const kind = worklistKind(item.kind);
  const Icon = ICON[item.kind] ?? Sigma;
  const clock = worklistClock(item);

  return (
    <li>
      <Link
        href={item.href}
        className="group flex items-center gap-3 px-5 py-3.5 transition first:rounded-t-xl last:rounded-b-xl hover:bg-muted/50"
      >
        <span
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-lg [&_svg]:size-4",
            kind.tone === "danger"
              ? "bg-danger/10 text-danger"
              : kind.tone === "warning"
                ? "bg-warning/15 text-warning"
                : "bg-calculation/10 text-calculation",
          )}
        >
          <Icon />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">{item.title}</span>
            <Badge tone={kind.tone}>{kind.label}</Badge>
          </span>
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.detail}</span>
        </span>
        <span className="flex shrink-0 flex-col items-end gap-0.5 text-right">
          {item.amount ? (
            <span className="font-mono text-xs tabular-nums">
              {formatMoneyCompact(item.amount, item.currency ?? "USD")}
            </span>
          ) : null}
          {clock ? (
            <span
              className={cn(
                "text-[11px]",
                clock.overdue ? "font-medium text-danger" : "text-muted-foreground",
              )}
            >
              {clock.text}
            </span>
          ) : null}
        </span>
        <ArrowRight className="size-4 shrink-0 text-muted-foreground/50 transition group-hover:text-foreground" />
      </Link>
    </li>
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
