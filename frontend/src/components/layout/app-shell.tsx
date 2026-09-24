"use client";

import {
  BarChart3,
  BriefcaseBusiness,
  ClipboardList,
  GraduationCap,
  UserRound
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/reports", label: "Outcomes", icon: BarChart3 },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/profile", label: "Application Assets", icon: UserRound },
  { href: "/interview", label: "Interview", icon: ClipboardList },
  { href: "/skills", label: "Skills", icon: GraduationCap },
  { href: "/data", label: "Export & backups", icon: ClipboardList }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-background text-foreground">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-card focus:p-3">Skip to content</a>
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-primary-foreground/15 bg-sidebar px-4 py-5 shadow-panel lg:block">
        <Link href="/dashboard" className="block border-b border-primary-foreground/15 pb-5">
          <div className="text-lg font-semibold text-primary-foreground">Job Pilot</div>
          <div className="mt-1 text-xs text-primary-foreground/65">AI job search workspace</div>
        </Link>
        <nav className="mt-5 grid gap-1">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition",
                  active
                    ? "bg-accent text-accent-foreground shadow-sm"
                    : "text-primary-foreground/90 hover:bg-primary-foreground/10 hover:text-primary-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <header className="sticky top-0 z-10 border-b border-primary-foreground/15 bg-sidebar px-4 py-3 shadow-panel lg:hidden">
        <div className="font-semibold text-primary-foreground">Job Pilot</div>
        <nav className="mt-3 flex gap-1 overflow-x-auto">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                aria-label={item.label}
                title={item.label}
                className={cn(
                  "flex min-h-12 shrink-0 flex-col items-center justify-center gap-1 rounded-md border px-2 text-[10px]",
                  active
                    ? "border-accent bg-accent text-accent-foreground"
                    : "border-primary-foreground/20 bg-primary-foreground/10 text-primary-foreground/90"
                )}
              >
                <Icon className="h-4 w-4" /><span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </header>
      <main id="main-content" className="px-4 py-6 lg:ml-64 lg:px-8">{children}</main>
    </div>
  );
}

