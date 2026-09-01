"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

const LINKS = [
  { label: "The queue", href: "/#queue" },
  { label: "What it watches", href: "/#watches" },
  { label: "How it works", href: "/#how-it-works" },
  { label: "Security", href: "/security" },
  { label: "About", href: "/about" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
        <Link
          href="/"
          className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Logo />
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-md px-3 py-2 text-sm text-muted-foreground transition hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button asChild variant="ghost" size="sm">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/login">Request access</Link>
          </Button>
        </div>

        <Dialog.Root open={open} onOpenChange={setOpen}>
          <Dialog.Trigger asChild>
            <button
              type="button"
              aria-label="Open menu"
              className="inline-flex size-9 items-center justify-center rounded-md border border-border text-foreground md:hidden"
            >
              <Menu className="size-5" />
            </button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-50 bg-background/70 backdrop-blur-sm data-[state=open]:animate-fade-in" />
            <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-72 max-w-[80vw] flex-col gap-1 border-l border-border bg-card p-4 shadow-lg focus:outline-none">
              <div className="flex items-center justify-between px-2 py-1">
                <Logo />
                <Dialog.Close
                  aria-label="Close menu"
                  className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
                >
                  <X className="size-4" />
                </Dialog.Close>
              </div>
              <div className="mt-2 flex flex-col">
                {LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className="rounded-md px-2 py-2.5 text-sm text-foreground hover:bg-muted"
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
              <div className="mt-3 flex flex-col gap-2 border-t border-border/60 pt-3">
                <Button asChild variant="secondary" size="sm" onClick={() => setOpen(false)}>
                  <Link href="/login">Sign in</Link>
                </Button>
                <Button asChild size="sm" onClick={() => setOpen(false)}>
                  <Link href="/login">Request access</Link>
                </Button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </div>
    </header>
  );
}
