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
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-4 focus:py-3 focus:text-foreground">Skip to content</a>
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-primary-foreground/15 bg-sidebar px-5 py-7 shadow-panel lg:block">
        <Link href="/dashboard" className="block rounded-sm border-b border-primary-foreground/15 pb-6">
          <div className="text-xl font-semibold tracking-tight text-primary-foreground">Job Pilot</div>
          <div className="mt-1 text-xs text-primary-foreground/70">AI job search workspace</div>
        </Link>
        <nav className="mt-7 grid gap-1.5" aria-label="Primary navigation">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-offset-2",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-primary-foreground/90 hover:bg-primary-foreground/15 hover:text-primary-foreground"
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
        <div className="text-lg font-semibold tracking-tight text-primary-foreground">Job Pilot</div>
        <nav aria-label="Primary navigation" className="mt-3 flex gap-2 overflow-x-auto pb-1">
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
                  "flex min-h-12 shrink-0 flex-col items-center justify-center gap-1 rounded-md border px-3 text-[11px] font-medium transition-colors",
                  active
                    ? "border-accent bg-accent text-accent-foreground"
                    : "border-primary-foreground/20 bg-primary-foreground/10 text-primary-foreground/90 hover:border-primary-foreground/40 hover:bg-primary-foreground/20"
                )}
              >
                <Icon className="h-4 w-4" /><span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </header>
      <main id="main-content" className="min-w-0 px-4 py-7 sm:px-6 sm:py-8 lg:ml-64 lg:px-10 lg:py-10 xl:px-12">
        <div className="mx-auto w-full max-w-workspace">{children}</div>
      </main>
    </div>
  );
}

