"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { BackLink, EmptyState, PageHeader } from "@/components/ui/page-header";
import type { NoticeKind, RecoveryNoticeOut } from "@/lib/api";
import {
  asProblem,
  draftRecoveryNotice,
  getRecoveryCandidate,
  listRecoveryNotices,
  reviewRecoveryNotice,
} from "@/lib/api";
import { NOTICE_KINDS, noticeKindLabel, noticeStatus } from "@/lib/notice";

const EMPTY_RECIPIENT = { name: "", organisation: "", role: "", email: "" };

export function RecoveryNoticesView({ candidateId }: { candidateId: string }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<NoticeKind>("initial_loss_advice");
  const [recipient, setRecipient] = useState(EMPTY_RECIPIENT);
  const [error, setError] = useState<string | null>(null);

  const candidate = useQuery({
    queryKey: ["recovery-candidates", candidateId, "status"],
    queryFn: async () =>
      (await getRecoveryCandidate({ path: { candidate_id: candidateId }, throwOnError: true })).data
        .candidate,
  });

  const notices = useQuery({
    queryKey: ["recovery-notices", candidateId],
    queryFn: async () => {
      const { data } = await listRecoveryNotices({
        path: { candidate_id: candidateId },
        throwOnError: true,
      });
      return data.notices;
    },
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["recovery-notices", candidateId] });

  const confirmed =
    candidate.data?.status === "confirmed" || candidate.data?.status === "notice_drafted";
  const current = (notices.data ?? []).find((n) => !n.superseded) ?? null;

  const draft = useMutation({
    mutationFn: async () => {
      const result = await draftRecoveryNotice({
        path: { candidate_id: candidateId },
        body: { kind, recipient },
      });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      setError(null);
      // The job runs on the worker; poll until a notice lands.
      const stop = setInterval(() => invalidate(), 2500);
      setTimeout(() => clearInterval(stop), 30000);
      invalidate();
    },
    onError: (e) => {
      const p = asProblem(e);
      setError(p?.detail ?? p?.title ?? "Could not queue the drafter.");
    },
  });

  return (
    <div className="space-y-6">
      <BackLink href={`/recovery-candidates/${candidateId}`}>Recovery candidate</BackLink>
      <PageHeader
        title="Notices"
        description={
          <>
            Drafted from a whitelist of approved facts only, after the recovery is confirmed. Every
            draft is for human review — <strong>Cedeon never sends anything.</strong>
          </>
        }
      />

      {!confirmed ? (
        <EmptyState
          icon={<FileText />}
          title="Recovery not confirmed yet"
          description="Confirm the recovery candidate before drafting a notice."
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Draft a notice</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-3 md:grid-cols-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (recipient.name.trim() && recipient.organisation.trim()) draft.mutate();
              }}
            >
              <Field label="Notice type" htmlFor="n-kind">
                <Select
                  id="n-kind"
                  value={kind}
                  onChange={(e) => setKind(e.target.value as NoticeKind)}
                >
                  {NOTICE_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {noticeKindLabel(k)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Recipient organisation" htmlFor="n-org">
                <Input
                  id="n-org"
                  value={recipient.organisation}
                  onChange={(e) => setRecipient({ ...recipient, organisation: e.target.value })}
                  placeholder="Reinsurer Alpha"
                />
              </Field>
              <Field label="Recipient name" htmlFor="n-name">
                <Input
                  id="n-name"
                  value={recipient.name}
                  onChange={(e) => setRecipient({ ...recipient, name: e.target.value })}
                  placeholder="Jane Underwriter"
                />
              </Field>
              <Field label="Recipient role (optional)" htmlFor="n-role">
                <Input
                  id="n-role"
                  value={recipient.role}
                  onChange={(e) => setRecipient({ ...recipient, role: e.target.value })}
                  placeholder="Claims Manager"
                />
              </Field>
              <div className="md:col-span-2">
                <Button type="submit" disabled={draft.isPending}>
                  {draft.isPending ? "Queuing…" : "Draft notice"}
                </Button>
                {error ? <span className="ml-3 text-sm text-danger">{error}</span> : null}
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {current ? <NoticeCard notice={current} onReviewed={invalidate} /> : null}

      {(notices.data ?? []).length > 1 ? (
        <Card>
          <CardHeader>
            <CardTitle>History</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {notices.data?.map((n) => (
              <div key={n.id} className="flex justify-between">
                <span className="text-muted-foreground">
                  {noticeKindLabel(n.kind)} · {new Date(n.created_at).toLocaleString()}
                </span>
                <Badge tone={noticeStatus(n.status).tone}>{noticeStatus(n.status).label}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function NoticeCard({ notice, onReviewed }: { notice: RecoveryNoticeOut; onReviewed: () => void }) {
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(notice.subject);
  const [body, setBody] = useState(notice.body_markdown);
  const [reason, setReason] = useState("");
  const status = noticeStatus(notice.status);
  const open = notice.status === "draft";

  const review = useMutation({
    mutationFn: async (args: { decision: string; withEdit?: boolean }) => {
      const result = await reviewRecoveryNotice({
        path: { notice_id: notice.id },
        body: {
          decision: args.decision as never,
          reason: reason.trim() || null,
          subject: args.withEdit ? subject : null,
          body_markdown: args.withEdit ? body : null,
        },
      });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      setEditing(false);
      setReason("");
      onReviewed();
    },
  });

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle>{noticeKindLabel(notice.kind)}</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            to {notice.recipient.name}
            {notice.recipient.role ? `, ${notice.recipient.role}` : ""} ·{" "}
            {notice.recipient.organisation}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          {notice.used_only_provided_facts ? (
            <Badge tone="success">approved facts only</Badge>
          ) : (
            <Badge tone="warning">check facts</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {editing ? (
          <>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="min-h-64 p-3 font-mono text-xs"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={() => review.mutate({ decision: "edit", withEdit: true })}>
                Save edit
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm font-medium">{notice.subject}</p>
            <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 font-sans text-sm">
              {notice.body_markdown}
            </pre>
          </>
        )}

        {notice.caveats.length > 0 ? (
          <div className="text-xs text-muted-foreground">
            <p className="font-medium">Caveats stated in the notice</p>
            <ul className="mt-1 list-disc pl-5">
              {notice.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {notice.notes_for_reviewer ? (
          <p className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            Before sending: {notice.notes_for_reviewer}
          </p>
        ) : null}

        {open && !editing ? (
          <div className="space-y-2">
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Optional note (recorded with the decision)"
            />
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => review.mutate({ decision: "confirm" })}>
                Approve
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => review.mutate({ decision: "request_info" })}
              >
                Request info
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => review.mutate({ decision: "reject" })}
              >
                Reject
              </Button>
            </div>
          </div>
        ) : null}
        {notice.status === "approved" ? (
          <p className="text-xs text-muted-foreground">
            Approved{notice.approved_at ? ` ${new Date(notice.approved_at).toLocaleString()}` : ""}.
            Cedeon does not send — take the text from here.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
