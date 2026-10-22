"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useDraft } from "@/lib/use-draft";
import { letterLocalDraft, letterCheckNonce, type LetterEdit, type LetterLocalDraft, type LetterReview, type LetterSentence } from "@/lib/letter-types";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";

function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const acceptsDraft = (value: unknown) => letterLocalDraft.safeParse(value).success;

export function LetterReviewPanel({ baselineId, sourceKey }: { baselineId: string; sourceKey: string | null }) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState<string>();
  const query = useQuery({ queryKey: ["letter-review", baselineId, selected, sourceKey], queryFn: () => api.letterReview(baselineId, selected),
    refetchInterval: q => q.state.data?.checks.some(c => c.state === "running") ? 1500 : false });
  const update = (view: LetterReview) => {
    cache.setQueryData(["letter-review", baselineId, view.revision.id, sourceKey], view);
    setSelected(view.revision.id);
    cache.invalidateQueries({ queryKey: ["letter-review", baselineId] });
  };
  if (query.error) return <p role="alert">{query.error.message}</p>;
  if (!query.data) return <p role="status">Loading letter review…</p>;
  return <section aria-label="Cover letter review" className="grid min-w-0 gap-4 border-t pt-4">
    <h3 className="font-semibold">Review and edit letters</h3>
    <Button variant="ghost" className="w-fit" onClick={() => { setSelected(undefined); cache.invalidateQueries({ queryKey: ["letter-review", baselineId] }); }}>Refresh letter review</Button>
    <Field label="Letter revision history"><Select value={query.data.revision.id} onChange={e => setSelected(e.target.value)}>{query.data.history.map(r => <option key={r.id} value={r.id}>Revision {r.sequence} · {r.origin}{r.reviewed ? " · Reviewed" : ""}{r.id === query.data?.current_revision_id ? " · Current" : ""}</option>)}</Select></Field>
    <LetterEditor view={query.data} onUpdated={update} onRefresh={() => { setSelected(undefined); cache.invalidateQueries({ queryKey: ["letter-review", baselineId] }); }} />
  </section>;
}

function LetterEditor({ view, onUpdated, onRefresh }: { view: LetterReview; onUpdated: (view: LetterReview) => void; onRefresh: () => void }) {
  const [variant, setVariant] = useState(0);
  const [reviewedHash, setReviewedHash] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const draft = useDraft<LetterLocalDraft>(`letter-edit-${view.profile_id}-${view.baseline_id}`,
    { version: 1, base: view.current_revision_id, key: "", edit: view.revision.edit }, acceptsDraft);
  const checks = useDraft<{ key: string; revision: string } | null>(`letter-check-${view.profile_id}-${view.baseline_id}`, null, value => letterCheckNonce.safeParse(value).success);
  const current = view.revision.id === view.current_revision_id;
  const conflict = draft.dirty && draft.value.base !== view.current_revision_id;
  const pendingCheck = view.checks.some(c => c.state === "running");
  const reviewToken = JSON.stringify([view.revision.id, view.revision.content_hash, view.revision.validation_hash, view.input_hash]);
  const accept = (updated: LetterReview) => { draft.discard(); setReviewedHash(undefined); onUpdated(updated); };
  const save = useMutation({ mutationFn: () => api.saveLetter(view.baseline_id, { request_key: draft.value.key || crypto.randomUUID(), expected_revision_id: draft.value.base, edit: draft.value.edit }), onSuccess: accept, onError: onRefresh });
  const restore = useMutation({ mutationFn: () => api.restoreLetter(view.baseline_id, { request_key: crypto.randomUUID(), expected_revision_id: view.current_revision_id, revision_id: view.revision.id }), onSuccess: accept });
  const check = useMutation({ mutationFn: (key: string) => api.checkLetter(view.baseline_id, { request_key: key, expected_revision_id: view.revision.id, content_hash: view.revision.content_hash }),
    onSuccess: updated => { checks.discard(); onUpdated(updated); }, onError: onRefresh });
  const approve = useMutation({ mutationFn: () => api.reviewLetter(view.baseline_id, { revision_id: view.revision.id, content_hash: view.revision.content_hash, validation_hash: view.revision.validation_hash, input_hash: view.input_hash }), onSuccess: onUpdated });
  const exporting = useMutation({ mutationFn: async (action: "copy" | "txt" | "md") => {
    const blob = await api.downloadLetter(view.baseline_id, view.revision.id, variant, action === "md" ? "md" : "txt");
    if (action === "copy") { await navigator.clipboard.writeText(await blob.text()); setNotice("Reviewed letter copied."); }
    else { saveBlob(blob, `cover-letter-${view.revision.id.slice(0, 8)}-${variant+1}.${action}`); setNotice("Reviewed letter downloaded."); }
  } });
  const busy = save.isPending || restore.isPending || check.isPending || approve.isPending || pendingCheck;
  const edit = current ? draft.value.edit : view.revision.edit;
  const chosen = edit.variants[variant] ?? edit.variants[0];
  const update = (change: (edit: LetterEdit) => void) => {
    const next = structuredClone(draft.value.edit); change(next);
    draft.setValue({ ...draft.value, edit: next, key: crypto.randomUUID() });
    setReviewedHash(undefined); setNotice(undefined);
  };
  const changeSentence = (p: number, s: number, patch: Partial<LetterSentence>) => update(e => Object.assign(e.variants[variant].paragraphs[p].sentences[s], patch));
  const startCheck = () => {
    setReviewedHash(undefined);
    const key = checks.value?.revision === view.revision.id ? checks.value.key : crypto.randomUUID();
    checks.setValue({ key, revision: view.revision.id }); check.mutate(key);
  };
  const exportable = Boolean(view.approval && view.revision.validation.valid && (!current || !draft.dirty));
  const error = save.error ?? restore.error ?? check.error ?? approve.error ?? exporting.error;
  return <div className="grid min-w-0 gap-4">
    {view.source_problem ? <p role="alert" className="text-sm">{view.source_problem} Previously reviewed downloads remain available.</p> : null}
    {draft.recoveryRaw !== null ? <div role="alert" className="grid gap-2 rounded border p-3"><p>A saved local letter draft has an incompatible format. Download it before discarding.</p><div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => saveBlob(new Blob([draft.recoveryRaw!], { type: "application/json" }), "letter-draft-recovery.json")}>Download letter recovery</Button><Button variant="ghost" onClick={() => draft.discard()}>Discard incompatible letter draft</Button></div></div> : null}
    {draft.storageError || checks.storageError ? <p role="alert">Browser draft storage is unavailable. Keep this page open until your work is saved.</p> : null}
    {checks.recoveryRaw !== null ? <div role="alert" className="grid gap-2"><p>The saved evidence-check request has an incompatible format.</p><Button variant="secondary" className="w-fit" onClick={() => saveBlob(new Blob([checks.recoveryRaw!], { type: "application/json" }), "letter-check-recovery.json")}>Download evidence-check recovery</Button><Button variant="ghost" className="w-fit" onClick={() => checks.discard()}>Discard incompatible evidence-check request</Button></div> : null}
    {conflict ? <div role="alert" className="grid gap-2 rounded border p-3"><p>A newer letter revision exists. Your local edits are preserved. Compare them with the saved preview before choosing how to continue.</p><Button variant="secondary" className="w-fit" onClick={() => draft.setValue({ ...draft.value, base: view.current_revision_id, key: crypto.randomUUID() })}>Keep my edits on current revision</Button></div> : null}
    <Field label="Letter variant"><Select value={variant} onChange={e => { setVariant(Number(e.target.value)); setNotice(undefined); }}>{edit.variants.map((v, n) => <option key={v.variant_id} value={n}>{n+1}. {v.angle}</option>)}</Select></Field>
    <p className="text-sm">{chosen.paragraphs.reduce((n, p) => n + p.sentences.reduce((total, s) => total + s.text.trim().split(/\s+/).filter(Boolean).length, 0), 0)} body words · Revision {view.revision.sequence}{draft.dirty && current ? " · Unsaved local edits" : ""}</p>
    <details open><summary className="cursor-pointer font-medium">Saved letter preview</summary><pre className="mt-3 whitespace-pre-wrap break-words rounded border bg-muted/30 p-4 font-sans text-sm leading-7">{view.variant_texts[variant]}</pre></details>
    {!current ? <p className="text-sm">Historical revision. Restore it to create a new editable version; its existing review remains attached to this version.</p> : null}
    {current ? <details><summary className="cursor-pointer font-medium">Edit letter sentences</summary><div className="mt-3 grid gap-4">
      <p className="text-sm">Use one sentence per field. Saving invalidates evidence checks. Add new facts to the approved bank before using them here.</p>
      {chosen.paragraphs.map((p, pi) => <fieldset key={pi} className="grid min-w-0 gap-3 rounded border p-3"><legend className="px-1 text-sm font-medium">Paragraph {pi+1}</legend>
        {p.sentences.map((s, si) => <div key={s.id} className="grid min-w-0 gap-2 border-b pb-3 last:border-b-0">
          <Field label={`Paragraph ${pi+1}, sentence ${si+1}`}><Textarea value={s.text} disabled={busy || !draft.ready} onChange={e => changeSentence(pi, si, { text: e.target.value })} /></Field>
          <Field label={`Sentence ${pi+1}.${si+1} kind`}><Select value={s.sentence_kind} disabled={busy || !draft.ready} onChange={e => changeSentence(pi, si, { sentence_kind: e.target.value as LetterSentence["sentence_kind"] })}>{["candidate_claim", "job_context", "motivation", "transition"].map(kind => <option key={kind} value={kind}>{kind.replaceAll("_", " ")}</option>)}</Select></Field>
          <details><summary className="cursor-pointer text-sm">Supporting evidence for sentence {pi+1}.{si+1}</summary><div className="mt-2 grid gap-2">{([{ label: "Candidate", items: view.evidence, key: "candidate_evidence_ids" }, { label: "Posting", items: view.job_evidence, key: "job_evidence_ids" }] as const).map(group => <fieldset key={group.key} className="grid gap-2"><legend className="text-sm font-medium">{group.label}</legend>{group.items.map(item => <label key={item.id} className="flex items-start gap-2 break-words text-xs"><input type="checkbox" disabled={busy || !draft.ready} checked={s[group.key].includes(item.id)} onChange={e => changeSentence(pi, si, { [group.key]: e.target.checked ? [...s[group.key], item.id] : s[group.key].filter(id => id !== item.id) })} /><span>{item.id}: {item.text}{"constraints" in item && item.constraints.length ? ` Constraints: ${item.constraints.join(" ")}` : ""}</span></label>)}</fieldset>)}</div></details>
          <Button variant="ghost" className="w-fit" disabled={busy || !draft.ready || p.sentences.length === 1} onClick={() => update(e => { e.variants[variant].paragraphs[pi].sentences.splice(si, 1); })}>Remove sentence {pi+1}.{si+1}</Button>
        </div>)}
        <Button variant="secondary" className="w-fit" disabled={busy || !draft.ready || p.sentences.length >= 10} onClick={() => update(e => { e.variants[variant].paragraphs[pi].sentences.push({ id: crypto.randomUUID(), text: "", sentence_kind: "motivation", candidate_evidence_ids: [], job_evidence_ids: [] }); })}>Add sentence to paragraph {pi+1}</Button>
        <Button variant="ghost" className="w-fit" disabled={busy || !draft.ready || chosen.paragraphs.length === 1} onClick={() => update(e => { e.variants[variant].paragraphs.splice(pi, 1); })}>Remove paragraph {pi+1}</Button>
      </fieldset>)}
      <Button variant="secondary" className="w-fit" disabled={busy || !draft.ready || chosen.paragraphs.length >= 5} onClick={() => update(e => { e.variants[variant].paragraphs.push({ sentences: [{ id: crypto.randomUUID(), text: "", sentence_kind: "motivation", candidate_evidence_ids: [], job_evidence_ids: [] }] }); })}>Add letter paragraph</Button>
      <div className="flex flex-wrap gap-2"><Button disabled={busy || !draft.ready || !draft.dirty} onClick={() => save.mutate()}>Save letter edits</Button><Button variant="ghost" disabled={busy || !draft.dirty} onClick={() => draft.discard()}>Discard local letter edits</Button></div>
    </div></details> : <Button variant="secondary" className="w-fit" disabled={busy || draft.dirty || !draft.ready} onClick={() => restore.mutate()}>Restore letter as new revision</Button>}
    <details><summary className="cursor-pointer">Sentence evidence assessment</summary><div className="mt-3 grid gap-3">{view.sentence_assessment?.sentences.map(s => <div key={s.sentence_id} className="rounded border p-3 text-sm"><p className="font-medium">{s.sentence_id}: {s.supported ? "Supported" : "Needs correction"}</p><p>{s.explanation}</p>{s.supports.map((q, i) => <blockquote className="mt-2 border-l-2 pl-3 text-xs" key={i}>{q.source_id}: {q.quote}</blockquote>)}</div>) ?? <p className="text-sm">This saved revision needs an independent sentence check.</p>}</div></details>
    <details><summary className="cursor-pointer">Changes from generated letter</summary><div className="mt-2 grid gap-3">{view.changes_from_baseline.length ? view.changes_from_baseline.map(change => <div key={change.field_path} className="grid gap-2 rounded border p-3 text-sm sm:grid-cols-2"><div><strong>Before</strong><p className="whitespace-pre-wrap break-words">{change.before && typeof change.before === "object" && "text" in change.before ? String(change.before.text) : "Sentence added"}</p></div><div><strong>After</strong><p className="whitespace-pre-wrap break-words">{change.after && typeof change.after === "object" && "text" in change.after ? String(change.after.text) : "Sentence removed"}</p></div></div>) : <p className="text-sm">No sentence or citation changes from the generated draft.</p>}</div></details>
    <details><summary className="cursor-pointer">Posting context not cited in this variant</summary><p className="mt-2 text-xs">These excerpts are not cited by this saved variant. This list does not imply that you meet every cited requirement.</p><ul className="mt-2 grid gap-2 text-sm">{view.job_evidence.filter(e => !view.revision.edit.variants[variant].paragraphs.some(p => p.sentences.some(s => s.job_evidence_ids.includes(e.id)))).map(e => <li key={e.id} className="rounded border p-2">{e.text}</li>)}</ul></details>
    {view.revision.validation.issues.length ? <ul aria-label="Letter validation issues" className="list-inside list-disc text-sm">{view.revision.validation.issues.map((i, n) => <li key={n}>{i.field_path}: {i.message}</li>)}</ul> : <p className="text-sm">Sentence evidence checks passed. Human review is still required.</p>}
    {view.checks.filter(c => c.revision_id === view.revision.id).slice(0, 1).map(c => <p role="status" key={c.id}>Sentence check: {c.state}{c.error ? ` · ${c.error}` : ""}</p>)}
    {current && !view.approval ? <>
      <Button variant="secondary" className="w-fit" disabled={busy || draft.dirty || !draft.ready || !checks.ready || !!view.source_problem} onClick={startCheck}>{check.isPending ? "Checking sentence evidence…" : "Check sentence evidence"}</Button>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={reviewedHash === reviewToken} disabled={busy || draft.dirty || !view.approval_eligible} onChange={e => setReviewedHash(e.target.checked ? reviewToken : undefined)} />I reviewed all {view.revision.edit.variants.length} saved letter variants and their supporting evidence.</label>
      <Button className="w-fit" disabled={busy || draft.dirty || !draft.ready || !view.approval_eligible || reviewedHash !== reviewToken} onClick={() => approve.mutate()}>Approve exact letter revision</Button>
    </> : view.approval ? <p className="text-sm font-medium">This saved letter revision was reviewed.</p> : null}
    <div className="flex flex-wrap gap-2"><Button variant="secondary" disabled={!exportable || exporting.isPending} onClick={() => exporting.mutate("copy")}>Copy reviewed letter</Button><Button variant="secondary" disabled={!exportable || exporting.isPending} onClick={() => exporting.mutate("txt")}>Download letter TXT</Button><Button variant="secondary" disabled={!exportable || exporting.isPending} onClick={() => exporting.mutate("md")}>Download letter Markdown</Button></div>
    {notice ? <p role="status">{notice}</p> : null}{error ? <p role="alert">{error.message}</p> : null}
  </div>;
}
