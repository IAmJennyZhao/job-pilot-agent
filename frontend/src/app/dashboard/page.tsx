"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  DollarSign,
  ExternalLink,
  FileSearch,
  RefreshCw,
  Sparkles,
  TimerReset
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { DashboardJobInsight, DashboardSankey, DashboardSankeyNode, DashboardSkillGap, JobStatus } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";

const stageOrder = ["Saved", "Applied", "Recruiter Screen", "Tech Screen", "Final Interview", "Offer"];
const terminalOrder = ["Rejected", "Withdrawn", "Ghosted"];
const stageColors: Record<string, string> = {
  Saved: "#0f766e",
  Applied: "#2563eb",
  "Recruiter Screen": "#7c3aed",
  "Tech Screen": "#9333ea",
  "Final Interview": "#db2777",
  Offer: "#059669",
  Rejected: "#e11d48",
  Withdrawn: "#d97706",
  Ghosted: "#64748b"
};

function jobsStatusHref(status: string) {
  return `/jobs?status=${encodeURIComponent(status)}`;
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

      {error ? <Panel className="border-rose-200 bg-rose-50 text-sm text-rose-700">{(error as Error).message}</Panel> : null}
      {isLoading ? <Panel>Loading dashboard...</Panel> : null}
      {markGhostedMutation.error ? <Panel className="border-rose-200 bg-rose-50 text-sm text-rose-700">{(markGhostedMutation.error as Error).message}</Panel> : null}
      {runAnalysisMutation.error ? <Panel className="border-rose-200 bg-rose-50 text-sm text-rose-700">{(runAnalysisMutation.error as Error).message}</Panel> : null}

      {data ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Metric href="/jobs" title="Active" value={activeJobs} detail={`${archivedJobs} archived, ${ghostedJobs} ghosted`} icon={<BriefcaseBusiness className="h-4 w-4" />} />
            <Metric href="/jobs?health=stale" title="Stale" value={staleJobs} detail="Needs review" icon={<TimerReset className="h-4 w-4" />} tone="warn" />
            <Metric href="/jobs?health=missing-data" title="Missing Data" value={missingDataCount} detail="Core coverage gaps" icon={<AlertTriangle className="h-4 w-4" />} tone="warn" />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
            <Panel className="overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Application Funnel</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Implied left-to-right status flow, with terminal outcomes split from the furthest reached stage.
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
                <Badge tone={staleJobs ? "warn" : "good"}>{staleJobs ? "Review" : "Clean"}</Badge>
              </div>
              <div className="mt-5 grid gap-5">
                <InsightList
                  title="Stale Jobs"
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
                  icon={<DollarSign className="h-4 w-4" />}
                  items={missingPayItems}
                  empty="Pay coverage is complete."
                />
                <CoverageBlock
                  title="Missing Fit"
                  icon={<FileSearch className="h-4 w-4" />}
                  items={missingFitItems}
                  empty="Fit scores are complete."
                />
                <CoverageBlock
                  title="Low Confidence"
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
        <div className={cn("grid h-8 w-8 place-items-center rounded-md", tone === "warn" ? "bg-amber-50 text-amber-700" : "bg-accent text-accent-foreground")}>
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
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const maxCount = Math.max(1, ...nodes.map((node) => node.count), ...links.map((link) => link.value));
  const total = nodesById.get("Saved")?.count ?? 0;
  const width = 920;
  const height = 330;
  const positions = new Map<string, { x: number; y: number }>();

  stageOrder.forEach((status, index) => {
    positions.set(status, { x: 46 + index * 124, y: 166 });
  });
  terminalOrder.forEach((status, index) => {
    positions.set(status, { x: 790, y: 82 + index * 86 });
  });

  if (!total) {
    return (
      <div className="mt-6 grid min-h-72 place-items-center rounded-md border border-dashed border-border text-sm text-muted-foreground">
        Add jobs to build the funnel.
      </div>
    );
  }

  return (
    <div className="mt-5 overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="min-h-[330px] min-w-[920px]">
        <defs>
          <filter id="sankeyShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" floodOpacity="0.12" />
          </filter>
        </defs>
        {links.map((link) => {
          const source = positions.get(link.source);
          const target = positions.get(link.target);
          if (!source || !target) return null;
          const strokeWidth = Math.max(3, Math.min(30, (link.value / maxCount) * 30));
          const color = stageColors[link.target] ?? stageColors[link.source] ?? "#0f766e";
          const path = `M ${source.x + 28} ${source.y} C ${source.x + 86} ${source.y}, ${target.x - 86} ${target.y}, ${target.x - 28} ${target.y}`;
          return (
            <a key={`${link.source}-${link.target}`} href={jobsStatusHref(link.target)} aria-label={`Open ${link.target} jobs`} className="cursor-pointer">
              <path d={path} fill="none" stroke={color} strokeOpacity="0.2" strokeWidth={strokeWidth + 8} strokeLinecap="round" />
              <path d={path} fill="none" stroke={color} strokeOpacity="0.55" strokeWidth={strokeWidth} strokeLinecap="round" />
            </a>
          );
        })}
        {nodes.map((node) => {
          const position = positions.get(node.id);
          if (!position) return null;
          return (
            <a key={node.id} href={jobsStatusHref(node.id)} aria-label={`Open ${node.label} jobs`} className="cursor-pointer">
              <SankeyNode node={node} x={position.x} y={position.y} maxCount={maxCount} />
            </a>
          );
        })}
      </svg>
    </div>
  );
}

function SankeyNode({
  node,
  x,
  y,
  maxCount
}: {
  node: DashboardSankeyNode;
  x: number;
  y: number;
  maxCount: number;
}) {
  const height = Math.max(24, Math.min(96, (node.count / maxCount) * 96));
  const color = stageColors[node.id] ?? "#0f766e";
  const labelY = node.kind === "terminal" ? y + 44 : y + 72;
  return (
    <g filter="url(#sankeyShadow)">
      <rect x={x - 24} y={y - height / 2} width="48" height={height} rx="7" fill={color} opacity={node.count ? 0.95 : 0.28} />
      <text x={x} y={y + 5} textAnchor="middle" className="fill-white text-sm font-semibold">
        {node.count}
      </text>
      <text x={x} y={labelY} textAnchor="middle" className="fill-slate-700 text-[11px] font-medium">
        {node.label}
      </text>
    </g>
  );
}

function InsightList({
  title,
  items,
  empty,
  action
}: {
  title: string;
  items?: DashboardJobInsight[];
  empty: string;
  action?: (item: DashboardJobInsight) => React.ReactNode;
}) {
  const safeItems = items ?? [];
  return (
    <div>
      <div className="mb-3 text-sm font-semibold">{title}</div>
      {safeItems.length ? (
        <div className="grid gap-3">
          {safeItems.map((item) => (
            <div key={`${title}-${item.id}`} className="border-b border-border pb-3 last:border-0 last:pb-0">
              <InsightHeader item={item} />
              <div className="mt-3 flex flex-wrap gap-2">
                {action ? action(item) : null}
                <Link href={`/jobs/${item.id}`}>
                  <Button size="sm" variant="ghost">
                    <ExternalLink className="h-4 w-4" />
                    Open
                  </Button>
                </Link>
              </div>
            </div>
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
  icon,
  items,
  empty
}: {
  title: string;
  icon: React.ReactNode;
  items?: DashboardJobInsight[];
  empty: string;
}) {
  const safeItems = items ?? [];
  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <span className="text-primary">{icon}</span>
        {title}
      </div>
      {safeItems.length ? (
        <div className="grid gap-3">
          {safeItems.slice(0, 4).map((item) => (
            <div key={`${title}-${item.id}`} className="flex items-start justify-between gap-3 border-b border-border pb-3 last:border-0 last:pb-0">
              <InsightHeader item={item} compact />
              <Link href={`/jobs/${item.id}`} className="shrink-0 text-sm font-medium text-primary">
                Open
              </Link>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

function InsightHeader({ item, compact = false }: { item: DashboardJobInsight; compact?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn("font-medium", compact ? "text-sm" : "text-base")}>
          {item.company}
        </span>
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
