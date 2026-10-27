"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DashboardActionSuggestion, JobAction } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { actionViews, agendaMatches, mergeAgenda, type ActionView, type AgendaItem } from "@/lib/action-agenda";
import { Panel, Badge } from "@/components/ui/panel";
import { useConfirm } from "@/components/ui/confirm-provider";

function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function JobActionEditor({ jobId }: { jobId: string }) {
  const query = useQuery({ queryKey: ["actions", jobId], queryFn: () => api.action(jobId) });
  return <Panel><h2 className="mb-3 font-semibold">Next action</h2>
    {query.isLoading ? <p>Loading next action…</p> : query.error ? <><p role="alert">{query.error.message}</p><Button onClick={() => query.refetch()}>Retry</Button></> :
      <ActionForm key={`${jobId}:${query.data?.title}:${query.data?.due_date}:${query.data?.completed_at}`} jobId={jobId} action={query.data ?? null} />}
  </Panel>;
}

function ActionForm({ jobId, action, onSaved }: { jobId: string; action: JobAction | null; onSaved?: () => void }) {
  const [title, setTitle] = useState(action?.title ?? "");
  const [due, setDue] = useState(action?.due_date ?? localDate());
  const [saved, setSaved] = useState(false);
  const client = useQueryClient();
  const confirm = useConfirm();
  const mutation = useMutation({
    mutationFn: async (mode: "save" | "complete" | "remove"): Promise<JobAction | void> => mode === "remove" ? api.deleteAction(jobId) : api.saveAction(jobId, { title: title.trim(), due_date: due, completed: mode === "complete" }),
    onSuccess: () => { setSaved(true); client.invalidateQueries({ queryKey: ["actions"] }); onSaved?.(); }
  });
  return <form className="grid gap-3" onSubmit={event => { event.preventDefault(); mutation.mutate("save"); }}>
    {action?.completed_at ? <p role="status" className="text-sm text-success-foreground">Completed. Save an action below to plan your next step.</p> : null}
    <fieldset disabled={mutation.isPending} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px]">
      <Field label="Next action"><Input required maxLength={500} value={title} onChange={event => { setTitle(event.target.value); setSaved(false); }} placeholder="Follow up with the recruiter" /></Field>
      <Field label="Due date"><Input required type="date" value={due} onChange={event => { setDue(event.target.value); setSaved(false); }} /></Field>
    </fieldset>
    <div className="flex flex-wrap gap-2">
      <Button disabled={mutation.isPending || !title.trim() || !due} type="submit">{mutation.isPending ? "Saving…" : action?.completed_at ? "Save next action" : "Save action"}</Button>
      {action && !action.completed_at ? <Button type="button" variant="secondary" disabled={mutation.isPending || !title.trim() || !due} onClick={() => mutation.mutate("complete")}>Mark complete</Button> : null}
      {action ? <Button type="button" variant="ghost" disabled={mutation.isPending} onClick={async () => { if (await confirm("Delete this next action?")) mutation.mutate("remove"); }}>Remove action</Button> : null}
    </div>
    {mutation.error ? <p role="alert" className="text-sm text-destructive">{mutation.error.message}</p> : null}
    {saved ? <p role="status" className="text-sm">Action saved.</p> : null}
  </form>;
}

type AgendaProps = {
  suggestions: DashboardActionSuggestion[];
  suggestionsLoading: boolean;
  suggestionsError: Error | null;
  onRetrySuggestions: () => void;
  since: string;
};

export function ActionAgenda(props: AgendaProps) {
  const query = useQuery({ queryKey: ["actions"], queryFn: api.actions });
  const [view, setView] = useState<ActionView>("To do");
  const [showAll, setShowAll] = useState(false);
  const [today, setToday] = useState(localDate);
  useEffect(() => { const timer = window.setInterval(() => setToday(localDate()), 30000); return () => window.clearInterval(timer); }, []);
  const items = mergeAgenda(query.data ?? [], props.suggestions, today);
  const matching = items.filter(item => agendaMatches(item, view, today));
  const visible = new Set((showAll ? matching : matching.slice(0, 8)).map(item => item.id));
  const cohortHref = (health: string) => `/jobs?health=${health}${props.since ? `&since=${encodeURIComponent(props.since)}` : ""}`;
  return <Panel>
    <h2 id="search-health" className="scroll-mt-28 font-semibold">Your next actions</h2>
    <div className="mb-3 flex flex-wrap gap-2" aria-label="Action views">{actionViews.map(name => <Button key={name} variant={view === name ? "primary" : "secondary"} aria-pressed={view === name} onClick={() => { setView(name); setShowAll(false); }}>{name} ({items.filter(item => agendaMatches(item, name, today)).length})</Button>)}</div>
    <details className="mb-4 text-xs text-muted-foreground"><summary className="cursor-pointer">About actions</summary><div className="mt-2 grid gap-2"><p>Scheduled tasks span all jobs and use local due dates. Completing a task leaves the job status unchanged.</p><p>Suggestions cover open jobs {props.since ? `saved since ${props.since} (UTC)` : "from all time"}. They are computed, not saved tasks. Overdue/today tasks appear first, then stale/data suggestions, then future tasks.</p></div></details>
    {query.isLoading ? <p role="status">Loading scheduled tasks…</p> : null}
    {props.suggestionsLoading ? <p role="status">Loading computed suggestions…</p> : null}
    {query.error ? <div role="alert" className="mb-3 text-sm">Scheduled tasks could not refresh: {query.error.message}. Computed suggestions remain available.<Button variant="secondary" onClick={() => query.refetch()}>Retry scheduled tasks</Button></div> : null}
    {props.suggestionsError ? <div role="alert" className="mb-3 text-sm">Computed suggestions could not refresh: {props.suggestionsError.message}. Scheduled tasks remain available.<Button variant="secondary" onClick={props.onRetrySuggestions}>Retry suggestions</Button></div> : null}
    <ul aria-label="Jobs with actions or suggestions" className="grid gap-3">{items.map(item => <AgendaRow key={item.id} item={item} hidden={!visible.has(item.id)} today={today} />)}</ul>
    {!matching.length && !query.isLoading && !props.suggestionsLoading && !query.error && !props.suggestionsError ? <p className="text-sm text-muted-foreground">No {view.toLowerCase()} items.</p> : null}
    {matching.length > 8 ? <Button className="mt-3" variant="secondary" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer jobs" : `Show all ${matching.length} jobs`}</Button> : null}
    <div className="mt-4 flex flex-wrap gap-3 text-sm"><Link className="underline" href={cohortHref("stale")}>All stale jobs</Link><Link className="underline" href={cohortHref("missing-data")}>All missing data</Link></div>
  </Panel>;
}

function AgendaRow({ item, hidden, today }: { item: AgendaItem; hidden: boolean; today: string }) {
  const [editing, setEditing] = useState(false);
  const { action, suggestion } = item;
  const job = action ?? suggestion!;
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.saveAction(item.id, { title: action!.title, due_date: action!.due_date, completed: !action!.completed_at }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["actions"] })
  });
  const ghost = useMutation({
    mutationFn: () => api.updateJob(item.id, { status: "Ghosted" }),
    onSuccess: () => {
      for (const key of ["dashboard", "jobs", "job", "actions", "outcome-report"]) client.invalidateQueries({ queryKey: [key] });
    }
  });
  return <li hidden={hidden} data-job-id={item.id} className="rounded-md border border-border p-4">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <Link className="min-w-0 break-words font-medium text-primary underline" href={`/jobs/${item.id}`}>{job.role_title} · {job.company}</Link>
      <Badge>{job.status}</Badge>
    </div>
    {action ? <div className="mt-3">
      <p className="text-xs font-medium text-muted-foreground">Scheduled task · {action.completed_at ? "Completed" : action.due_date < today ? "Overdue" : action.due_date === today ? "Today" : "Upcoming"}</p>
      <p className="mt-1 break-words font-medium">{action.title}</p>
      <p className="text-xs text-muted-foreground">Due {action.due_date} · local calendar date</p>
      <div className="mt-2 flex flex-wrap gap-2"><Button variant="secondary" disabled={mutation.isPending || editing} onClick={() => mutation.mutate()}>{action.completed_at ? "Reopen" : "Complete"}</Button><Button variant="ghost" disabled={mutation.isPending} aria-expanded={editing} onClick={() => setEditing(!editing)}>{editing ? "Cancel" : "Edit / reschedule"}</Button></div>
      {mutation.error ? <p role="alert" className="text-sm text-destructive">{mutation.error.message}</p> : null}
      {editing ? <div className="mt-3"><ActionForm jobId={item.id} action={action} onSaved={() => setEditing(false)} /></div> : null}
    </div> : null}
    {suggestion ? <div className={`${action ? "mt-3 border-t border-border pt-3" : "mt-2"} flex flex-wrap items-center justify-between gap-3`}>
      <div className="min-w-0"><p className="text-xs font-medium text-muted-foreground">Computed suggestions · not scheduled</p>
      <div className="mt-2 flex flex-wrap gap-2">{suggestion.reasons.map(reason => <Badge key={reason.kind} tone="warn">{reason.label}</Badge>)}</div></div>
      <div className="ml-auto flex flex-wrap items-center gap-3">
        {suggestion.reasons.some(reason => reason.kind === "stale") ? <Button size="sm" variant="secondary" disabled={ghost.isPending || editing || mutation.isPending} onClick={() => ghost.mutate()}>{ghost.isPending ? "Updating…" : "Mark as ghosted"}</Button> : null}
        <Link className="py-2 text-sm underline" href={`/jobs/${item.id}`}>Review job</Link>
      </div>
      {ghost.error ? <p role="alert" className="w-full text-sm text-destructive">{ghost.error.message}</p> : null}
    </div> : null}
  </li>;
}
