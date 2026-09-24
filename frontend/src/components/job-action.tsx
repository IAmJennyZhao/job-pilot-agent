"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { JobAction } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Panel } from "@/components/ui/panel";
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

function ActionForm({ jobId, action }: { jobId: string; action: JobAction | null }) {
  const [title, setTitle] = useState(action?.title ?? "");
  const [due, setDue] = useState(action?.due_date ?? localDate());
  const [saved, setSaved] = useState(false);
  const client = useQueryClient();
  const confirm = useConfirm();
  const mutation = useMutation({
    mutationFn: async (mode: "save" | "complete" | "remove"): Promise<JobAction | void> => mode === "remove" ? api.deleteAction(jobId) : api.saveAction(jobId, { title: title.trim(), due_date: due, completed: mode === "complete" }),
    onSuccess: () => { setSaved(true); client.invalidateQueries({ queryKey: ["actions"] }); }
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

export function ActionAgenda() {
  const query = useQuery({ queryKey: ["actions"], queryFn: api.actions });
  const [view, setView] = useState("Today");
  const [today, setToday] = useState(localDate);
  // Re-evaluate the local calendar day when a dashboard stays open overnight.
  useEffect(() => { const timer = window.setInterval(() => setToday(localDate()), 30000); return () => window.clearInterval(timer); }, []);
  const pending = (query.data ?? []).filter(action => !action.completed_at);
  const groups: Record<string, JobAction[]> = {
    Today: pending.filter(action => action.due_date === today),
    Overdue: pending.filter(action => action.due_date < today),
    Upcoming: pending.filter(action => action.due_date > today),
    Completed: (query.data ?? []).filter(action => action.completed_at)
  };
  return <Panel><h2 className="font-semibold">Your next actions</h2>
    <p className="my-2 text-sm text-muted-foreground">Across all jobs, including closed applications. Due dates use your local calendar day. Open a job to add an action.</p>
    <div className="mb-4 flex flex-wrap gap-2" aria-label="Action views">{Object.keys(groups).map(name => <Button key={name} variant={view === name ? "primary" : "secondary"} aria-pressed={view === name} onClick={() => setView(name)}>{name} ({groups[name].length})</Button>)}</div>
    {query.isLoading ? <p>Loading actions…</p> : query.error ? <><p role="alert">{query.error.message}</p><Button onClick={() => query.refetch()}>Retry actions</Button></> : groups[view].length ? <ul className="grid gap-3">{groups[view].map(action => <AgendaRow key={action.job_id} action={action} />)}</ul> : <p className="text-sm text-muted-foreground">No {view.toLowerCase()} actions.</p>}
  </Panel>;
}

function AgendaRow({ action }: { action: JobAction }) {
  const [editing, setEditing] = useState(false);
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.saveAction(action.job_id, { title: action.title, due_date: action.due_date, completed: !action.completed_at }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["actions"] })
  });
  return <li className="rounded-md border border-border p-3">
    <div className="flex flex-wrap items-center justify-between gap-3"><div className="min-w-0">
      <p className="break-words font-medium">{action.title}</p>
      <Link className="text-sm text-primary underline" href={`/jobs/${action.job_id}`}>{action.role_title} · {action.company}</Link>
      <p className="text-xs text-muted-foreground">Due {action.due_date} · {action.status}</p>
    </div><div className="flex gap-2"><Button variant="secondary" disabled={mutation.isPending} onClick={() => mutation.mutate()}>{action.completed_at ? "Reopen" : "Complete"}</Button><Button variant="ghost" aria-expanded={editing} onClick={() => setEditing(!editing)}>{editing ? "Cancel" : "Edit / reschedule"}</Button></div></div>
    {mutation.error ? <p role="alert">{mutation.error.message}</p> : null}
    {editing ? <div className="mt-3"><ActionForm jobId={action.job_id} action={action} /></div> : null}
  </li>;
}
