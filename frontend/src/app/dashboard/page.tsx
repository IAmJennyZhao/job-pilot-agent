"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  DollarSign,
  FileSearch,
  RefreshCw,
  Sparkles,
  TimerReset
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { DashboardJobInsight, DashboardSankey, DashboardSkillGap, JobStatus } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";

const stageOrder = ["Saved", "Applied", "Recruiter Screen", "Tech Screen", "Final Interview", "Offer"];
const terminalOrder = ["Rejected", "Withdrawn", "Ghosted"];
const stageColors: Record<string, string> = {
  Saved: "hsl(var(--chart-saved))",
  Applied: "hsl(var(--chart-applied))",
  "Recruiter Screen": "hsl(var(--chart-recruiter))",
  "Tech Screen": "hsl(var(--chart-tech))",
  "Final Interview": "hsl(var(--chart-final))",
  Offer: "hsl(var(--chart-offer))",
  Rejected: "hsl(var(--chart-rejected))",
  Withdrawn: "hsl(var(--chart-withdrawn))",
  Ghosted: "hsl(var(--chart-ghosted))"
};
const fallbackStageColor = "hsl(var(--chart-saved))";

function jobsStatusHref(status: string, source?: string) {
  return `/jobs?funnel=${encodeURIComponent(status)}${source ? `&from=${encodeURIComponent(source)}` : ""}`;
}

function uniqueInsightItems(items: DashboardJobInsight[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard
  });

  const markGhostedMutation = useMutation({
    mutationFn: (jobId: string) =>
      api.updateJob(jobId, {
        status: "Ghosted",
        status_note: "Marked ghosted from dashboard."
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
  });

  const runAnalysisMutation = useMutation({
    mutationFn: (jobId: string) => api.runJobIntelligence(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
    }
  });

  const missingPayItems = data?.coverage_risk?.missing_pay ?? [];
  const missingFitItems = data?.coverage_risk?.missing_fit ?? [];
  const lowConfidenceItems = data?.coverage_risk?.low_confidence ?? [];
  const staleItems = data?.search_health?.stale_jobs ?? [];
  const missingDataItems = data?.search_health?.missing_data ?? uniqueInsightItems([...missingPayItems, ...missingFitItems, ...lowConfidenceItems]);
  const needsAnalysisItems = (data?.search_health?.needs_analysis ?? []).slice(0, 3);
  const recurringRisks = data?.coverage_risk?.recurring_risks ?? [];
  const activeJobs = data?.health?.active_jobs ?? data?.total_jobs ?? 0;
  const staleJobs = data?.health?.stale_jobs ?? staleItems.length;
  const missingDataCount = data?.health?.missing_data ?? missingDataItems.length;
  const archivedJobs = data?.archived_jobs ?? data?.health?.archived_jobs ?? 0;
  const ghostedJobs = data?.health?.ghosted_jobs ?? data?.ghosted_jobs ?? 0;

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Dashboard"
        description="Pipeline analytics, search health, opportunity coverage, and active skill gaps from tracked jobs."
        action={
          <Button variant="secondary" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        }
      />

      {error ? <Panel className="border-destructive/25 bg-destructive/10 text-sm text-destructive">{(error as Error).message}</Panel> : null}
      {isLoading ? <Panel>Loading dashboard...</Panel> : null}
      {markGhostedMutation.error ? <Panel className="border-destructive/25 bg-destructive/10 text-sm text-destructive">{(markGhostedMutation.error as Error).message}</Panel> : null}
      {runAnalysisMutation.error ? <Panel className="border-destructive/25 bg-destructive/10 text-sm text-destructive">{(runAnalysisMutation.error as Error).message}</Panel> : null}

      {data ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Metric href="/jobs?health=active" title="Active" value={activeJobs} detail={`${archivedJobs} archived, ${ghostedJobs} ghosted`} icon={<BriefcaseBusiness className="h-4 w-4" />} />
            <Metric href="/jobs?health=stale" title="Stale" value={staleJobs} detail="Needs review" icon={<TimerReset className="h-4 w-4" />} tone="warn" />
            <Metric href="/jobs?health=missing-data" title="Missing Data" value={missingDataCount} detail="Core coverage gaps" icon={<AlertTriangle className="h-4 w-4" />} tone="warn" />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
            <Panel className="overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Application Funnel</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Counts include every job that reached each stage, including later outcomes. Earlier stages are inferred; archived jobs are excluded.
                  </p>
                </div>
                <Link href="/jobs" className="text-sm font-medium text-primary">
                  Open jobs
                </Link>
              </div>
              <SankeyChart sankey={data.sankey} />
            </Panel>

            <Panel>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Search Health</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{data.next_recommended_action}</p>
                </div>
                <Badge tone={staleJobs || missingDataCount || needsAnalysisItems.length ? "warn" : "good"}>{staleJobs || missingDataCount || needsAnalysisItems.length ? "Needs attention" : "Up to date"}</Badge>
              </div>
              <div className="mt-5 grid gap-5">
                <InsightList
                  title="Stale Jobs"
                  href="/jobs?health=stale"
                  items={staleItems}
                  empty="No stage-based stale jobs."
                  action={(item) => (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => markGhostedMutation.mutate(item.id)}
                      disabled={markGhostedMutation.isPending && markGhostedMutation.variables === item.id}
                    >
                      {markGhostedMutation.isPending && markGhostedMutation.variables === item.id ? "Saving..." : "Mark Ghosted"}
                    </Button>
                  )}
                />
                <InsightList
                  title="Needs Analysis"
                  href="/jobs?health=needs-analysis"
                  items={needsAnalysisItems}
                  empty="Every active opportunity has fit/job analysis."
                  action={(item) => (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => runAnalysisMutation.mutate(item.id)}
                      disabled={runAnalysisMutation.isPending && runAnalysisMutation.variables === item.id}
                    >
                      <Sparkles className="h-4 w-4" />
                      {runAnalysisMutation.isPending && runAnalysisMutation.variables === item.id ? "Running..." : "Run"}
                    </Button>
                  )}
                />
              </div>
            </Panel>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
            <Panel>
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Opportunity Coverage And Risk</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Data quality and recurring risk signals across open opportunities.</p>
                </div>
                <Badge>{missingDataCount} jobs</Badge>
              </div>
              <div className="grid gap-5">
                <CoverageBlock
                  title="Missing Pay"
                  href="/jobs?health=missing-pay"
                  icon={<DollarSign className="h-4 w-4" />}
                  items={missingPayItems}
                  empty="Pay coverage is complete."
                />
                <CoverageBlock
                  title="Missing Fit"
                  href="/jobs?health=missing-fit"
                  icon={<FileSearch className="h-4 w-4" />}
                  items={missingFitItems}
                  empty="Fit scores are complete."
                />
                <CoverageBlock
                  title="Low Confidence"
                  href="/jobs?health=low-confidence"
                  icon={<AlertTriangle className="h-4 w-4" />}
                  items={lowConfidenceItems}
                  empty="Extraction confidence looks healthy."
                />
                <div>
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                    <BarChart3 className="h-4 w-4 text-primary" />
                    Recurring Risks
                  </div>
                  {recurringRisks.length ? (
                    <div className="flex flex-wrap gap-2">
                      {recurringRisks.map((risk) => (
                        <Badge key={risk.label} tone={risk.count >= 2 ? "warn" : "neutral"}>
                          {risk.label} ({risk.count})
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No recurring advanced-analysis risks yet.</p>
                  )}
                </div>
              </div>
            </Panel>

            <Panel>
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Top Skill Gaps</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Ranked by active opportunities affected, using resume gaps first.</p>
                </div>
                <Link href="/skills" className="text-sm font-medium text-primary">
                  Open skills
                </Link>
              </div>
              <SkillGapList gaps={data.top_skill_gaps ?? []} />
            </Panel>
          </div>
        </>
      ) : null}
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

function SankeyChart({ sankey }: { sankey?: DashboardSankey }) {
  const nodes = sankey?.nodes ?? [];
  const links = sankey?.links ?? [];
  const total = nodes.find(node => node.id === "Saved")?.count ?? 0;
  if (!total) return <div className="mt-6 rounded-md border border-dashed border-border p-6 text-sm">Your funnel starts with a saved job. <Link href="/jobs" className="font-medium underline">Open the tracker to add one</Link></div>;
  return <div className="mt-5 grid gap-5">
    <p className="text-sm text-muted-foreground">{total} tracked jobs · Select a stage or outcome to see exactly those jobs.</p>
    <ol aria-label="Stages reached" className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {stageOrder.map((stage, index) => {
        const node = nodes.find(node => node.id === stage);
        const count = node?.count ?? 0;
        const percent = Math.round(count / total * 100);
        return <li key={stage}><Link href={jobsStatusHref(stage)} aria-label={`${stage}: ${count} jobs reached this stage, ${percent}% of tracked jobs`} className="block rounded-md border border-border p-3 transition hover:border-primary hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring">
          <div className="text-xs text-muted-foreground">{index + 1}. {stage}</div>
          <div className="my-2 flex items-baseline justify-between"><strong className="text-xl">{count}</strong><span className="text-xs">{percent}%</span></div>
          <div aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${percent}%`, background: stageColors[stage] }} /></div>
        </Link></li>;
      })}
    </ol>
    <div><h3 className="mb-2 text-sm font-semibold">Closed outcomes by furthest stage</h3>
      <div className="grid gap-3 sm:grid-cols-3">{terminalOrder.map(status => {
        const count = nodes.find(node => node.id === status)?.count ?? 0;
        return <div key={status} className="min-w-0 rounded-md border border-border p-3">
          <Link href={jobsStatusHref(status)} className="font-semibold underline-offset-2 hover:underline">{status} ({count})</Link>
          <ul className="mt-2 grid gap-1 text-sm">{links.filter(link => link.target === status).map(link => <li key={link.source}><Link href={jobsStatusHref(status, link.source)} className="block rounded px-1 py-2 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring" aria-label={`${link.value} jobs ${status.toLowerCase()} after ${link.source}`}><span className="block">After {link.source}</span><span className="text-muted-foreground">{link.value} jobs · {Math.round(link.value / total * 100)}% of total</span></Link></li>)}</ul>
          {!count ? <p className="mt-2 text-xs text-muted-foreground">No outcomes yet</p> : null}
        </div>;
      })}</div>
    </div>
    <details className="text-sm"><summary className="cursor-pointer font-medium">Stage transitions and counts</summary><table className="mt-3 w-full text-left"><caption className="sr-only">All inferred transitions; each link opens the exact jobs counted.</caption><thead><tr><th scope="col">Transition</th><th scope="col">Jobs</th></tr></thead><tbody>{links.map(link => <tr key={`${link.source}-${link.target}`} className="border-t border-border"><td className="py-2"><Link className="underline" href={jobsStatusHref(link.target, link.source)}>{link.source} → {link.target}</Link></td><td>{link.value}</td></tr>)}</tbody></table></details>
  </div>;
}

function InsightList({
  title,
  href,
  items,
  empty,
  action
}: {
  title: string;
  href: string;
  items?: DashboardJobInsight[];
  empty: string;
  action?: (item: DashboardJobInsight) => React.ReactNode;
}) {
  const safeItems = items ?? [];
  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-2 text-sm font-semibold">{title}<Link href={href} className="text-primary underline">View all</Link></div>
      {safeItems.length ? (
        <div className="grid gap-3">
          {safeItems.map((item) => (
            <DashboardJobTile key={`${title}-${item.id}`} item={item} action={action} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

function CoverageBlock({
  title,
  href,
  icon,
  items,
  empty
}: {
  title: string;
  href: string;
  icon: React.ReactNode;
  items?: DashboardJobInsight[];
  empty: string;
}) {
  const safeItems = items ?? [];
  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <span className="text-primary">{icon}</span>
        {title}<Link href={href} className="ml-auto text-primary underline">View all</Link>
      </div>
      {safeItems.length ? (
        <div className="grid gap-3">
          {safeItems.slice(0, 4).map((item) => (
            <DashboardJobTile key={`${title}-${item.id}`} item={item} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

function DashboardJobTile({
  item,
  action
}: {
  item: DashboardJobInsight;
  action?: (item: DashboardJobInsight) => React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "grid gap-3 rounded-md border border-border bg-card-strong/75 p-3 transition hover:border-primary/40 hover:bg-accent/45",
        action ? "sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center" : ""
      )}
    >
      <Link href={`/jobs/${item.id}`} className="block min-w-0 rounded-sm focus:outline-none focus:ring-2 focus:ring-primary/40">
        <InsightHeader item={item} />
      </Link>
      {action ? <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">{action(item)}</div> : null}
    </div>
  );
}

function InsightHeader({ item }: { item: DashboardJobInsight }) {
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{item.company}</span>
        <Badge tone={statusTone(item.status)}>{item.status}</Badge>
      </div>
      <div className="mt-1 text-sm text-muted-foreground">{item.role_title}</div>
      <div className="mt-1 text-xs text-muted-foreground">
        {item.issue_label} - {formatDate(item.last_movement_at)}
      </div>
    </div>
  );
}

function SkillGapList({ gaps }: { gaps?: DashboardSkillGap[] }) {
  const safeGaps = gaps ?? [];
  if (!safeGaps.length) {
    return <p className="text-sm text-muted-foreground">Run analysis or resume matching to populate active skill gaps.</p>;
  }
  return (
    <div className="grid gap-4">
      {safeGaps.map((gap) => (
        <div key={gap.skill_name} className="border-b border-border pb-4 last:border-0 last:pb-0">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-semibold">{gap.skill_name}</div>
              <div className="mt-1 text-sm text-muted-foreground">{gap.suggested_action}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone={gap.source === "resume_match" ? "warn" : "neutral"}>{gap.source.replace("_", " ")}</Badge>
              <Badge>{gap.count} jobs</Badge>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {gap.affected_jobs.map((job) => (
              <Link key={`${gap.skill_name}-${job.id}`} href={`/jobs/${job.id}`} className="rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground">
                {job.company}
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function statusTone(status: JobStatus): "neutral" | "good" | "warn" | "bad" {
  if (status === "Offer") return "good";
  if (status === "Rejected" || status === "Ghosted") return "bad";
  if (status === "Withdrawn" || status === "Archived") return "warn";
  return "neutral";
}
