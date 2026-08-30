import Link from "next/link";
import type { ReactNode } from "react";
import { AppNav } from "@/components/app/app-nav";
import { SignOutButton } from "@/components/app/sign-out-button";
import { Logo } from "@/components/logo";
import type { Session } from "@/lib/session";

export function AppShell({ session, children }: { session: Session; children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Link href="/dashboard">
              <Logo />
            </Link>
            <span className="hidden text-sm text-muted-foreground sm:inline">
              / {session.organization.name}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-muted-foreground md:inline">
              {session.user.email}
            </span>
            <span className="rounded-full border border-border px-2 py-0.5 text-xs font-medium capitalize text-muted-foreground">
              {session.role}
            </span>
            <SignOutButton />
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl gap-8 px-6 py-8">
        <AppNav />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
