import { Settings } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { AppNav } from "@/components/app/app-nav";
import { MobileNav } from "@/components/app/mobile-nav";
import { SignOutButton } from "@/components/app/sign-out-button";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import type { Session } from "@/lib/session";

export function AppShell({ session, children }: { session: Session; children: ReactNode }) {
  const initials =
    (session.user.name ?? session.user.email)
      .split(/[\s@.]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((s) => s[0]?.toUpperCase())
      .join("") || "C";

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-2.5">
            <MobileNav />
            <Link
              href="/dashboard"
              className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Logo />
            </Link>
            <span className="hidden items-center gap-2 text-sm text-muted-foreground sm:flex">
              <span className="text-border-strong">/</span>
              {session.organization.name}
            </span>
          </div>
          <div className="flex items-center gap-2.5">
            <ThemeToggle className="hidden sm:inline-flex" />
            <span className="hidden text-sm text-muted-foreground md:inline">
              {session.user.email}
            </span>
            <span className="hidden rounded-full border border-border bg-muted px-2 py-0.5 text-xs font-medium capitalize text-muted-foreground sm:inline">
              {session.role}
            </span>
            <Link
              href="/settings/members"
              title="Organization settings"
              className="flex size-8 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground"
            >
              <Settings className="size-4" />
            </Link>
            <span
              className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary"
              title={session.user.email}
            >
              {initials}
            </span>
            <SignOutButton />
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl gap-8 px-4 py-8 sm:px-6">
        <aside className="hidden w-56 shrink-0 lg:block">
          <div className="sticky top-20">
            <AppNav />
          </div>
        </aside>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
