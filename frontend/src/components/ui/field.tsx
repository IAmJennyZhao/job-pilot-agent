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
  const content = React.isValidElement(children)
    ? React.cloneElement(children as React.ReactElement<React.InputHTMLAttributes<HTMLInputElement>>, { id: fieldId, "aria-invalid": Boolean(error), "aria-describedby": error ? errorId : undefined })
    : children;
  return (
    <div className="grid gap-1.5 text-sm font-medium text-foreground">
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
        "h-10 w-full rounded-md border border-border bg-input px-3 text-sm outline-none transition placeholder:text-muted-foreground/70 focus:border-ring focus:ring-2 focus:ring-ring/25",
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
        "min-h-24 w-full rounded-md border border-border bg-input px-3 py-2 text-sm outline-none transition placeholder:text-muted-foreground/70 focus:border-ring focus:ring-2 focus:ring-ring/25",
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
        "h-10 w-full rounded-md border border-border bg-input px-3 text-sm outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/25",
        props.className
      )}
    />
  );
}

