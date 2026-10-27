"use client";

import { useId, useState } from "react";
import Link from "next/link";
import type { DashboardSankey } from "@/lib/types";
import { funnelHref, funnelOutcomes, layoutFunnel } from "@/lib/funnel-layout";
import { Button } from "@/components/ui/button";
import { ChartNoAxesCombined, List } from "lucide-react";

const colors: Record<string, string> = {
  Saved: "hsl(var(--chart-saved))", Applied: "hsl(var(--chart-applied))",
  "Recruiter Screen": "hsl(var(--chart-recruiter))", "Tech Screen": "hsl(var(--chart-tech))",
  "Final Interview": "hsl(var(--chart-final))", Offer: "hsl(var(--chart-offer))",
  Rejected: "hsl(var(--chart-rejected))", Withdrawn: "hsl(var(--chart-withdrawn))", Ghosted: "hsl(var(--chart-ghosted))"
};

export function FunnelChart({ sankey, since }: { sankey?: DashboardSankey; since: string }) {
  const [view, setView] = useState<"chart" | "counts">("chart");
  const descriptionId = useId();
  const layout = layoutFunnel(sankey ?? { nodes: [], links: [] });
  const href = (flow: typeof layout.flows[number]) => funnelHref(flow.stopped ? flow.source : flow.target, since, flow.stopped ? undefined : flow.source, flow.stopped);
  const label = (flow: typeof layout.flows[number]) => flow.stopped
    ? `${flow.value} jobs with no later stage after ${flow.source}, excluding closed outcomes`
    : `${flow.value} jobs ${funnelOutcomes.includes(flow.target) ? flow.target.toLowerCase() + " after" : "from " + flow.source + " to"} ${funnelOutcomes.includes(flow.target) ? flow.source : flow.target}`;

  return <section aria-label="Application funnel visualization" className="min-w-0">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1"><h2 className="text-base font-semibold">Application Sankey</h2><Link href={funnelHref("Saved", since)} aria-label="View funnel jobs" className="text-sm text-muted-foreground underline">{layout.total} tracked jobs</Link></div>
      <div className="flex gap-2" aria-label="Funnel display">
        <Button size="sm" title="Chart" aria-label="Chart" variant={view === "chart" ? "primary" : "secondary"} aria-pressed={view === "chart"} onClick={() => setView("chart")}><ChartNoAxesCombined className="h-4 w-4" /></Button>
        <Button size="sm" title="Counts & drill-downs" aria-label="Counts & drill-downs" variant={view === "counts" ? "primary" : "secondary"} aria-pressed={view === "counts"} onClick={() => setView("counts")}><List className="h-4 w-4" /></Button>
      </div>
    </div>
    <p id={descriptionId} className="sr-only">Flow thickness represents jobs on one shared scale. Each stage splits into the next stage, closed outcomes, or “No later stage”: jobs whose furthest recorded stage is here and which are not currently closed. This can include jobs moved back to an earlier status. Closed outcomes are included; archived jobs are excluded. Use the counts view for the same drill-downs without chart scrolling.</p>
    {!layout.total ? <p className="my-4 rounded-md border border-dashed border-border p-4 text-sm">No non-archived jobs in this cohort. Change the date filter or <Link href="/jobs" className="underline">open the tracker</Link>.</p> : null}
    {view === "chart" ? <>
      <div role="region" aria-label="Scrollable proportional funnel" aria-describedby={descriptionId} tabIndex={0} className="mt-4 overflow-x-auto rounded-md border border-border focus-visible:ring-2 focus-visible:ring-ring">
        <svg aria-label="Proportional application Sankey" role="group" viewBox={`0 0 ${layout.width} ${layout.height}`} className="w-full min-w-[1000px]" style={{ aspectRatio: `${layout.width} / ${layout.height}` }}>
          {layout.flows.map(flow => <a key={`${flow.source}-${flow.target}`} href={href(flow)} aria-label={label(flow)} className="group outline-none">
            <title>{label(flow)}</title>
            <path data-flow={`${flow.source}:${flow.target}`} data-count={flow.value} data-thickness={flow.height} d={flow.path} fill={colors[flow.stopped ? flow.source : flow.target]} className="opacity-40 group-hover:opacity-75 group-focus:opacity-100" />
            <path d={flow.centerPath} fill="none" stroke="transparent" strokeWidth={Math.max(14, flow.height)} />
            {flow.exit ? <>
              <rect x={flow.x} y={flow.y} width={12} height={flow.height} fill={colors[flow.stopped ? flow.source : flow.target]} />
              <text x={flow.x + 18} y={flow.y + flow.height / 2 - 3} className="fill-foreground text-[14px] group-focus:underline"><tspan>{flow.target}</tspan><tspan x={flow.x + 18} dy={17}>{flow.value} jobs</tspan></text>
            </> : null}
          </a>)}
          {layout.stages.map(stage => <a key={stage.id} href={funnelHref(stage.id, since)} aria-label={`${stage.id}: ${stage.count} jobs reached this stage; ${stage.recorded} recorded, ${stage.count - stage.recorded} inferred`} className="group outline-none">
            <title>{stage.id}: {stage.count} reached; {stage.recorded} recorded, {stage.count - stage.recorded} inferred</title>
            <rect x={stage.x - 6} y={12} width={166} height={40} rx={4} className="fill-transparent group-hover:fill-accent group-focus:fill-accent group-focus:stroke-primary" />
            <text x={stage.x} y={27} className="fill-foreground text-[14px] font-medium">{stage.id}</text>
            <text x={stage.x} y={46} className="fill-muted-foreground text-[14px]">{stage.count} jobs</text>
            <rect data-stage={stage.id} x={stage.x} y={stage.y} width={12} height={stage.height} fill={colors[stage.id]} />
            {!stage.count ? <path d={`M${stage.x},65 h12`} className="stroke-muted-foreground" strokeDasharray="2 2" /> : null}
          </a>)}
        </svg>
      </div>
    </> : <div className="grid gap-4">
      <ol aria-label="Stages reached" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{layout.stages.map(stage => <li key={stage.id} className="rounded-md border border-border p-3 text-sm">
        <Link className="font-semibold underline" href={funnelHref(stage.id, since)}>{stage.id}: {stage.count}</Link>
        <p className="mt-1 text-xs text-muted-foreground">{stage.recorded} recorded · {stage.count - stage.recorded} inferred · {layout.total ? Math.round(stage.count / layout.total * 100) : 0}% of tracked jobs</p>
        <p className="mt-1 text-xs text-muted-foreground">{(() => {
          const index = layout.stages.indexOf(stage);
          const previous = index ? layout.stages[index - 1].count : layout.total;
          return previous ? `${Math.round(stage.count / previous * 100)}% from ${index ? layout.stages[index - 1].id : "saved jobs"}` : "No previous-stage jobs";
        })()}</p>
        <ul className="mt-2 grid gap-1">{layout.flows.filter(flow => flow.source === stage.id).map(flow => <li key={flow.target}><Link className="block py-2 underline focus-visible:ring-2 focus-visible:ring-ring" href={href(flow)} aria-label={label(flow)}>{flow.target}: {flow.value}</Link></li>)}</ul>
        {!stage.count ? <p className="mt-2 text-muted-foreground">No jobs reached this stage.</p> : null}
      </li>)}</ol>
    </div>}
    <div className="mt-4 flex flex-wrap gap-x-5 gap-y-3 text-sm" aria-label="Closed outcome totals">{funnelOutcomes.map(status => <Link key={status} className="py-2 underline" href={funnelHref(status, since)}>{status}: {sankey?.nodes.find(node => node.id === status)?.count ?? 0}</Link>)}</div>
  </section>;
}
