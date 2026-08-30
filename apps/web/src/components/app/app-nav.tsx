"use client";

import type { LucideIcon } from "lucide-react";
import {
  Activity,
  FileText,
  FolderTree,
  LayoutDashboard,
  ScrollText,
  Sigma,
  Upload,
  Waves,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

type Item = { label: string; href: string; icon: LucideIcon };
type Group = { title: string; items: Item[] };

const GROUPS: Group[] = [
  {
    title: "Overview",
    items: [{ label: "Dashboard", href: "/dashboard", icon: LayoutDashboard }],
  },
  {
    title: "Contracts",
    items: [
      { label: "Documents", href: "/documents", icon: FileText },
      { label: "Programs", href: "/programs", icon: FolderTree },
      { label: "Treaty library", href: "/treaties", icon: ScrollText },
    ],
  },
  {
    title: "Losses",
    items: [
      { label: "Loss imports", href: "/loss-imports", icon: Upload },
      { label: "Loss events", href: "/loss-events", icon: Waves },
    ],
  },
  {
    title: "Recovery",
    items: [{ label: "Recovery candidates", href: "/recovery-candidates", icon: Sigma }],
  },
  {
    title: "Oversight",
    items: [{ label: "Activity", href: "/activity", icon: Activity }],
  },
];

export function AppNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="space-y-6">
      {GROUPS.map((group) => (
        <div key={group.title}>
          <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
            {group.title}
          </p>
          <ul className="mt-2 space-y-0.5">
            {group.items.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition",
                      active
                        ? "bg-primary/10 font-medium text-primary"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon
                      className={cn(
                        "size-4 shrink-0",
                        active
                          ? "text-primary"
                          : "text-muted-foreground/70 group-hover:text-foreground",
                      )}
                    />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
