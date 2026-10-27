"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Badge, Panel } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { analyticsSince } from "@/lib/analytics-cohort";

export function TopSkillGaps() {
  const since = analyticsSince(useSearchParams());
  const query = useQuery({ queryKey: ["dashboard", since], queryFn: () => api.dashboard(since), refetchInterval: 60000 });
  const gaps = query.data?.top_skill_gaps ?? [];
  return <Panel>
    <h2 id="top-skill-gaps" tabIndex={-1} className="scroll-mt-28 font-semibold">Top Skill Gaps</h2>
    <p className="mb-4 mt-1 text-xs text-muted-foreground">Open opportunities{since ? ` saved since ${since} (UTC)` : " · all time"}</p>
    {query.isLoading ? <p role="status">Loading top skill gaps…</p> : null}
    {query.error ? <p role="alert" className="text-sm text-destructive">{query.error.message} <Button variant="secondary" onClick={() => query.refetch()}>Retry top skill gaps</Button></p> : null}
    {!gaps.length && !query.isLoading && !query.error ? <p className="text-sm text-muted-foreground">Run analysis or resume matching to populate active skill gaps.</p> : null}
    <div className="grid gap-4">{gaps.map(gap => <div key={gap.skill_name} className="border-b border-border pb-4 last:border-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><div className="font-semibold">{gap.skill_name}</div><div className="mt-1 text-sm text-muted-foreground">{gap.suggested_action}</div></div>
        <div className="flex flex-wrap gap-2"><Badge tone={gap.source === "resume_match" ? "warn" : "neutral"}>{gap.source.replace("_", " ")}</Badge><Badge>{gap.count} jobs</Badge></div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">{gap.affected_jobs.map(job => <Link key={`${gap.skill_name}-${job.id}`} href={`/jobs/${job.id}`} className="rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground">{job.company}</Link>)}</div>
    </div>)}</div>
  </Panel>;
}
