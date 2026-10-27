"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BriefcaseBusiness,
  RefreshCw,
  TimerReset
} from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import OutcomesView from "@/components/dashboard/outcomes-view";
import SkillsView from "@/components/dashboard/skills-view";
import { FunnelChart } from "@/components/dashboard/funnel-chart";
import { AnalyticsFilter } from "@/components/dashboard/analytics-filter";
import { analyticsSince } from "@/lib/analytics-cohort";
import { RetainedView } from "@/components/layout/retained-view";
import { LocalTab, LocalTabs } from "@/components/ui/local-tabs";
import { pushLocalView, selectLocalView } from "@/lib/workspace-navigation";
import { ActionAgenda } from "@/components/job-action";
import { Button } from "@/components/ui/button";
import { PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { DashboardJobInsight } from "@/lib/types";
import { cn } from "@/lib/utils";

function uniqueInsightItems(items: DashboardJobInsight[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

const dashboardTabs = ["overview", "outcomes", "skills"] as const;

export default function DashboardPage() { return <Suspense fallback={<Panel>Loading dashboard...</Panel>}><DashboardWorkspace /></Suspense>; }

function DashboardWorkspace() {
  const params = useSearchParams();
  const active = selectLocalView(params, dashboardTabs, "overview");
  useEffect(() => {
    const scrollToShortcut = () => {
      const anchor = window.location.hash.slice(1);
      if (anchor) requestAnimationFrame(() => document.getElementById(anchor)?.scrollIntoView({ block: "start" }));
    };
    scrollToShortcut();
    window.addEventListener("hashchange", scrollToShortcut);
    return () => window.removeEventListener("hashchange", scrollToShortcut);
  }, [active]);
  return <div className="grid gap-6">
    <LocalTabs label="Dashboard views">
      {dashboardTabs.map((tab) => <LocalTab key={tab} active={active === tab} onClick={() => pushLocalView("/dashboard", params, tab)}>{tab === "overview" ? "Overview" : tab === "outcomes" ? "Outcomes" : "Skills & learning"}</LocalTab>)}
    </LocalTabs>
    {active === "outcomes" ? <AnalyticsFilter view="outcomes" /> : null}
    <RetainedView active={active === "overview"}><DashboardContent active={active === "overview"} /></RetainedView>
    <RetainedView active={active === "outcomes"}><OutcomesView /></RetainedView>
    <RetainedView active={active === "skills"}><SkillsView /></RetainedView>
  </div>;
}

function DashboardContent({ active }: { active: boolean }) {
  const params = useSearchParams();
  const since = analyticsSince(params);
  const cohortHref = (href: string) => since ? `${href}${href.includes("?") ? "&" : "?"}since=${encodeURIComponent(since)}` : href;
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["dashboard", since],
    queryFn: () => api.dashboard(since),
    refetchInterval: 60000
  });

  const missingPayItems = data?.coverage_risk?.missing_pay ?? [];
  const missingFitItems = data?.coverage_risk?.missing_fit ?? [];
  const lowConfidenceItems = data?.coverage_risk?.low_confidence ?? [];
  const staleItems = data?.search_health?.stale_jobs ?? [];
  const missingDataItems = data?.search_health?.missing_data ?? uniqueInsightItems([...missingPayItems, ...missingFitItems, ...lowConfidenceItems]);
  const activeJobs = data?.health?.active_jobs ?? data?.total_jobs ?? 0;
  const staleJobs = data?.health?.stale_jobs ?? staleItems.length;
  const missingDataCount = data?.health?.missing_data ?? missingDataItems.length;
  const archivedJobs = data?.archived_jobs ?? data?.health?.archived_jobs ?? 0;
  const ghostedJobs = data?.health?.ghosted_jobs ?? data?.ghosted_jobs ?? 0;

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Dashboard"
        action={
          <Button variant="secondary" onClick={() => { refetch(); queryClient.invalidateQueries({ queryKey: ["actions"] }); }} disabled={isFetching}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        }
      />

      {error ? <Panel className="border-destructive/25 bg-destructive/10 text-sm text-destructive">{(error as Error).message}</Panel> : null}
      {isLoading ? <Panel>Loading dashboard...</Panel> : null}

      {data ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Metric href={cohortHref("/jobs?health=active")} title="Active" value={activeJobs} detail={`${archivedJobs} archived, ${ghostedJobs} ghosted`} icon={<BriefcaseBusiness className="h-4 w-4" />} />
            <Metric href={cohortHref("/jobs?health=stale")} title="Stale" value={staleJobs} detail="Needs review" icon={<TimerReset className="h-4 w-4" />} tone="warn" />
            <Metric href={cohortHref("/jobs?health=missing-data")} title="Missing Data" value={missingDataCount} detail="Core coverage gaps" icon={<AlertTriangle className="h-4 w-4" />} tone="warn" />
          </div>

          <div className="grid min-w-0 gap-4">
            <Panel className="overflow-hidden">
              <FunnelChart sankey={data.sankey} since={since} />
            </Panel>
          </div>
        </>
      ) : null}
      {active ? <AnalyticsFilter view="overview" /> : null}
      <ActionAgenda suggestions={data?.action_suggestions ?? []} suggestionsLoading={isLoading} suggestionsError={error}
        onRetrySuggestions={() => refetch()} since={since} />
    </div>
  );
}

function Metric({
  href,
  title,
  value,
  detail,
  icon,
  tone = "neutral"
}: {
  href: string;
  title: string;
  value: number;
  detail: string;
  icon: React.ReactNode;
  tone?: "neutral" | "warn";
}) {
  const content = (
    <Panel className="h-full transition hover:border-primary/50 hover:shadow-md">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-muted-foreground">{title}</div>
        <div className={cn("grid h-8 w-8 place-items-center rounded-md", tone === "warn" ? "bg-warning text-warning-foreground" : "bg-accent text-accent-foreground")}>
          {icon}
        </div>
      </div>
      <div className="mt-4 text-3xl font-semibold">{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
    </Panel>
  );
  return (
    <Link href={href} className="block focus:outline-none focus:ring-2 focus:ring-primary/40">
      {content}
    </Link>
  );
}
