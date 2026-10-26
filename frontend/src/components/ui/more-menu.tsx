"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";

export type MoreItem = { label: string; href: string };

export function MoreMenu({ items, label = "More" }: { items: MoreItem[]; label?: string }) {
  const details = React.useRef<HTMLDetailsElement>(null);
  return (
    <details ref={details} className="relative self-start text-sm">
      <summary className="flex min-h-11 cursor-pointer list-none items-center rounded-t-md border-b-2 border-transparent px-3 py-2 font-medium text-muted-foreground hover:bg-accent/40 hover:text-foreground [&::-webkit-details-marker]:hidden">
        {label}<ChevronDown className="ml-1 h-4 w-4" aria-hidden="true" />
      </summary>
      <div className="absolute right-0 z-20 mt-1 grid min-w-52 gap-1 rounded-md border border-border bg-popover p-2 text-popover-foreground shadow-panel">
        {items.map((item) => (
          <Link key={item.href} href={item.href} onClick={() => { if (details.current) details.current.open = false; }} className="rounded px-3 py-2 hover:bg-accent/50">
            {item.label}
          </Link>
        ))}
      </div>
    </details>
  );
}
