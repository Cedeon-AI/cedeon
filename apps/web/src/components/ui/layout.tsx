import type { ElementType, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Container({
  className,
  as: As = "div",
  ...props
}: HTMLAttributes<HTMLElement> & { as?: ElementType }) {
  return <As className={cn("mx-auto w-full max-w-6xl px-6", className)} {...props} />;
}

export function Separator({ className }: { className?: string }) {
  return <hr className={cn("h-px w-full border-0 bg-border", className)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} />;
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground shadow-xs",
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A full-bleed marketing section with consistent vertical rhythm. */
export function Section({
  className,
  children,
  tint,
  bordered,
  ...props
}: HTMLAttributes<HTMLElement> & {
  tint?: "muted" | "primary" | "none";
  bordered?: boolean;
}) {
  return (
    <section
      className={cn(
        "py-16 sm:py-24",
        tint === "muted" && "bg-muted/40",
        tint === "primary" && "bg-primary/4",
        bordered && "border-y border-border/60",
        className,
      )}
      {...props}
    >
      {children}
    </section>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "left",
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  align?: "left" | "center";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3",
        align === "center" && "items-center text-center",
        className,
      )}
    >
      {eyebrow ? (
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
          {eyebrow}
        </span>
      ) : null}
      <h2 className="max-w-2xl text-pretty text-2xl font-semibold tracking-tight sm:text-[2rem] sm:leading-[1.15]">
        {title}
      </h2>
      {description ? (
        <p className="max-w-2xl text-pretty text-muted-foreground sm:text-[1.0625rem]">
          {description}
        </p>
      ) : null}
    </div>
  );
}
