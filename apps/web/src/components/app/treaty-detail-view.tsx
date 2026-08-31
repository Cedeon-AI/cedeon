"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { NoticeProvisionEditor } from "@/components/app/notice-provision-editor";
import { RecoveryPreview } from "@/components/app/recovery-preview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BackLink, PageHeader } from "@/components/ui/page-header";
import { getTreaty } from "@/lib/api";
import { formatShare, isBusy, termLabel, versionStatus } from "@/lib/treaties";
import { formatMoney } from "@/lib/utils";

export function TreatyDetailView({ treatyId }: { treatyId: string }) {
  const treaty = useQuery({
    queryKey: ["treaties", treatyId],
    queryFn: async () => {
      const { data } = await getTreaty({ path: { treaty_id: treatyId }, throwOnError: true });
      return data;
    },
    refetchInterval: (q) =>
      q.state.data?.current_version && isBusy(q.state.data.current_version.status) ? 2500 : false,
  });

  const version = treaty.data?.current_version;
  const status = version ? versionStatus(version.status) : null;
  const layer = version?.layers[0];

  return (
    <div className="space-y-6">
      <BackLink href="/treaties">Treaties</BackLink>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            {treaty.data?.treaty.name ?? "Treaty"}
            {status ? <Badge tone={status.tone}>{status.label}</Badge> : null}
          </span>
        }
        description={`${treaty.data?.treaty.cedent_name ?? ""} · ${treaty.data?.treaty.program_name ?? ""}`}
        actions={
          version?.status === "needs_validation" ? (
            <Button asChild size="sm">
              <Link href={`/treaties/${treatyId}/validate`}>Validate terms</Link>
            </Button>
          ) : undefined
        }
      />

      {version?.status === "needs_validation" ? (
        <Card className="border-warning/40 bg-warning/5">
          <CardContent className="flex items-center justify-between py-4">
            <p className="text-sm">
              Cedeon extracted the treaty terms. Validate them to make this treaty executable.
            </p>
            <Link href={`/treaties/${treatyId}/validate`}>
              <Button size="sm">Open validation workspace</Button>
            </Link>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Layer</CardTitle>
          </CardHeader>
          <CardContent>
            {layer ? (
              <div className="space-y-1">
                <p className="text-2xl font-semibold tracking-tight">
                  {formatMoney(layer.limit, layer.currency)}{" "}
                  <span className="text-base font-normal text-muted-foreground">excess of</span>{" "}
                  {formatMoney(layer.attachment, layer.currency)}
                </p>
                <p className="text-xs text-muted-foreground">Per occurrence · {layer.currency}</p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Not yet validated — no executable layer.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Participants</CardTitle>
          </CardHeader>
          <CardContent>
            {version && version.participations.length > 0 ? (
              <ul className="divide-y divide-border text-sm">
                {version.participations.map((p) => (
                  <li key={p.reinsurer_id} className="flex justify-between py-2">
                    <span>{p.reinsurer_name}</span>
                    <span className="font-medium">{formatShare(p.placed_share)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No confirmed participants.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {version?.status === "validated" || version?.status === "active" ? (
        <RecoveryPreview treatyId={treatyId} />
      ) : null}

      {version?.source_document_id ? (
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Source document</CardTitle>
            <Link
              href={`/documents/${version.source_document_id}`}
              className="text-sm font-medium text-primary hover:underline"
            >
              Open the wording →
            </Link>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              The contract PDF Cedeon parsed and extracted the terms from. Every validated term
              cites a page and clause in it.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {version && version.status !== "draft" && version.status !== "parsing" ? (
        <NoticeProvisionEditor
          treatyId={treatyId}
          versionId={version.id}
          term={version.terms.find((t) => t.key === "notice_provision")}
        />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Validated terms</CardTitle>
        </CardHeader>
        <CardContent>
          {version && version.terms.filter((t) => t.key !== "participation").length > 0 ? (
            <dl className="grid gap-3 sm:grid-cols-2">
              {version.terms
                .filter((t) => t.key !== "participation")
                .map((t) => (
                  <div key={t.key} className="rounded-md border border-border p-3">
                    <dt className="text-xs font-medium uppercase tracking-wide text-human">
                      {termLabel(t.key)}
                    </dt>
                    <dd className="mt-1 text-sm">
                      {String((t.value as { value?: string }).value ?? "—")}
                    </dd>
                  </div>
                ))}
            </dl>
          ) : (
            <p className="text-sm text-muted-foreground">
              Terms appear here once confirmed in the validation workspace.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
