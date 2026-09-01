"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { asProblem, register } from "@/lib/api";

export function RegisterForm() {
  const router = useRouter();
  const [form, setForm] = useState({
    organization_name: "",
    name: "",
    email: "",
    password: "",
  });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const result = await register({ body: form });
    setPending(false);

    if (!result.data) {
      const problem = asProblem(result.error);
      setError(
        problem?.detail ?? "Could not create the organization. Check the form and try again.",
      );
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Field label="Organization" htmlFor="organization_name">
        <Input
          id="organization_name"
          required
          placeholder="Atlantic Specialty Insurance Company"
          value={form.organization_name}
          onChange={set("organization_name")}
        />
      </Field>
      <Field label="Your name" htmlFor="name">
        <Input id="name" required value={form.name} onChange={set("name")} />
      </Field>
      <Field label="Work email" htmlFor="email">
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={set("email")}
        />
      </Field>
      <Field label="Password" htmlFor="password" error={undefined}>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          value={form.password}
          onChange={set("password")}
        />
      </Field>
      <p className="text-xs text-muted-foreground">At least 12 characters.</p>
      {error ? (
        <p className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      <Button type="submit" className="w-full" disabled={pending}>
        {pending ? "Creating…" : "Create workspace"}
      </Button>
    </form>
  );
}
