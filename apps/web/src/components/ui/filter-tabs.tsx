import { cn } from "@/lib/utils";

export function FilterTabs<T extends string>({
  options,
  value,
  onChange,
  size = "sm",
}: {
  options: readonly { label: string; value: T }[];
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "md";
}) {
  return (
    <div className="inline-flex flex-wrap items-center gap-0.5 rounded-lg border border-border bg-muted/50 p-0.5">
      {options.map((option) => (
        <button
          key={option.value || "all"}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
          className={cn(
            "rounded-md font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
            value === option.value
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
