"use client";

import { BarChart3, BriefcaseBusiness, ClipboardList, Menu, UserRound, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard?tab=overview", path: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/jobs", path: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/profile?tab=resumes", path: "/profile", label: "Application Assets", icon: UserRound },
  { href: "/interview?tab=practice", path: "/interview", label: "Interview", icon: ClipboardList }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = React.useState(false);
  const menuButton = React.useRef<HTMLButtonElement>(null);
  const drawer = React.useRef<HTMLDialogElement>(null);

  React.useEffect(() => { setMenuOpen(false); }, [pathname]);
  React.useEffect(() => {
    const dialog = drawer.current;
    if (!dialog) return;
    if (menuOpen && !dialog.open) {
      dialog.showModal();
      dialog.querySelector<HTMLAnchorElement>("nav a")?.focus();
    } else if (!menuOpen && dialog.open) {
      dialog.close();
    }
  }, [menuOpen]);

  const destination = (item: (typeof nav)[number], mobile = false) => {
    const Icon = item.icon;
    const active = pathname === item.path || pathname.startsWith(`${item.path}/`);
    return (
      <Link
        key={item.path}
        href={item.href}
        aria-current={active ? "page" : undefined}
        onClick={mobile ? () => setMenuOpen(false) : undefined}
        className={cn(
          "flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          active ? "bg-accent text-accent-foreground" : "text-primary-foreground/90 hover:bg-primary-foreground/15 hover:text-primary-foreground"
        )}
      >
        <Icon className="h-4 w-4" />{item.label}
      </Link>
    );
  };

  const utility = (mobile = false) => <Link href="/data" onClick={mobile ? () => setMenuOpen(false) : undefined} aria-current={pathname === "/data" ? "page" : undefined} className={cn("flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium", pathname === "/data" ? "bg-accent text-accent-foreground" : "text-primary-foreground/90 hover:bg-primary-foreground/15 hover:text-primary-foreground")}><ClipboardList className="h-4 w-4" />Export & backups</Link>;
  return (
    <div className="min-h-screen bg-background text-foreground">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-4 focus:py-3 focus:text-foreground">Skip to content</a>
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-primary-foreground/15 bg-sidebar px-5 py-7 shadow-panel lg:flex">
        <Link href="/dashboard" className="block rounded-sm border-b border-primary-foreground/15 pb-6">
          <div className="text-xl font-semibold tracking-tight text-primary-foreground">Job Pilot</div>
          <div className="mt-1 text-xs text-primary-foreground/70">AI job search workspace</div>
        </Link>
        <nav className="mt-7 grid gap-1.5" aria-label="Primary navigation">
          {nav.map((item) => destination(item))}
        </nav>
        <div className="mt-auto border-t border-primary-foreground/20 pt-4">{utility()}</div>
      </aside>
      <header className="sticky top-0 z-10 border-b border-primary-foreground/15 bg-sidebar px-4 py-3 shadow-panel lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <Link href="/dashboard?tab=overview" className="text-lg font-semibold tracking-tight text-primary-foreground">Job Pilot</Link>
          <button ref={menuButton} type="button" onClick={() => setMenuOpen(true)} aria-haspopup="dialog" aria-expanded={menuOpen} className="inline-flex min-h-11 items-center gap-2 rounded-md px-3 text-sm font-medium text-primary-foreground hover:bg-primary-foreground/15"><Menu className="h-5 w-5" />Menu</button>
        </div>
      </header>
      <dialog ref={drawer} aria-label="Navigation menu" onCancel={event => { event.preventDefault(); setMenuOpen(false); }} onClose={() => { setMenuOpen(false); menuButton.current?.focus(); }} onClick={event => { if (event.target === drawer.current) setMenuOpen(false); }} className="fixed left-0 top-0 z-50 m-0 h-dvh max-h-dvh w-72 max-w-[calc(100vw-2rem)] flex-col border-0 bg-sidebar p-5 text-primary-foreground shadow-2xl backdrop:bg-black/45 open:flex lg:hidden">
        <div className="flex items-center justify-between border-b border-primary-foreground/20 pb-5"><span className="text-lg font-semibold">Job Pilot</span><button type="button" onClick={() => setMenuOpen(false)} aria-label="Close menu" className="rounded-md p-2 hover:bg-primary-foreground/15"><X className="h-5 w-5" /></button></div>
        <nav aria-label="Mobile navigation" className="mt-5 grid gap-2">{nav.map(item => destination(item, true))}</nav>
        <div className="mt-auto border-t border-primary-foreground/20 pt-4">{utility(true)}</div>
      </dialog>
      <main id="main-content" className="min-w-0 px-4 py-7 sm:px-6 sm:py-8 lg:ml-64 lg:px-10 lg:py-10 xl:px-12">
        <div className="mx-auto w-full max-w-workspace">{children}</div>
      </main>
    </div>
  );
}

