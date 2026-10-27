"use client";

import { useId, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { OutcomeRow } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { analyticsSince } from "@/lib/analytics-cohort";
import { PageHeader, Panel } from "@/components/ui/panel";

const groupLabels = { source: "Job source", category: "Role category", resume: "Resume version" };
const rate = (value: number | null) => value === null ? "—" : `${value}%`;

export default function ReportsPage() {
  const params = useSearchParams();
  const since = analyticsSince(params);
  const requestedGroup = params.get("group");
  const dimension: "source" | "category" | "resume" = requestedGroup === "category" || requestedGroup === "resume" ? requestedGroup : "source";
  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("tab", "outcomes");
    if (value) next.set(key, value); else next.delete(key);
    window.history.pushState(null, "", `/dashboard?${next}${window.location.hash}`);
  };
  const query = useQuery({ queryKey: ["outcome-report", since], queryFn: () => api.outcomeReport(since) });
  return <div className="grid gap-6">
    <PageHeader title="Search outcomes" />
    <Panel>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Field label="Group by"><Select value={dimension} onChange={event => setFilter("group", event.target.value)}>{Object.entries(groupLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></Field>
        <h2 className="text-sm font-medium">{query.data?.total_jobs ?? 0} saved jobs in this cohort</h2>
      </div>
      <details className="my-4 text-xs text-muted-foreground"><summary className="cursor-pointer">How counts are calculated</summary><div className="mt-2 grid max-w-4xl gap-2">
        <p>Includes archived and closed jobs. Interviews mean reaching Recruiter Screen or later; rates divide by applications that reached Applied or later. Later stages imply earlier stages. An empty denominator shows “—”.</p>
        <p>Labels are frozen when progress beyond Saved is first recorded. A resume version identifies the selected resume content at that point, not proof of submission. Older jobs without a recorded version stay unknown; their source and category use current details. Small samples and recent applications can distort comparisons.</p>
      </div></details>
      {query.isLoading ? <p role="status">Loading outcomes…</p> : query.error ? <><p role="alert">{query.error.message}</p><Button onClick={() => query.refetch()}>Retry report</Button></> : <>
        <div role="region" aria-label="Outcome comparisons" tabIndex={0} className="overflow-x-auto rounded-md border border-border focus-visible:ring-2 focus-visible:ring-ring">
          <table className="w-full min-w-[780px] text-sm">
            <caption className="sr-only">Outcomes by {groupLabels[dimension].toLowerCase()}. View a row to see its contributing jobs.</caption>
            <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground"><tr>
              <th scope="col" className="z-10 w-32 min-w-32 max-w-32 bg-card px-3 py-3 text-left sm:sticky sm:left-0 sm:w-auto sm:min-w-40 sm:max-w-56">{groupLabels[dimension]}</th>
              {["Saved", "Applied", "Interviews", "Interview rate", "Offers", "Offer rate"].map(label => <th key={label} scope="col" className="whitespace-nowrap px-3 py-3 text-right font-medium">{label}</th>)}
              <th scope="col" className="sticky right-0 z-10 bg-card px-1 py-3 text-right font-medium sm:px-3">Jobs</th>
            </tr></thead>
            <tbody>{query.data?.groups[dimension].map(row => <ComparisonRow key={`${dimension}:${since}:${row.label}`} row={row} since={since} />)}</tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted-foreground sm:hidden">Swipe for more columns.</p>
        {query.data?.total_jobs === 0 ? <p className="mt-4 text-sm">No jobs in this date range.</p> : null}
      </>}
    </Panel>
  </div>;
}

function ComparisonRow({ row, since }: { row: OutcomeRow; since: string }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  return <>
    <tr className="border-b border-border last:border-0">
      <th scope="row" className="z-10 w-32 min-w-32 max-w-32 bg-card px-3 py-2 text-left font-medium sm:sticky sm:left-0 sm:w-auto sm:min-w-40 sm:max-w-56">
        <span className="break-words">{row.label}</span>
        {row.applied < 10 ? <span className="block text-xs font-normal text-warning-foreground" title={`${row.applied} applications. Treat rates as directional.`}>Small sample</span> : null}
      </th>
      {[row.saved, row.applied, row.interviews, rate(row.interview_rate), row.offers, rate(row.offer_rate)].map((value, index) => <td key={index} className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{value}</td>)}
      <td className="sticky right-0 z-10 bg-card px-1 py-2 text-right sm:px-3"><Button size="sm" variant="ghost" className="min-h-11 gap-1 px-2 sm:gap-2 sm:px-3" aria-label={`${expanded ? "Hide" : "View"} ${row.saved} contributing jobs for ${row.label}`} aria-expanded={expanded} aria-controls={detailsId} onClick={() => setExpanded(value => !value)}>{expanded ? "Hide" : "View"}<ChevronDown aria-hidden="true" className={`h-4 w-4 transition-transform ${expanded ? "rotate-180" : ""}`} /></Button></td>
    </tr>
    <tr id={detailsId} hidden={!expanded} className="border-b border-border bg-muted/20"><td colSpan={8} className="p-3">{expanded ? <ContributingJobs row={row} since={since} /> : null}</td></tr>
  </>;
}

function ContributingJobs({ row, since }: { row: OutcomeRow; since: string }) {
  const query = useQuery({ queryKey: ["jobs", "outcome-details", since], queryFn: () => api.jobs({ includeArchived: true, savedSince: since }) });
  const jobs = new Map(query.data?.map(job => [job.id, job]));
  return <div className="sticky left-0 max-w-[calc(100vw-6rem)] sm:max-w-none">
    <h3 className="mb-2 text-xs font-medium text-muted-foreground">{row.saved} contributing jobs</h3>
    {query.isLoading ? <p role="status" className="text-xs">Loading job titles…</p> : null}
    {query.error ? <p role="alert" className="mb-2 text-xs text-destructive">Job titles could not load. Saved job links remain available. <Button size="sm" variant="secondary" onClick={() => query.refetch()}>Retry job titles</Button></p> : null}
    <ul className="grid gap-2">{row.job_ids.map((id, index) => {
      const job = jobs.get(id);
      return <li key={id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded border border-border bg-card px-3 py-2">
        <div className="min-w-0"><Link href={`/jobs/${id}`} className="break-words font-medium text-primary underline">{job?.role_title ?? `Open contributing job ${index + 1}`}</Link>{job ? <p className="break-words text-xs text-muted-foreground">{job.company}</p> : null}</div>
        {job ? <span className="text-xs text-muted-foreground">{job.status}</span> : null}
      </li>;
    })}</ul>
  </div>;
}
