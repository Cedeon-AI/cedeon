"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/settings/organization", label: "Organization" },
  { href: "/settings/members", label: "Members" },
];

export function SettingsNav() {
  const pathname = usePathname();
  return (
    <nav className="shrink-0 lg:w-44">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Settings
      </p>
      <ul className="flex gap-1 lg:flex-col lg:gap-0.5">
        {TABS.map((t) => {
          const active = pathname === t.href;
          return (
            <li key={t.href}>
              <Link
                href={t.href}
                className={cn(
                  "block rounded-md px-3 py-2 text-sm transition",
                  active
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
