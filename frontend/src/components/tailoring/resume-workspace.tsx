"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { useDraft } from "@/lib/use-draft";
import type { GenerationRequest, GenerationRun } from "@/lib/generation-types";
import { PreferenceFlags } from "@/components/intake-review";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Panel } from "@/components/ui/panel";
import { ResumeReview } from "./resume-review";

const stages = [ ["select", "Select evidence"], ["critique", "Critique"], ["revise", "Revise"], ["polish", "Polish"] ] as const;
const active = (state?: string) => state === "pending" || state === "running";

export function ResumeWorkspace({ jobId, updatedAt }: { jobId: string; updatedAt: string }) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [reviewedHash, setReviewedHash] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const saveKey = useDraft<{ fingerprint: string; key: string } | null>(`resume-request-${jobId}`, null);
  const generate = useMutation({
    mutationFn: ({ payload, parent }: { payload: GenerationRequest; parent?: string }) => parent ? api.retryResume(parent, payload) : api.generateResume(jobId, payload),
    onSuccess: run => {
      setSelected(run.id);
      cache.invalidateQueries({ queryKey: ["resume-run", run.id] });
      saveKey.discard();
      cache.invalidateQueries({ queryKey: ["resume-workspace", jobId] });
    },
    onError: () => cache.invalidateQueries({ queryKey: ["resume-workspace", jobId] })
  });
  const workspace = useQuery({ queryKey: ["resume-workspace", jobId, updatedAt], queryFn: () => api.generationWorkspace(jobId), retry: false,
    refetchInterval: query => generate.isPending || query.state.data?.runs.some(run => active(run.state)) ? 1500 : false });
  const current = workspace.data;
  const ready = current?.readiness;
  const description = useDraft(`tailoring-description-${jobId}`, ready?.source_content ?? "");
  const saveDescription = useMutation({ mutationFn: () => api.updateJob(jobId, { source_content: description.value }), onSuccess: () => {
    description.clear(); setEditing(false); setReviewedHash(null);
    cache.invalidateQueries({ queryKey: ["job", jobId] });
    cache.invalidateQueries({ queryKey: ["resume-workspace", jobId] });
  } });
  const runId = selected ?? current?.runs[0]?.id;
  const runQuery = useQuery({ queryKey: ["resume-run", runId, ready?.input_hash], queryFn: () => api.generationRun(runId!), enabled: !!runId, staleTime: 0,
    refetchInterval: query => active(query.state.data?.state) ? 1000 : false });
  const run = runQuery.data;
  const running = generate.isPending || current?.runs.some(r => active(r.state));
  const reviewed = Boolean(ready?.description_reviewed || ready?.description_hash === reviewedHash);
  const canGenerate = ready?.ready && reviewed && !running && !editing && !workspace.isFetching && saveKey.ready;
  const start = (parent?: string) => {
    if (!canGenerate || !ready?.input_hash) return;
    const values = { expected_input_hash: ready.input_hash, reviewed_description_hash: ready.description_hash, acknowledged_evaluation_hash: ready.evaluation.evaluation_hash };
    const fingerprint = JSON.stringify({ ...values, parent });
    const key = saveKey.value?.fingerprint === fingerprint ? saveKey.value.key : crypto.randomUUID();
    saveKey.setValue({ fingerprint, key });
    generate.mutate({ payload: { ...values, request_key: key }, parent });
  };
  return <Panel><section id="tailoring-preparation" aria-label="Resume tailoring" className="grid gap-4 scroll-mt-4">
    <h2 className="font-semibold">Tailoring preparation</h2>
    <p className="text-sm text-muted-foreground">Generate a saved resume draft in four passes. Detailed job analysis remains a separate optional action.</p>
    {workspace.isPending ? <p role="status">Loading tailoring readiness…</p> : workspace.error ? <p role="alert">{workspace.error.message} <Button onClick={() => workspace.refetch()}>Refresh readiness</Button></p> : ready ? <>
      <PreferenceFlags evaluation={ready.evaluation} />
      {ready.saved_evaluation ? <details><summary className="cursor-pointer text-sm">Checks recorded when saved</summary><div className="mt-2"><PreferenceFlags evaluation={ready.saved_evaluation} /></div></details> : null}
      {ready.missing.length ? <ul className="list-inside list-disc text-sm text-warning-foreground">{ready.missing.map(reason => <li key={reason}>{reason}</li>)}</ul> : null}
      <Link className="w-fit text-sm underline" href="/profile?tab=base">Review sources in Application Assets</Link>
      <details><summary className="cursor-pointer text-sm font-medium">Review full saved job description</summary><pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">{ready.source_content || "No description saved."}</pre></details>
      {editing ? <div className="grid gap-2">
        <Field label="Full job description for tailoring"><Textarea className="min-h-48" value={description.value} onChange={e => description.setValue(e.target.value)} /></Field>
        <div className="flex gap-2"><Button disabled={saveDescription.isPending || !description.value.trim() || description.value.length > 100000} onClick={() => saveDescription.mutate()}>Save description</Button><Button variant="ghost" disabled={saveDescription.isPending} onClick={() => { description.discard(); setEditing(false); }}>Cancel description edit</Button></div>
        {saveDescription.error ? <p role="alert" className="text-sm text-destructive">{saveDescription.error.message}</p> : null}
      </div> : <Button className="w-fit" variant="secondary" disabled={Boolean(running)} onClick={() => setEditing(true)}>{description.dirty ? "Resume description edit" : "Edit full description"}</Button>}
      {ready.description_reviewed ? <p className="text-sm">Full job description reviewed.</p> : <label className="flex items-start gap-2 text-sm"><input type="checkbox" disabled={!ready.source_content.trim() || editing} checked={reviewed} onChange={e => setReviewedHash(e.target.checked ? ready.description_hash : null)} />I reviewed this complete saved job description.</label>}
      <div className="flex flex-wrap gap-2"><Button disabled={!canGenerate} onClick={() => start()}>{generate.isPending ? "Generating resume…" : "Generate tailored resume"}</Button>
        <Button variant="secondary" disabled={workspace.isFetching} onClick={() => { workspace.refetch(); if (runId) runQuery.refetch(); }}>Refresh progress</Button>
      </div>
      <p className="text-xs text-muted-foreground">Generate acknowledges the displayed preference checks. Red flags do not prevent generation. A draft does not mark this job Applied or select a resume asset.</p>
      {generate.error ? <p role="alert" className="text-sm text-destructive">{generate.error.message} Refresh progress before retrying; the server may still be working.</p> : null}
      {saveKey.storageError ? <p className="text-sm text-warning-foreground">Browser draft storage is unavailable. Check saved run history after a connection failure.</p> : null}
      {current && current.runs.length > 0 ? <Field label="Resume generation history"><Select value={runId ?? ""} onChange={e => setSelected(e.target.value)}>{current.runs.map((r, index) => <option key={r.id} value={r.id}>{index === 0 ? "Latest: " : ""}{r.state} — {new Date(r.created_at).toLocaleString()} — {r.id.slice(0, 8)}</option>)}</Select></Field> : null}
      {runQuery.error ? <p role="alert" className="text-sm text-destructive">{runQuery.error.message}</p> : null}
      {run ? <>
        <RunProgress run={run} />
        {run.source_changed ? <p className="text-sm text-warning-foreground">Sources or the job changed after this run. This historical draft is preserved; generate a new draft for the current inputs.</p> : null}
        {run.error ? <p role="alert" className="text-sm text-destructive">{run.error}</p> : null}
        {(run.state === "failed" || run.state === "interrupted") ? <div className="grid gap-2">
          <Button className="w-fit" variant="secondary" disabled={!canGenerate || run.input_hash !== ready.input_hash} onClick={() => start(run.id)}>Retry from saved checkpoints</Button>
          <p className="text-xs text-muted-foreground">Retry creates a linked attempt with the same inputs and reuses validated stages. An uncertain provider request may have already incurred usage. Changed inputs require a new generation.</p>
        </div> : null}
        {run.revision ? <ResumeReview key={run.revision.id} baselineId={run.revision.id} sourceKey={ready.input_hash} /> : null}
        <details><summary className="cursor-pointer text-sm">Intermediate drafts, critique and validation</summary><div className="mt-3 grid gap-3">{run.stages.map(attempt => <details key={attempt.id} className="rounded border border-border p-3"><summary className="cursor-pointer text-sm">{attempt.stage} — attempt {attempt.attempt}: {attempt.state}{attempt.metadata.reused_from_attempt ? " (reused checkpoint)" : ""}</summary>
          {attempt.error ? <p className="my-2 text-sm text-destructive">{attempt.error}</p> : null}
          {attempt.validation?.blocking_issues.map(issue => <p className="my-2 text-sm" key={issue}>{issue}</p>)}
          {attempt.metadata.usage ? <p className="my-2 text-xs">Tokens: {attempt.metadata.usage.input_tokens ?? "unknown"} in / {attempt.metadata.usage.output_tokens ?? "unknown"} out</p> : null}
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs">{JSON.stringify(attempt.output, null, 2)}</pre>
        </details>)}</div></details>
      </> : running ? <p role="status" className="text-sm">Waiting for the server to persist the new run…</p> : null}
      <p className="text-sm text-muted-foreground">Review the saved content, then inspect its PDF preview before approving final downloads.</p>
    </> : null}
  </section></Panel>;
}

function RunProgress({ run }: { run: GenerationRun }) {
  return <div className="grid gap-2"><p role="status" className="text-sm font-medium">Resume run: {run.state}</p><ol aria-label="Resume generation progress" className="grid gap-2 sm:grid-cols-4">{stages.map(([key, label]) => {
    const attempt = run.stages.filter(s => s.stage === key).sort((a, b) => b.attempt - a.attempt)[0];
    return <li key={key} className="rounded border border-border p-3 text-sm"><strong>{label}</strong><p>{attempt?.state ?? "Not started"}</p>{attempt && attempt.attempt > 1 ? <p className="text-xs">Repair attempt</p> : null}</li>;
  })}</ol></div>;
}
