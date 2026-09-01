"use client";

import type { LucideIcon } from "lucide-react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

type Theme = "system" | "light" | "dark";

const KEY = "cedeon-theme";
const SYNC_EVENT = "cedeon-theme-change";

const OPTIONS: { value: Theme; label: string; Icon: LucideIcon }[] = [
  { value: "system", label: "System theme", Icon: Monitor },
  { value: "light", label: "Light theme", Icon: Sun },
  { value: "dark", label: "Dark theme", Icon: Moon },
];

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.dataset.theme = theme;
}

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>("system");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const stored = localStorage.getItem(KEY);
      if (stored === "light" || stored === "dark" || stored === "system") setTheme(stored);
    } catch {
      // localStorage unavailable — stay on "system"
    }

    // Keep every toggle on the page (header, mobile menu, footer) in sync.
    const onSync = (event: Event) => {
      const next = (event as CustomEvent<Theme>).detail;
      if (next === "light" || next === "dark" || next === "system") setTheme(next);
    };
    window.addEventListener(SYNC_EVENT, onSync);
    return () => window.removeEventListener(SYNC_EVENT, onSync);
  }, []);

  function choose(next: Theme) {
    setTheme(next);
    applyTheme(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // ignore — the choice still applies for this session
    }
    window.dispatchEvent(new CustomEvent<Theme>(SYNC_EVENT, { detail: next }));
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg border border-border bg-muted/50 p-0.5",
        className,
      )}
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = mounted && theme === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            aria-label={label}
            title={label}
            onClick={() => choose(value)}
            className={cn(
              "inline-flex size-7 items-center justify-center rounded-md transition",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-3.5" />
          </button>
        );
      })}
    </div>
  );
}
