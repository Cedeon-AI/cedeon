"use client";

import type { LucideIcon } from "lucide-react";
import {
  FolderTree,
  Home,
  Scale,
  ScrollText,
  ShieldCheck,
  Sigma,
  Wallet,
  Waves,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

type Item = { label: string; href: string; icon: LucideIcon };
type Group = { title: string; items: Item[] };

const GROUPS: Group[] = [
  {
    title: "",
    items: [{ label: "Home", href: "/dashboard", icon: Home }],
  },
  {
    title: "Reinsurance program",
    items: [
      { label: "Treaties", href: "/treaties", icon: ScrollText },
      { label: "Programs", href: "/programs", icon: FolderTree },
    ],
  },
  {
    title: "Losses",
    items: [{ label: "Loss events", href: "/loss-events", icon: Waves }],
  },
  {
    title: "Recoveries",
    items: [
      { label: "Recoveries", href: "/recovery-candidates", icon: Sigma },
      { label: "Recoverables", href: "/recoverables", icon: Wallet },
      { label: "Statements", href: "/statements", icon: Scale },
    ],
  },
  {
    title: "Oversight",
    items: [{ label: "Audit log", href: "/activity", icon: ShieldCheck }],
  },
];

export function AppNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="space-y-6">
      {GROUPS.map((group) => (
        <div key={group.title || "root"}>
          {group.title ? (
            <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
              {group.title}
            </p>
          ) : null}
          <ul className={cn("space-y-0.5", group.title && "mt-2")}>
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
