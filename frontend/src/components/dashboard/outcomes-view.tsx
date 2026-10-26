"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { PageHeader, Panel } from "@/components/ui/panel";

export default function ReportsPage() {
  const params = useSearchParams();
  const since = params.get("outcomesSince") ?? "";
  const requestedGroup = params.get("group");
  const dimension: "source" | "category" | "resume" = requestedGroup === "category" || requestedGroup === "resume" ? requestedGroup : "source";
  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("tab", "outcomes");
    if (value) next.set(key, value); else next.delete(key);
    window.history.replaceState(null, "", `/dashboard?${next}`);
  };
  const query = useQuery({ queryKey: ["outcome-report", since], queryFn: () => api.outcomeReport(since) });
  return <div className="grid gap-6"><PageHeader title="Search outcomes" description="Compare where applications reach interviews and offers." />
    <Panel><div className="flex flex-wrap items-end gap-3"><Field label="Group by"><Select value={dimension} onChange={event => setFilter("group", event.target.value)}><option value="source">Job source</option><option value="category">Role category</option><option value="resume">Resume version</option></Select></Field><Field label="Jobs saved on or after (UTC)"><Input type="date" value={since} onChange={event => setFilter("outcomesSince", event.target.value)} /></Field><Button variant="secondary" onClick={() => setFilter("outcomesSince", "")}>All time</Button></div>
      <p className="mt-3 text-sm text-muted-foreground">Includes archived and closed jobs. Interviews mean reaching Recruiter Screen or later; rates divide by applications that reached Applied or later. Later stages imply earlier stages. An empty denominator shows “—”.</p>
      <p className="mt-2 text-sm text-muted-foreground">Labels are frozen when progress beyond Saved is first recorded. A resume version identifies the selected resume content at that point, not proof of submission. Older jobs without a recorded version stay unknown; their source and category use current details. Small samples and recent applications can distort comparisons.</p>
    </Panel>
    {query.isLoading ? <Panel>Loading outcomes…</Panel> : query.error ? <Panel><p role="alert">{query.error.message}</p><Button onClick={() => query.refetch()}>Retry report</Button></Panel> : <Panel><h2 className="mb-4 font-semibold">{query.data?.total_jobs ?? 0} saved jobs in this cohort</h2><div className="grid gap-4">{query.data?.groups[dimension].map(row => <article key={row.label} className="rounded-md border border-border p-4"><h3 className="break-words font-semibold">{row.label}</h3><dl className="my-3 grid grid-cols-2 gap-3 md:grid-cols-5">{[["Saved", row.saved], ["Applied", row.applied], ["Interviews", row.interviews], ["Interview rate", row.interview_rate === null ? "—" : `${row.interview_rate}%`], ["Offers / rate", `${row.offers} / ${row.offer_rate === null ? "—" : `${row.offer_rate}%`}`]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="font-medium">{value}</dd></div>)}</dl>{row.applied < 10 ? <p className="text-xs text-warning-foreground">Small sample: {row.applied} applications. Treat rates as directional.</p> : null}<details className="mt-3 text-sm"><summary className="cursor-pointer">View {row.saved} contributing jobs</summary><ul className="mt-2 grid gap-1">{row.job_ids.map((id, index) => <li key={id}><Link className="text-primary underline" href={`/jobs/${id}`}>Open contributing job {index + 1}</Link></li>)}</ul></details></article>)}{query.data?.total_jobs === 0 ? <p>No jobs in this date range.</p> : null}</div></Panel>}
  </div>;
}
