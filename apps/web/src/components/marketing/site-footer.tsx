import Link from "next/link";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const COLUMNS: { title: string; links: { label: string; href: string }[] }[] = [
  {
    title: "Product",
    links: [
      { label: "The queue", href: "/#queue" },
      { label: "What it watches", href: "/#watches" },
      { label: "How it works", href: "/#how-it-works" },
      { label: "Platform", href: "/#platform" },
      { label: "Worked example", href: "/#example" },
      { label: "FAQ", href: "/#faq" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Security", href: "/security" },
    ],
  },
  {
    title: "Access",
    links: [
      { label: "Request access", href: "/login" },
      { label: "Sign in", href: "/login" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-border/60 bg-muted/30">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-6 py-14 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="space-y-3">
          <Logo className="text-foreground" />
          <p className="max-w-xs text-sm text-muted-foreground">
            The intelligence system for ceded reinsurance. From validated contract to collected
            recovery — one queue of what needs a person, every figure traced to a source.
          </p>
        </div>
        {COLUMNS.map((col) => (
          <div key={col.title}>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {col.title}
            </p>
            <ul className="mt-3 space-y-2">
              {col.links.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-border/60">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-6 py-5 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Cedeon. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <p>Privacy notice and terms available on request.</p>
            <ThemeToggle />
          </div>
        </div>
      </div>
    </footer>
  );
}
