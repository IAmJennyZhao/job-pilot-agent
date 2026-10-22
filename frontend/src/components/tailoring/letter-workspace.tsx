"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useDraft } from "@/lib/use-draft";
import { letterContextDraft, letterRequestNonce, type LetterOptions, type LetterRequest } from "@/lib/letter-types";
import { PreferenceFlags } from "@/components/intake-review";
import { Button } from "@/components/ui/button";
import { Field, Select, Input, Textarea } from "@/components/ui/field";
import { Panel } from "@/components/ui/panel";
import { LetterReviewPanel } from "./letter-review";

const active = (state?: string) => state === "pending" || state === "running";
export function LetterWorkspace({ jobId, updatedAt }: { jobId: string; updatedAt: string }) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState<string>();
  const [reviewedHash, setReviewedHash] = useState<string>();
  const [options, setOptions] = useState<LetterOptions>({ count: 3, length: "standard", template_id: null });
  const context = useDraft(`letter-company-context-${jobId}`, { text: "", source_url: "", confirmed: false }, value => letterContextDraft.safeParse(value).success);
  const nonce = useDraft<{ fingerprint: string; key: string } | null>(`letter-request-${jobId}`, null, value => letterRequestNonce.safeParse(value).success);
  const generation = useMutation({
    mutationFn: ({ payload, parent }: { payload: LetterRequest; parent?: string }) => parent ? api.retryLetter(parent, payload) : api.generateLetter(jobId, payload),
    onSuccess: run => { setSelected(run.id); nonce.discard(); cache.setQueryData(["letter-run", run.id], run); },
    onSettled: () => cache.invalidateQueries({ queryKey: ["letter-workspace", jobId] })
  });
  const workspace = useQuery({ queryKey: ["letter-workspace", jobId, updatedAt], queryFn: () => api.letterWorkspace(jobId), retry: false,
    refetchInterval: q => generation.isPending || q.state.data?.runs.some(r => active(r.state)) ? 1500 : false });
  const ready = workspace.data?.readiness;
  const runId = selected ?? workspace.data?.runs[0]?.id;
  const result = useQuery({ queryKey: ["letter-run", runId], queryFn: () => api.letterRun(runId!), enabled: !!runId,
    refetchInterval: q => active(q.state.data?.state) ? 1500 : false });
  const running = generation.isPending || workspace.data?.runs.some(r => active(r.state));
  const reviewed = ready?.description_reviewed || reviewedHash === ready?.description_hash;
  const hasContext = Boolean(context.value.text.trim() || context.value.source_url.trim());
  const canGenerate = ready?.ready && reviewed && !running && !workspace.isFetching && nonce.ready && context.ready && (!hasContext || (context.value.confirmed && context.value.text.trim() && context.value.source_url.trim()));
  const start = (parent?: string) => {
    if (!canGenerate || !ready?.input_hash) return;
    const values = { expected_input_hash: ready.input_hash, reviewed_description_hash: ready.description_hash,
      acknowledged_evaluation_hash: ready.evaluation.evaluation_hash, options: { ...options, company_context: hasContext ? { text: context.value.text, source_url: context.value.source_url, confirmed: true as const } : null } };
    const fingerprint = JSON.stringify({ ...values, parent });
    const key = nonce.value?.fingerprint === fingerprint ? nonce.value.key : crypto.randomUUID();
    nonce.setValue({ fingerprint, key });
    generation.mutate({ payload: { ...values, request_key: key }, parent });
  };
  const run = result.data;
  return <Panel><section aria-label="Cover letters" className="grid min-w-0 gap-4">
    <h2 className="font-semibold">Cover letters</h2>
    <p className="text-sm text-muted-foreground">Generate letters independently of your resume. Each sentence is checked against approved evidence before you review the saved draft.</p>
    {[{ name: "company context", draft: context }, { name: "generation request", draft: nonce }].map(item => item.draft.recoveryRaw !== null ? <div role="alert" key={item.name} className="grid gap-2"><p>The saved {item.name} has an incompatible format. Download a recovery copy before discarding it.</p><a className="text-sm underline" href={`data:application/json;charset=utf-8,${encodeURIComponent(item.draft.recoveryRaw)}`} download={`letter-${item.name.replaceAll(" ", "-")}-recovery.json`}>Download {item.name} recovery</a><Button variant="ghost" className="w-fit" onClick={() => item.draft.discard()}>Discard incompatible {item.name}</Button></div> : null)}
    {workspace.error ? <p role="alert">{workspace.error.message}</p> : !ready ? <p role="status">Loading letter readiness…</p> : <>
      <details><summary className="cursor-pointer">Preference checks and saved posting</summary><div className="grid gap-3 pt-3"><PreferenceFlags evaluation={ready.evaluation} /><pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs">{ready.source_content}</pre></div></details>
      {ready.missing.length ? <ul className="list-inside list-disc text-sm">{ready.missing.map(m => <li key={m}>{m.replaceAll("resume generation", "letter generation").replaceAll("generating a resume", "generating a letter")}</li>)}</ul> : null}
      {!ready.description_reviewed ? <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={Boolean(reviewed)} onChange={e => setReviewedHash(e.target.checked ? ready.description_hash : undefined)} />I reviewed the full saved posting for this letter.</label> : null}
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Letter variants"><Select value={options.count} disabled={Boolean(running)} onChange={e => setOptions({ ...options, count: Number(e.target.value) })}>{[1, 2, 3].map(n => <option key={n} value={n}>{n} {n === 1 ? "variant" : "variants"}</option>)}</Select></Field>
        <Field label="Letter length"><Select value={options.length} disabled={Boolean(running)} onChange={e => setOptions({ ...options, length: e.target.value as LetterOptions["length"] })}><option value="standard">Standard · 180–250 words</option><option value="short">Short · 100–150 words</option></Select></Field>
        <Field label="Letter style template"><Select value={options.template_id ?? ""} disabled={Boolean(running)} onChange={e => setOptions({ ...options, template_id: e.target.value || null })}><option value="">No template</option>{workspace.data?.templates.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</Select></Field>
      </div>
      <details><summary className="cursor-pointer text-sm">Optional company-source excerpt</summary><div className="mt-3 grid gap-3"><p className="text-xs">Paste an exact excerpt you checked. This supplies company context only; it cannot support claims about your experience. No URL is fetched automatically.</p><Field label="Company context source URL"><Input value={context.value.source_url} disabled={Boolean(running)} onChange={e => context.setValue({ ...context.value, source_url: e.target.value, confirmed: false })} /></Field><Field label="Company source excerpt"><Textarea maxLength={4000} value={context.value.text} disabled={Boolean(running)} onChange={e => context.setValue({ ...context.value, text: e.target.value, confirmed: false })} /></Field><label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={context.value.confirmed} disabled={Boolean(running)} onChange={e => context.setValue({ ...context.value, confirmed: e.target.checked })} />I checked this excerpt against its source and approve using it as company context.</label><Button variant="ghost" className="w-fit" disabled={Boolean(running)} onClick={() => context.discard()}>Clear company context</Button></div></details>
      <p className="text-xs text-muted-foreground">Templates guide paragraph rhythm only. Their personal history is not used as evidence. Generate acknowledges the displayed preference checks.</p>
      <div className="flex flex-wrap gap-2"><Button disabled={!canGenerate} onClick={() => start()}>{generation.isPending ? "Generating letters…" : "Generate tailored cover letters"}</Button><Button variant="secondary" onClick={() => { workspace.refetch(); if (runId) result.refetch(); }}>Refresh letter progress</Button></div>
      {generation.error ? <p role="alert">{generation.error.message} Refresh progress before retrying; a request may still be running.</p> : null}
      {nonce.storageError ? <p role="alert">Browser recovery storage is unavailable. Check run history after a connection failure.</p> : null}
      {workspace.data?.runs.length ? <Field label="Letter generation history"><Select value={runId ?? ""} onChange={e => setSelected(e.target.value)}>{workspace.data.runs.map(r => <option value={r.id} key={r.id}>{r.state} · {new Date(r.created_at).toLocaleString()} · {r.id.slice(0, 8)}</option>)}</Select></Field> : null}
      {result.error ? <p role="alert">{result.error.message}</p> : null}
      {run ? <>
        <p role="status">Letter run: {run.state}</p>
        {run.error ? <p role="alert">{run.error}</p> : null}
        {run.source_changed ? <p className="text-sm">The posting or approved sources changed. This historical draft is preserved.</p> : null}
        {run.state === "failed" || run.state === "interrupted" ? <div className="grid gap-2"><Button variant="secondary" className="w-fit" disabled={!canGenerate} onClick={() => start(run.id)}>Retry letter generation</Button><p className="text-xs">Retry requires the same options and sources, creates a linked run, and repeats writing and checking. A previous uncertain request may have incurred usage.</p></div> : null}
        <details><summary className="cursor-pointer">Letter generation checks</summary><ul className="grid gap-2 pt-2">{run.stages.map(s => <li key={s.id} className="rounded border p-3 text-sm">{s.stage === "letter_draft" ? "Write draft" : "Check sentence evidence"} · attempt {s.attempt} · {s.state}{s.error ? <p>{s.error}</p> : null}{s.validation?.issues.map((i, n) => <p key={n}>{i.field_path}: {i.message}</p>)}</li>)}</ul></details>
        {run.revision ? <LetterReviewPanel key={run.revision.id} baselineId={run.revision.id} sourceKey={ready.input_hash} /> : null}
      </> : null}
    </>}
  </section></Panel>;
}
