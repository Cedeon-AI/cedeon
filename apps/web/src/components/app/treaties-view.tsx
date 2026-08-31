"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, ScrollText } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, PageHeader } from "@/components/ui/page-header";
import { listTreaties } from "@/lib/api";
import { isBusy, versionStatus } from "@/lib/treaties";

export function TreatiesView() {
  const treaties = useQuery({
    queryKey: ["treaties"],
    queryFn: async () => (await listTreaties({ throwOnError: true })).data.treaties,
    refetchInterval: (q) =>
      (q.state.data ?? []).some((t) => t.current_version && isBusy(t.current_version.status))
        ? 2500
        : false,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Treaties"
        description="Your reinsurance program — the contracts Cedeon runs recoveries against."
        actions={
          <Button asChild size="sm">
            <Link href="/treaties/new">
              <Plus /> Set up a treaty
            </Link>
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Treaties</CardTitle>
        </CardHeader>
        <CardContent>
          {treaties.data && treaties.data.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 font-medium">Treaty</th>
                  <th className="py-2 font-medium">Cedent</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {treaties.data.map((t) => {
                  const s = t.current_version ? versionStatus(t.current_version.status) : null;
                  return (
                    <tr key={t.id} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5">
                        <Link
                          href={`/treaties/${t.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {t.name}
                        </Link>
                      </td>
                      <td className="py-2.5 text-muted-foreground">{t.cedent_name}</td>
                      <td className="py-2.5">{s ? <Badge tone={s.tone}>{s.label}</Badge> : "—"}</td>
                      <td className="py-2.5 text-right">
                        {t.current_version?.status === "needs_validation" ? (
                          <Link
                            href={`/treaties/${t.id}/validate`}
                            className="text-sm font-medium text-primary hover:underline"
                          >
                            Validate →
                          </Link>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon={<ScrollText />}
              title="No treaties yet"
              description="Set up your first treaty — upload the wording and Cedeon extracts the terms."
              action={
                <Button asChild size="sm" variant="secondary">
                  <Link href="/treaties/new">Set up a treaty</Link>
                </Button>
              }
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
