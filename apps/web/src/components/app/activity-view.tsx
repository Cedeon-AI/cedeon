"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { actorTone, agentLabel, runStatusTone, usd } from "@/lib/activity";
import type { AgentRunSummary } from "@/lib/api";
import { getAgentRun, getAiSpend, listAgentRuns, listAuditEvents } from "@/lib/api";

type Tab = "runs" | "audit" | "spend";

export function ActivityView() {
  const [tab, setTab] = useState<Tab>("runs");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Activity</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          What the AI did, what happened, and what it cost. Every model call is recorded on{" "}
          <span className="font-mono text-xs">agent_runs</span>; every state transition on the
          append-only audit log.
        </p>
      </div>

      <div className="flex gap-1 text-sm">
        {(
          [
            ["runs", "AI runs"],
            ["audit", "Audit log"],
            ["spend", "AI spend"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={
              tab === key
                ? "rounded-md bg-muted px-3 py-1.5 font-medium"
                : "rounded-md px-3 py-1.5 text-muted-foreground hover:bg-muted/60"
            }
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "runs" ? <AgentRuns /> : null}
      {tab === "audit" ? <AuditLog /> : null}
      {tab === "spend" ? <AiSpend /> : null}
    </div>
  );
}

function AgentRuns() {
  const [selected, setSelected] = useState<string | null>(null);
  const runs = useQuery({
    queryKey: ["activity", "agent-runs"],
    queryFn: async () => (await listAgentRuns({ throwOnError: true })).data.runs,
    refetchInterval: (q) =>
      (q.state.data ?? []).some((r) => r.status === "running") ? 3000 : false,
  });

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
      <Card>
        <CardHeader>
          <CardTitle>Recent AI runs</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {runs.data && runs.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 pr-3 font-medium">Agent</th>
                  <th className="py-2 pr-3 font-medium">Model</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 text-right font-medium">Tokens</th>
                  <th className="py-2 pr-3 text-right font-medium">Cost</th>
                  <th className="py-2 pr-3 text-right font-medium">Latency</th>
                  <th className="py-2 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => setSelected(r.id)}
                    className={`cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40 ${
                      selected === r.id ? "bg-muted/60" : ""
                    }`}
                  >
                    <td className="py-2 pr-3 font-medium">{agentLabel(r.agent_type)}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{r.model}</td>
                    <td className="py-2 pr-3">
                      <Badge tone={runStatusTone(r.status)}>{r.status}</Badge>
                    </td>
                    <td className="py-2 pr-3 text-right text-muted-foreground">
                      {(r.input_tokens ?? 0) + (r.output_tokens ?? 0) || "—"}
                    </td>
                    <td className="py-2 pr-3 text-right text-muted-foreground">
                      {r.cost_usd ? usd(r.cost_usd) : "—"}
                    </td>
                    <td className="py-2 pr-3 text-right text-muted-foreground">
                      {r.latency_ms ? `${(r.latency_ms / 1000).toFixed(1)}s` : "—"}
                    </td>
                    <td className="py-2 text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">No AI runs yet.</p>
          )}
        </CardContent>
      </Card>

      <div>{selected ? <RunDetail runId={selected} /> : <RunHint />}</div>
    </div>
  );
}

function RunHint() {
  return (
    <Card>
      <CardContent className="py-8 text-center text-sm text-muted-foreground">
        Select a run to see its tools and output.
      </CardContent>
    </Card>
  );
}

function RunDetail({ runId }: { runId: string }) {
  const detail = useQuery({
    queryKey: ["activity", "agent-run", runId],
    queryFn: async () => (await getAgentRun({ path: { run_id: runId }, throwOnError: true })).data,
  });
  if (detail.isLoading || !detail.data) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-muted-foreground">Loading…</CardContent>
      </Card>
    );
  }
  const { run, tool_calls, output } = detail.data;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{agentLabel(run.agent_type)} run</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <dl className="space-y-1">
          <Row k="Model" v={run.model} />
          <Row k="Prompt" v={run.prompt_version ?? "—"} />
          <Row k="Status" v={run.status} />
          <Row k="Tokens" v={`${run.input_tokens ?? 0} in · ${run.output_tokens ?? 0} out`} />
          <Row k="Cost" v={run.cost_usd ? usd(run.cost_usd) : "—"} />
          <Row k="Latency" v={run.latency_ms ? `${(run.latency_ms / 1000).toFixed(1)}s` : "—"} />
          {run.correlation_id ? <Row k="Correlation" v={run.correlation_id} /> : null}
        </dl>
        {run.error ? (
          <p className="rounded-md border border-danger/30 bg-danger/5 p-2 text-xs text-danger">
            {run.error}
          </p>
        ) : null}
        {tool_calls.length > 0 ? (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Tool calls
            </p>
            <ol className="mt-1 space-y-1">
              {tool_calls.map((c) => (
                <li key={c.ordinal} className="rounded border border-border p-2 text-xs">
                  <span className="font-mono font-medium">{c.tool_name}</span>
                  <span className="ml-2 text-muted-foreground">{JSON.stringify(c.arguments)}</span>
                </li>
              ))}
            </ol>
          </div>
        ) : null}
        {output ? (
          <details>
            <summary className="cursor-pointer text-xs text-muted-foreground">
              Structured output
            </summary>
            <pre className="mt-1 max-h-80 overflow-auto rounded border border-border bg-muted/30 p-2 text-[11px]">
              {JSON.stringify(output, null, 2)}
            </pre>
          </details>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="text-right font-mono text-xs">{v}</dd>
    </div>
  );
}

function AuditLog() {
  const [action, setAction] = useState("");
  const events = useQuery({
    queryKey: ["activity", "audit", action],
    queryFn: async () => {
      const { data } = await listAuditEvents({
        query: { limit: 200, action: action || undefined },
        throwOnError: true,
      });
      return data.events;
    },
  });
  const actions = Array.from(new Set((events.data ?? []).map((e) => e.action))).sort();

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Audit log</CardTitle>
        <select
          value={action}
          onChange={(e) => setAction(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs"
        >
          <option value="">all actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </CardHeader>
      <CardContent>
        {events.data && events.data.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {events.data.map((e) => (
              <li key={e.id} className="border-b border-border/60 pb-2 last:border-0">
                <div className="flex items-center gap-2">
                  <Badge tone={actorTone(e.actor_type)}>{e.actor_type}</Badge>
                  <span className="font-mono text-xs text-muted-foreground">{e.action}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {new Date(e.occurred_at).toLocaleString()}
                  </span>
                </div>
                <p className="mt-0.5">{e.summary}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No audit events.</p>
        )}
      </CardContent>
    </Card>
  );
}

function AiSpend() {
  const spend = useQuery({
    queryKey: ["activity", "ai-spend"],
    queryFn: async () => (await getAiSpend({ query: { days: 30 }, throwOnError: true })).data,
  });
  if (spend.isLoading || !spend.data) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  const s = spend.data;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Runs (30d)" value={String(s.totals.runs)} />
        <Stat label="Succeeded" value={String(s.totals.succeeded)} tone="text-human" />
        <Stat label="Failed" value={String(s.totals.failed)} tone="text-danger" />
        <Stat label="Cost (30d)" value={usd(s.totals.cost_usd)} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>By agent</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">Agent</th>
                <th className="py-2 pr-3 text-right font-medium">Runs</th>
                <th className="py-2 pr-3 text-right font-medium">Failed</th>
                <th className="py-2 pr-3 text-right font-medium">Tokens</th>
                <th className="py-2 pr-3 text-right font-medium">Avg latency</th>
                <th className="py-2 text-right font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {s.by_type.map((t) => (
                <tr key={t.agent_type} className="border-b border-border/60 last:border-0">
                  <td className="py-2 pr-3 font-medium">{agentLabel(t.agent_type)}</td>
                  <td className="py-2 pr-3 text-right text-muted-foreground">{t.runs}</td>
                  <td className="py-2 pr-3 text-right text-muted-foreground">{t.failed}</td>
                  <td className="py-2 pr-3 text-right text-muted-foreground">
                    {t.input_tokens + t.output_tokens}
                  </td>
                  <td className="py-2 pr-3 text-right text-muted-foreground">
                    {t.avg_latency_ms ? `${(t.avg_latency_ms / 1000).toFixed(1)}s` : "—"}
                  </td>
                  <td className="py-2 text-right font-medium">{usd(t.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {s.by_day.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>By day</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {s.by_day.map((d) => (
              <div key={d.day} className="flex justify-between">
                <span className="text-muted-foreground">
                  {d.day} · {d.runs} run{d.runs === 1 ? "" : "s"}
                </span>
                <span className="font-medium">{usd(d.cost_usd)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-md border border-border p-3">
      <p className={`text-lg font-semibold ${tone ?? ""}`}>{value}</p>
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
    </div>
  );
}

export type { AgentRunSummary };
