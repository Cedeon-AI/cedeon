"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV: { label: string; href: string; soon?: boolean }[] = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Documents", href: "/documents" },
  { label: "Programs", href: "/programs" },
  { label: "Treaty library", href: "/treaties" },
  { label: "Loss imports", href: "/loss-imports" },
  { label: "Loss events", href: "/loss-events" },
  { label: "Recovery candidates", href: "/recovery-candidates" },
];

export function AppNav() {
  const pathname = usePathname();
  return (
    <nav className="hidden w-52 shrink-0 lg:block">
      <ul className="space-y-1">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          if (item.soon) {
            return (
              <li key={item.href}>
                <span className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-muted-foreground/60">
                  {item.label}
                  <span className="text-[10px] uppercase tracking-wide">Soon</span>
                </span>
              </li>
            );
          }
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  "block rounded-md px-3 py-2 text-sm",
                  active
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted/60",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
