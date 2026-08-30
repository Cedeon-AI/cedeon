"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import type { PacketStatementOut, RecoveryPacketVersionOut } from "@/lib/api";
import {
  asProblem,
  generateRecoveryPacket,
  getRecoveryPacket,
  reviewRecoveryPacketVersion,
} from "@/lib/api";
import { packetVersionStatus, statementClass } from "@/lib/packet";

export function RecoveryPacketView({ candidateId }: { candidateId: string }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const packet = useQuery({
    queryKey: ["recovery-packet", candidateId],
    queryFn: async () => {
      const result = await getRecoveryPacket({ path: { candidate_id: candidateId } });
      return result.data ?? null; // 404 → no packet yet
    },
    retry: false,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["recovery-packet", candidateId] });

  const generate = useMutation({
    mutationFn: async () => {
      const result = await generateRecoveryPacket({ path: { candidate_id: candidateId } });
      if (!result.data) throw result.error;
    },
    onSuccess: invalidate,
  });

  const detail = packet.data;
  const version = detail?.current_version ?? null;
  const packetId = detail?.packet_id ?? null;

  const review = useMutation({
    mutationFn: async (args: { decision: string; statement_key?: string; value?: string }) => {
      if (!packetId || !version) return;
      const result = await reviewRecoveryPacketVersion({
        path: { packet_id: packetId, version_id: version.id },
        body: {
          decision: args.decision as never,
          reason: reason.trim() || null,
          statement_key: args.statement_key ?? null,
          value: args.value ?? null,
        },
      });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      setReason("");
      setEditing(null);
      invalidate();
    },
  });

  const reviewProblem = asProblem(review.error);

  if (packet.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/recovery-candidates/${candidateId}`}
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Recovery candidate
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">Recovery packet</h1>
          {version ? (
            <Badge tone={packetVersionStatus(version.status).tone}>
              v{version.version_no} · {packetVersionStatus(version.status).label}
            </Badge>
          ) : null}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          An audit-friendly artifact. Every statement is one of four classes; AI statements carry
          their citation. Nothing here is computed — it assembles the deterministic calculation, the
          investigator's findings, and your decisions.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
          {generate.isPending ? "Assembling…" : version ? "Regenerate" : "Generate packet"}
        </Button>
        {version && packetId ? (
          <a
            href={`/api/recovery-packets/${packetId}/versions/${version.id}/html`}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-primary hover:underline"
          >
            Open printable HTML →
          </a>
        ) : null}
      </div>

      {!version ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No packet yet. Generate one once the candidate has a calculation.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
          <div className="space-y-4">
            {version.content.sections.map((section) => (
              <Card key={section.key}>
                <CardHeader>
                  <CardTitle>{section.title}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {section.statements.map((s) => (
                    <StatementRow
                      key={s.key}
                      statement={s}
                      editable={version.status === "draft"}
                      editing={editing === s.key}
                      editValue={editValue}
                      onStartEdit={() => {
                        setEditing(s.key);
                        setEditValue(s.text);
                      }}
                      onCancel={() => setEditing(null)}
                      onChange={setEditValue}
                      onSave={() =>
                        review.mutate({
                          decision: "edit",
                          statement_key: s.key,
                          value: editValue,
                        })
                      }
                    />
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="space-y-4">
            <ReviewCard
              version={version}
              reason={reason}
              onReason={setReason}
              onReview={(decision) => review.mutate({ decision })}
              pending={review.isPending}
              error={reviewProblem?.detail ?? reviewProblem?.title ?? null}
            />
            {detail && detail.versions.length > 1 ? (
              <Card>
                <CardHeader>
                  <CardTitle>Versions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 text-sm">
                  {detail.versions.map((v) => (
                    <div key={v.id} className="flex justify-between">
                      <span className="text-muted-foreground">
                        v{v.version_no}
                        {v.id === version.id ? " · current" : ""}
                      </span>
                      <Badge tone={packetVersionStatus(v.status).tone}>
                        {packetVersionStatus(v.status).label}
                      </Badge>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

function StatementRow({
  statement,
  editable,
  editing,
  editValue,
  onStartEdit,
  onCancel,
  onChange,
  onSave,
}: {
  statement: PacketStatementOut;
  editable: boolean;
  editing: boolean;
  editValue: string;
  onStartEdit: () => void;
  onCancel: () => void;
  onChange: (v: string) => void;
  onSave: () => void;
}) {
  const meta = statementClass(statement.statement_class);
  return (
    <div className={`rounded-r border-l-4 ${meta.color} px-3 py-2`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide">{meta.label}</span>
        <div className="flex items-center gap-2">
          {statement.edited_by_human ? (
            <span className="text-[11px] font-semibold text-human">✎ edited</span>
          ) : null}
          {editable && !editing ? (
            <button
              type="button"
              onClick={onStartEdit}
              className="text-[11px] text-primary hover:underline"
            >
              edit
            </button>
          ) : null}
        </div>
      </div>
      {editing ? (
        <div className="mt-1 space-y-2">
          <Input value={editValue} onChange={(e) => onChange(e.target.value)} />
          <div className="flex gap-2">
            <Button size="sm" onClick={onSave}>
              Save (new version)
            </Button>
            <Button size="sm" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-1 text-sm">{statement.text}</p>
      )}
      {statement.citation?.quoted_text ? (
        <p className="mt-1 border-l-2 border-border pl-2 text-xs text-muted-foreground">
          {statement.citation.page_number ? `p.${statement.citation.page_number}` : ""}
          {statement.citation.section ? ` · ${statement.citation.section}` : ""}
          <span className="mt-0.5 block italic">“{statement.citation.quoted_text}”</span>
        </p>
      ) : null}
    </div>
  );
}

function ReviewCard({
  version,
  reason,
  onReason,
  onReview,
  pending,
  error,
}: {
  version: RecoveryPacketVersionOut;
  reason: string;
  onReason: (v: string) => void;
  onReview: (decision: string) => void;
  pending: boolean;
  error: string | null;
}) {
  const open = version.status === "draft";
  return (
    <Card>
      <CardHeader>
        <CardTitle>Review</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {open ? (
          <>
            <textarea
              value={reason}
              onChange={(e) => onReason(e.target.value)}
              placeholder="Optional note (recorded with the decision)"
              className="min-h-16 w-full rounded-md border border-input bg-background p-2 text-sm"
            />
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => onReview("confirm")} disabled={pending}>
                Approve
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => onReview("request_info")}
                disabled={pending}
              >
                Request changes
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onReview("reject")}
                disabled={pending}
              >
                Reject
              </Button>
            </div>
          </>
        ) : (
          <p className="text-sm">
            {packetVersionStatus(version.status).label}
            {version.approved_at ? ` · ${new Date(version.approved_at).toLocaleString()}` : ""}
          </p>
        )}
        {version.review_note ? (
          <p className="text-xs text-muted-foreground">Note: {version.review_note}</p>
        ) : null}
        {error ? <p className="text-sm text-danger">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
