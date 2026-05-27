import * as React from "react";
import { cn } from "@/lib/utils";

export function Panel({
  className,
  children
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn("rounded-lg border border-border bg-white p-5 shadow-panel", className)}>
      {children}
    </section>
  );
}

export function PageHeader({
  title,
  description,
  action
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "good" | "warn" | "bad" }) {
  const tones = {
    neutral: "border-border bg-muted text-muted-foreground",
    good: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warn: "border-amber-200 bg-amber-50 text-amber-700",
    bad: "border-rose-200 bg-rose-50 text-rose-700"
  };
  return (
    <span className={cn("inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}

