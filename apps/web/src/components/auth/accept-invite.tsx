"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { acceptInvitation, asProblem, previewInvitation } from "@/lib/api";

export function AcceptInvite({ token }: { token: string }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const preview = useQuery({
    queryKey: ["invitation", token],
    retry: false,
    queryFn: async () => (await previewInvitation({ path: { token }, throwOnError: true })).data,
  });

  async function accept(body: { name?: string; password?: string }) {
    setError(null);
    setPending(true);
    const result = await acceptInvitation({ path: { token }, body });
    setPending(false);
    if (!result.data) {
      setError(asProblem(result.error)?.detail ?? "Could not accept the invitation.");
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  if (preview.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (preview.isError || !preview.data) {
    return (
      <div className="space-y-3 text-sm">
        <p className="text-danger">This invitation link is not valid.</p>
        <Link href="/login" className="font-medium text-primary hover:underline">
          Go to sign in
        </Link>
      </div>
    );
  }

  const p = preview.data;

  if (p.expired) {
    return (
      <div className="space-y-3 text-sm">
        <p>
          Your invitation to <span className="font-medium">{p.organization_name}</span> has expired.
          Ask {p.invited_by_name ?? "an admin"} to send a new one.
        </p>
        <Link href="/login" className="font-medium text-primary hover:underline">
          Go to sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {p.invited_by_name ? `${p.invited_by_name} invited you` : "You've been invited"} to join{" "}
        <span className="font-medium text-foreground">{p.organization_name}</span> as{" "}
        <span className="font-medium text-foreground">{p.role}</span>, at{" "}
        <span className="font-mono text-xs">{p.invited_email}</span>.
      </p>

      {p.account_exists ? (
        <div className="space-y-3">
          <p className="text-sm">
            You already have a Cedeon account for this email. Accept below if you're signed in as{" "}
            <span className="font-mono text-xs">{p.invited_email}</span> — otherwise sign in first.
          </p>
          <Button className="w-full" disabled={pending} onClick={() => accept({})}>
            {pending ? "Joining…" : `Join ${p.organization_name}`}
          </Button>
          <Button asChild variant="outline" className="w-full">
            <Link href={`/login?next=/invite/${token}`}>Sign in as this account</Link>
          </Button>
          {error ? (
            <p className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          ) : null}
        </div>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            accept({ name, password });
          }}
        >
          <Field label="Your name" htmlFor="name">
            <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Password" htmlFor="password">
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <p className="text-xs text-muted-foreground">At least 12 characters.</p>
          {error ? (
            <p className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          ) : null}
          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? "Joining…" : `Join ${p.organization_name}`}
          </Button>
        </form>
      )}
    </div>
  );
}
