import * as React from "react";
import { cn } from "@/lib/utils";

export function Field({
  label,
  children,
  error
}: {
  label: string;
  children: React.ReactNode;
  error?: string;
}) {
  const fieldId = React.useId();
  const errorId = `${fieldId}-error`;
  const input = React.isValidElement(children) ? children as React.ReactElement<React.InputHTMLAttributes<HTMLInputElement>> : null;
  const content = input
    ? React.cloneElement(input, { id: fieldId, "aria-invalid": Boolean(error) || input.props["aria-invalid"] || false, "aria-describedby": [input.props["aria-describedby"], error ? errorId : undefined].filter(Boolean).join(" ") || undefined })
    : children;
  return (
    <div className="grid min-w-0 gap-2 text-sm font-medium text-foreground">
      <label htmlFor={fieldId}>{label}</label>
      {content}
      {error ? <span id={errorId} className="text-xs font-normal text-destructive">{error}</span> : null}
    </div>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        "h-11 w-full rounded-md border border-border bg-input px-3 text-sm outline-none transition-colors placeholder:text-muted-foreground/70 hover:border-primary/35 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/35 disabled:cursor-not-allowed disabled:opacity-60",
        props.className
      )}
    />
  );
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={cn(
        "min-h-24 w-full rounded-md border border-border bg-input px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground/70 hover:border-primary/35 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/35 disabled:cursor-not-allowed disabled:opacity-60",
        props.className
      )}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={cn(
        "h-11 w-full rounded-md border border-border bg-input px-3 text-sm outline-none transition-colors hover:border-primary/35 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/35 disabled:cursor-not-allowed disabled:opacity-60",
        props.className
      )}
    />
  );
}

