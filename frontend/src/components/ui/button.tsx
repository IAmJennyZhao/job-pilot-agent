import * as React from "react";
import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "icon";
};

const variants = {
  primary: "bg-primary text-primary-foreground hover:bg-primary/90",
  secondary: "border border-border bg-white text-foreground hover:bg-muted",
  ghost: "text-foreground hover:bg-muted",
  danger: "bg-destructive text-destructive-foreground hover:bg-destructive/90"
};

const sizes = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  icon: "h-9 w-9 p-0"
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition disabled:pointer-events-none disabled:opacity-55",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}

