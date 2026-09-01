"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { asProblem, getCurrentOrganization, getCurrentUser, renameOrganization } from "@/lib/api";

export function SettingsOrganizationView() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => (await getCurrentUser({ throwOnError: true })).data,
  });
  const org = useQuery({
    queryKey: ["organization"],
    queryFn: async () => (await getCurrentOrganization({ throwOnError: true })).data,
  });
  const isAdmin = me.data?.role === "admin";

  useEffect(() => {
    if (org.data && name === "") setName(org.data.name);
  }, [org.data, name]);

  const rename = useMutation({
    mutationFn: async () => {
      const result = await renameOrganization({ body: { name: name.trim() } });
      if (result.error) throw result.error;
    },
    onSuccess: () => {
      setError(null);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["organization"] });
    },
    onError: (err) => setError(asProblem(err)?.detail ?? "Could not rename the organization."),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Organization" description="Your Cedeon workspace." />
      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Organization name" htmlFor="org-name">
            <Input
              id="org-name"
              value={name}
              disabled={!isAdmin}
              onChange={(e) => {
                setName(e.target.value);
                setSaved(false);
              }}
              className="max-w-md"
            />
          </Field>
          <p className="text-xs text-muted-foreground">
            The workspace identifier ({org.data?.slug ?? "…"}) never changes, so links and
            references stay stable.
          </p>
          {isAdmin ? (
            <div className="flex items-center gap-3">
              <Button
                onClick={() => rename.mutate()}
                disabled={rename.isPending || !name.trim() || name.trim() === org.data?.name}
              >
                {rename.isPending ? "Saving…" : "Save"}
              </Button>
              {saved ? <span className="text-xs text-human">Saved.</span> : null}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Only an admin can rename the organization.
            </p>
          )}
          {error ? <p className="text-sm text-danger">{error}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
