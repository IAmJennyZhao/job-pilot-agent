"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { analyticsSince } from "@/lib/analytics-cohort";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Panel } from "@/components/ui/panel";

export function AnalyticsFilter({ view }: { view: "overview" | "outcomes" }) {
  const params = useSearchParams();
  const [expanded, setExpanded] = useState(false);
  const since = analyticsSince(params);
  const conflictingLegacy = ["saved_since", "outcomesSince"].some(key => params.has(key) && params.get(key) !== since);
  const validDate = !since || (/^\d{4}-\d{2}-\d{2}$/.test(since) && !Number.isNaN(Date.parse(since)) && new Date(since).toISOString().slice(0, 10) === since);
  const setSince = (value: string) => {
    const next = new URLSearchParams(params.toString());
    next.delete("outcomesSince");
    next.delete("saved_since");
    if (value) next.set("since", value); else next.delete("since");
    window.history.pushState(null, "", `/dashboard${next.size ? `?${next}` : ""}${window.location.hash}`);
  };
  const sinceDaysAgo = (days: number) => {
    const date = new Date();
    date.setUTCDate(date.getUTCDate() - days);
    setSince(date.toISOString().slice(0, 10));
  };
  return <Panel>
    <details open={expanded || !validDate || conflictingLegacy} onToggle={event => setExpanded(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm font-medium">Analytics cohort <span className="ml-2 text-muted-foreground">{since || "All time"}</span></summary>
    <div className="mt-4 flex flex-wrap items-end gap-3">
      <Field label="Jobs saved on or after (UTC)"><Input type="date" value={since} onChange={event => setSince(event.target.value)} aria-invalid={!validDate} /></Field>
      <Button variant="secondary" onClick={() => sinceDaysAgo(30)}>30 days ago</Button>
      <Button variant="secondary" onClick={() => sinceDaysAgo(90)}>90 days ago</Button>
      <Button variant="ghost" onClick={() => setSince("")}>All time</Button>
    </div>
    <p className="mt-3 text-sm text-muted-foreground">{view === "overview" ? "Funnel: includes closed outcomes, excludes archived jobs. Health, coverage and skill gaps: open opportunities only (Saved through Offer)." : "Outcomes: includes all jobs in the cohort, including archived and closed jobs. Its total can differ from the Overview funnel and active count."}</p>
    <details className="mt-3 text-sm text-muted-foreground">
      <summary className="cursor-pointer">Date basis and eligibility</summary>
      <div className="mt-2 grid gap-2">
        <p>The date uses when a job was first saved, inclusive from midnight UTC, with no end date. All time removes that lower bound. Full progression history is counted, not just activity after the selected date. Editing, applying or archiving a job does not reset its saved date.</p>
        <p>Open opportunities are Saved, Applied, Recruiter Screen, Tech Screen, Final Interview and Offer. Rejected, Withdrawn, Ghosted and Archived are excluded from health, coverage and skill gaps. The funnel includes Rejected, Withdrawn and Ghosted, but excludes Archived.</p>
        <p>Outcomes includes archived history to preserve comparisons. Reaching a later stage implies the earlier stages. Interviews mean Recruiter Screen or later; interview and offer rates divide by jobs that reached Applied or later. Drill-downs retain the population and date of their metric.</p>
        <p>Staleness uses time since the latest status movement as of now, not the cohort start. Scheduled actions span all saved jobs and use your local calendar day for due dates.</p>
      </div>
    </details>
    </details>
    {!validDate ? <p role="alert" className="mt-3 text-sm text-destructive">Invalid date in this link: {since}. Choose a valid date or All time.</p> : null}
    {conflictingLegacy ? <p role="status" className="mt-3 text-sm text-warning-foreground">This link has different legacy date filters. Both views now use {since || "All time"}; choose a date to replace the old filters.</p> : null}
  </Panel>;
}
