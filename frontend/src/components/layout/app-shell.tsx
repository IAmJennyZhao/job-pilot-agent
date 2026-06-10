"use client";

import {
  BarChart3,
  BriefcaseBusiness,
  ClipboardList,
  GraduationCap,
  MessageSquare,
  UserRound
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/profile", label: "Profile", icon: UserRound },
  { href: "/interview", label: "Interview", icon: ClipboardList },
  { href: "/skills", label: "Skills", icon: GraduationCap },
  { href: "/chat", label: "Chat", icon: MessageSquare }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-card-strong/90 px-4 py-5 shadow-panel lg:block">
        <Link href="/dashboard" className="block border-b border-border pb-5">
          <div className="text-lg font-semibold text-primary">CareerPilot</div>
          <div className="mt-1 text-xs text-muted-foreground">AI job search workspace</div>
        </Link>
        <nav className="mt-5 grid gap-1">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition",
                  active ? "bg-accent text-accent-foreground shadow-sm" : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <header className="sticky top-0 z-10 border-b border-border bg-card-strong/95 px-4 py-3 shadow-panel backdrop-blur lg:hidden">
        <div className="font-semibold text-primary">CareerPilot</div>
        <nav className="mt-3 flex gap-1 overflow-x-auto">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-label={item.label}
                title={item.label}
                className={cn(
                  "grid h-9 min-w-9 place-items-center rounded-md border text-sm",
                  active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card-strong text-muted-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="px-4 py-6 lg:ml-64 lg:px-8">{children}</main>
    </div>
  );
}

