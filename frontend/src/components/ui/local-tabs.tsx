import * as React from "react";
import { cn } from "@/lib/utils";

export function LocalTabs({
  label,
  children,
  className
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <nav aria-label={label} className={cn("flex min-w-0 flex-wrap gap-x-2 gap-y-1 border-b border-border", className)}>
      {children}
    </nav>
  );
}

export function LocalTab({
  active,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-t-md border-b-2 px-3 py-2 text-sm font-medium transition-colors",
        "focus-visible:relative focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        active
          ? "border-primary bg-accent/65 text-foreground"
          : "border-transparent text-muted-foreground hover:bg-accent/40 hover:text-foreground",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
