import Link from "next/link";
import type { ReactNode } from "react";
import { SignOutButton } from "@/components/app/sign-out-button";
import { Logo } from "@/components/logo";
import type { Session } from "@/lib/session";
import { cn } from "@/lib/utils";

const NAV: { label: string; href: string; soon?: boolean }[] = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Programs", href: "/programs", soon: true },
  { label: "Treaty library", href: "/treaties", soon: true },
  { label: "Loss imports", href: "/loss-imports", soon: true },
  { label: "Recovery candidates", href: "/recovery-candidates", soon: true },
];

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
        <nav className="hidden w-52 shrink-0 lg:block">
          <ul className="space-y-1">
            {NAV.map((item) => (
              <li key={item.href}>
                <span
                  className={cn(
                    "flex items-center justify-between rounded-md px-3 py-2 text-sm",
                    item.soon
                      ? "cursor-not-allowed text-muted-foreground/60"
                      : "bg-muted font-medium text-foreground",
                  )}
                >
                  {item.label}
                  {item.soon ? (
                    <span className="text-[10px] uppercase tracking-wide">Soon</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </nav>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
