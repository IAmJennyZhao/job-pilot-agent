"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { useDraft } from "@/lib/use-draft";
import type { ReviewWorkspace, ResumeEdit, ResumeChange, SaveResumeEdit, RestoreResumeRevision } from "@/lib/review-types";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Badge, Panel } from "@/components/ui/panel";
import { ResumeExports } from "./resume-exports";
import { SavedTextPreview } from "./document-workflow";
import { acceptsResumeDraft, acceptsResumeRestore } from "@/lib/resume-draft";

export function ResumeReview({ baselineId, sourceKey }: { baselineId: string; sourceKey?: string | null }) {
  const [selected, setSelected] = useState<string>();
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["resume-review", baselineId, selected, sourceKey], queryFn: () => api.resumeReview(baselineId, selected), staleTime: 0 });
  const saved = (result: ReviewWorkspace) => {
    setSelected(undefined);
    cache.setQueryData(["resume-review", baselineId, undefined, sourceKey], result);
    cache.invalidateQueries({ queryKey: ["resume-review", baselineId] });
  };
  if (!query.data) return <div>{query.error ? <p role="alert">{query.error.message}</p> : <p role="status">Loading resume review…</p>}<Button variant="secondary" onClick={() => query.refetch()}>Refresh resume</Button></div>;
  return <ReviewContent key={baselineId} view={query.data} onSelect={setSelected} onSaved={saved} onRefresh={() => query.refetch()} refreshing={query.isFetching} refreshError={query.error?.message} />;
}

function ReviewContent({ view, onSelect, onSaved, onRefresh, refreshing, refreshError }: {
  view: ReviewWorkspace; onSelect: (id?: string) => void; onSaved: (view: ReviewWorkspace) => void;
  onRefresh: () => void; refreshing: boolean; refreshError?: string;
}) {
  const revision = view.revision;
  const draft = useDraft<SaveResumeEdit>(`resume-edit-${view.profile_id}-${view.baseline_id}`, { expected_revision_id: revision.id, request_key: "", edit: revision.edit }, acceptsResumeDraft);
  const restoreRequest = useDraft<RestoreResumeRevision | null>(`resume-restore-${view.profile_id}-${view.baseline_id}`, null, acceptsResumeRestore);
  const [editing, setEditing] = useState(false);
  const [comparedRevision, setComparedRevision] = useState<string | null>(null);
  const [comparison, setComparison] = useState("baseline");
  const [claimId, setClaimId] = useState("");
  const isEditing = editing || draft.dirty;
  const save = useMutation({ mutationFn: (payload: SaveResumeEdit) => api.saveResumeEdit(view.baseline_id, payload), onSuccess: result => {
    draft.discard(); setEditing(false); setComparedRevision(null); onSaved(result);
  }, onError: onRefresh });
  const restore = useMutation({ mutationFn: (payload: RestoreResumeRevision) => api.restoreResumeRevision(view.baseline_id, payload), onSuccess: result => { restoreRequest.discard(); onSaved(result); }, onError: onRefresh });
  const review = useMutation({ mutationFn: () => api.reviewResume(view.baseline_id, { revision_id: revision.id, content_hash: revision.content_hash, validation_hash: revision.validation_hash, input_hash: view.input_hash }), onSuccess: onSaved, onError: onRefresh });
  const busy = save.isPending || restore.isPending || review.isPending;
  const stale = draft.value.expected_revision_id !== view.current_revision_id;
  const update = (edit: ResumeEdit) => { draft.setValue({ ...draft.value, request_key: crypto.randomUUID(), edit }); setComparedRevision(null); save.reset(); };
  const startEditing = () => { draft.setValue({ expected_revision_id: revision.id, request_key: crypto.randomUUID(), edit: structuredClone(revision.edit) }); setEditing(true); };
  const restoreSelected = () => {
    const payload = restoreRequest.value?.revision_id === revision.id ? restoreRequest.value : { request_key: crypto.randomUUID(), expected_revision_id: view.current_revision_id, revision_id: revision.id };
    restoreRequest.setValue(payload); restore.mutate(payload);
  };
  const recordLabel = (id: string) => { const r = view.records.find(r => r.id === id); return r ? [r.employer, r.title_display, r.name].filter(Boolean).join(" · ") : "Unknown source record"; };
  const edit = draft.value.edit;
  const normalizeProjects = (bullets: ResumeEdit["bullets"]) => {
    const selected = new Set(bullets.map(b => b.record_id));
    const projects = view.records.filter(r => r.kind === "project" && selected.has(r.id)).map(r => r.id);
    return [...edit.project_order.filter(id => projects.includes(id)), ...projects.filter(id => !edit.project_order.includes(id))];
  };
  const setBullets = (bullets: ResumeEdit["bullets"]) => update({ ...edit, bullets, project_order: normalizeProjects(bullets) });
  const moveBullet = (index: number, direction: number) => {
    const bullets = [...edit.bullets];
    let target = index + direction;
    while (target >= 0 && target < bullets.length && bullets[target].record_id !== bullets[index].record_id) target += direction;
    if (target >= 0 && target < bullets.length) { [bullets[index], bullets[target]] = [bullets[target], bullets[index]]; setBullets(bullets); }
  };
  const skills = new Map<string, { name: string; source_ids: string[] }>();
  view.technology_catalog.forEach(s => skills.set(s.name.toLowerCase(), { name: s.name, source_ids: [s.id] }));
  view.skill_groups.forEach(g => g.values.forEach(name => { if (!skills.has(name.toLowerCase())) skills.set(name.toLowerCase(), { name, source_ids: [g.id] }); }));
  // Keep an already selected approved alias visible too.
  edit.skills.forEach(s => { if (!skills.has(s.name.toLowerCase())) skills.set(s.name.toLowerCase(), s); });
  return <section id="resume-review" tabIndex={-1} aria-label="Resume review and editing" data-baseline-id={view.baseline_id} data-revision-id={revision.id} className="grid min-w-0 scroll-mt-28 gap-6">
    <Panel className="grid gap-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-lg font-semibold">Review and edit resume</h3><div className="flex flex-wrap gap-2"><Badge>{revision.id === view.current_revision_id ? "Current saved revision" : "Historical revision"}</Badge>{isEditing ? <Badge tone="warn">Unsaved local edits</Badge> : null}</div></div>
    {revision.content.advisory_review && <section aria-label="Advisory factual review" className="grid gap-2 rounded border border-border p-3 text-sm">
      <h4 className="font-medium">Advisory factual review</h4>
      {!view.advisory_current ? <p>These findings apply to an earlier draft. Your edits have not been reviewed by the model.</p> : revision.content.advisory_review.status === 'unavailable' ? <p>AI review was unavailable. Your draft is preserved for your review.</p> : <p>AI review completed. This is advisory feedback, not factual certification.</p>}
      <details open={!view.advisory_current || revision.content.advisory_review.findings.some(f => f.verdict !== "supported")}><summary className="cursor-pointer font-medium">Factual findings and review guidance</summary><div className="mt-2 grid gap-2">
      <p>Compare every rewritten bullet with its cited facts. AI feedback can be mistaken; your approval applies to this exact saved version.</p>
      <ul className="grid gap-2">{revision.content.advisory_review.findings.filter(f => f.verdict !== 'supported').map(f => <li key={f.bullet_id}><strong>{view.advisory_current ? 'Check' : 'Earlier finding'}:</strong> {f.explanation}<p className="text-muted-foreground">{revision.content.draft.bullets.find(b => b.id === f.bullet_id)?.text ?? 'The referenced bullet is no longer selected.'}</p></li>)}</ul>
      </div></details>
    </section>}
    {revision.content.content_budget && <p aria-label="Resume content budget" className="text-sm">
      {revision.content.content_budget.bullets} selected {revision.content.content_budget.bullets === 1 ? 'bullet' : 'bullets'}. {revision.content.content_budget.within_budget ? 'Within the estimated page budget.' : 'Above the estimated page budget; consider fewer or shorter approved claims.'} Render the saved revision to check actual one-page fit.
    </p>}
    {[draft, restoreRequest].map((recovery, index) => recovery.recoveryRaw !== null ? <div key={index} role="alert" className="grid gap-2 rounded border border-border p-3 text-sm">
      <p>A recovered {index === 0 ? "edit" : "restore request"} uses an incompatible or damaged format. Its original text is preserved. Download it before discarding if you need to recover your work.</p>
      <div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => {
        const url = URL.createObjectURL(new Blob([recovery.recoveryRaw!], { type: "application/json" }));
        const link = document.createElement("a"); link.href = url; link.download = "recovered-resume-draft.json"; document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      }}>Download recovered {index === 0 ? "edit" : "restore request"}</Button><Button variant="ghost" onClick={recovery.discard}>Discard incompatible {index === 0 ? "edit" : "restore request"}</Button></div>
    </div> : null)}
    <Field label="Resume revision history"><Select disabled={busy || isEditing} value={revision.id} onChange={e => { onSelect(e.target.value); review.reset(); restore.reset(); }}>
      {view.history.map(r => <option key={r.id} value={r.id}>{r.sequence === 0 ? "Original generated draft" : `Revision ${r.sequence} · ${r.origin}`} · {r.reviewed ? "Reviewed" : r.valid ? "Awaiting review" : "Needs correction"}{r.id === view.current_revision_id ? " · Current" : ""}</option>)}
    </Select></Field>
    <p className="text-xs text-muted-foreground">Saved {new Date(revision.created_at).toLocaleString()} · {revision.origin === "generated" ? "Original generation" : `Revision ${revision.sequence} · ${revision.origin}`}</p>
    <p role="status" className="text-sm font-medium">{isEditing ? "Unsaved edits — save and validate before review." : view.approved_current ? "Reviewed — this exact saved version is approved." : view.approval ? "Historically reviewed — this is not the current eligible version." : revision.validation.valid ? "Awaiting review — automated checks passed." : "Needs correction — resolve the saved validation issues."}</p>
    <p aria-label="Saved resume review eligibility" className="text-xs text-muted-foreground">Saved revision: {view.approval_eligible ? "eligible for content review" : "not eligible for new content review"}. {isEditing ? "Save or discard local edits before reviewing. " : ""}Final PDF approval is separate.</p>
    {view.source_problem ? <p className="text-sm text-warning-foreground">{view.source_problem} Historical drafts and review records remain available.</p> : null}
    {view.approval ? <p className="text-xs text-muted-foreground">Reviewed {new Date(view.approval.reviewed_at).toLocaleString()}. Approval belongs only to this saved revision.</p> : null}
    <div className="flex flex-wrap gap-2">
      {!isEditing ? <Button variant="secondary" disabled={busy || !draft.ready || revision.id !== view.current_revision_id} onClick={startEditing}>Edit resume</Button> : null}
      <Button variant={isEditing ? "secondary" : "primary"} disabled={busy || refreshing || isEditing || !draft.ready || !view.approval_eligible || view.approved_current} onClick={() => review.mutate()}>{review.isPending ? "Recording review…" : "Mark reviewed"}</Button>
      {revision.id !== view.current_revision_id ? <Button variant="secondary" disabled={busy || isEditing || !restoreRequest.ready} onClick={restoreSelected}>Restore as new revision</Button> : null}
      <Button variant="ghost" disabled={busy || refreshing} onClick={onRefresh}>Refresh resume</Button>
    </div>
    {review.error || restore.error || refreshError ? <p role="alert" className="text-sm text-destructive">{review.error?.message || restore.error?.message || refreshError}</p> : null}
    <p className="text-xs text-muted-foreground">Mark reviewed confirms the saved content and its supporting evidence. It does not approve new source facts or verify PDF layout.</p>
    <div className="grid min-w-0 items-start gap-6 xl:grid-cols-2"><div className="grid min-w-0 gap-4">
    {isEditing ? <div className="grid gap-4 rounded border border-border p-3">
      <h4 className="font-medium">Edit resume content</h4>
      <p className="text-sm">Identity, employers, titles, dates and education stay tied to approved sources. Unsupported wording can be saved, but must be corrected before review. <Link className="underline" href="/profile?tab=sources">New facts require source approval.</Link></p>
      {stale ? <div className="grid gap-2 text-sm text-warning-foreground"><p>A newer revision exists. Your edits still belong to their original parent. Compare them with the current saved preview below. A retry of an already completed save is safe.</p>
        <Button variant="secondary" disabled={busy} onClick={() => onSelect(undefined)}>Show current saved version</Button>
        <label className="flex gap-2"><input type="checkbox" checked={comparedRevision === view.current_revision_id} onChange={e => setComparedRevision(e.target.checked ? view.current_revision_id : null)} />I compared my edits with the current saved version.</label>
        <Button variant="secondary" disabled={busy || comparedRevision !== view.current_revision_id || revision.id !== view.current_revision_id} onClick={() => { draft.setValue({ ...draft.value, expected_revision_id: view.current_revision_id, request_key: crypto.randomUUID() }); setComparedRevision(null); save.reset(); }}>Keep these edits on current version</Button>
      </div> : null}
      <fieldset disabled={busy} className="grid min-w-0 gap-4">
        {edit.bullets.map((bullet, index) => <div className="grid gap-2 rounded border border-border p-3" key={`${bullet.id}-${index}`}>
          <p className="text-sm font-medium">{recordLabel(bullet.record_id)}</p>
          <Field label={`Bullet ${index + 1}`} error={revision.validation.issues.find(i => i.field_path === `bullets.${bullet.id}`)?.message}>
            <Textarea maxLength={1800} value={bullet.text} onChange={e => setBullets(edit.bullets.map((b, i) => i === index ? { ...b, text: e.target.value } : b))} />
          </Field>
          <div className="flex flex-wrap gap-2"><Button variant="ghost" disabled={!edit.bullets.slice(0, index).some(b => b.record_id === bullet.record_id)} onClick={() => moveBullet(index, -1)}>Move bullet {index + 1} up</Button><Button variant="ghost" disabled={!edit.bullets.slice(index + 1).some(b => b.record_id === bullet.record_id)} onClick={() => moveBullet(index, 1)}>Move bullet {index + 1} down</Button><Button variant="ghost" onClick={() => setBullets(edit.bullets.filter((_, i) => i !== index))}>Remove bullet {index + 1}</Button></div>
          <details><summary className="cursor-pointer text-sm">Evidence and targeted requirements for bullet {index + 1}</summary><div className="mt-2 grid gap-2 text-sm">
            {revision.content.draft.coverage && <p>Requirement links come from the saved evidence assessment and update when approved content is added.</p>}
            {bullet.evidence_ids.map(id => <blockquote className="break-words" key={id}>{view.evidence.find(c => c.id === id)?.text ?? "Unavailable approved evidence"}</blockquote>)}
            {revision.content.draft.requirements.map(r => <label className="flex items-start gap-2" key={r.id}><input type="checkbox" disabled={!!revision.content.draft.coverage} checked={bullet.requirement_ids.includes(r.id)} onChange={e => setBullets(edit.bullets.map((b, i) => i === index ? { ...b, requirement_ids: e.target.checked ? [...b.requirement_ids, r.id] : b.requirement_ids.filter(id => id !== r.id) } : b))} /><span>{r.description} — Posting: “{r.quote}”</span></label>)}
            <p className="text-xs">A requirement link records your mapping; it does not independently prove that the requirement is met.</p>
          </div></details>
        </div>)}
        {!edit.bullets.length ? <p className="text-sm">No bullets selected. You may save this work, but review requires supported content.</p> : null}
        <Field label="Add approved content"><Select value={claimId} onChange={e => setClaimId(e.target.value)}><option value="">Choose an approved claim</option>{view.evidence.filter(c => !edit.bullets.some(b => b.evidence_ids.includes(c.id))).map(c => <option key={c.id} value={c.id}>{recordLabel(c.record_id)}: {c.text.slice(0, 100)}</option>)}</Select></Field>
        <Button className="w-fit" variant="secondary" disabled={!claimId || edit.bullets.length >= 20} onClick={() => { const claim = view.evidence.find(c => c.id === claimId); if (claim) setBullets([...edit.bullets, { id: crypto.randomUUID(), record_id: claim.record_id, evidence_ids: [claim.id], requirement_ids: revision.content.draft.coverage?.filter(c => [...c.full_claim_ids, ...c.partial_claim_ids].includes(claim.id)).map(c => c.requirement_id) ?? [], text: claim.text }]); setClaimId(""); }}>Add selected claim</Button>
        {edit.project_order.length > 1 ? <div className="grid gap-2"><p className="text-sm font-medium">Project order</p>{edit.project_order.map((id, index) => <div key={id} className="flex flex-wrap items-center gap-2 text-sm"><span>{recordLabel(id)}</span>{[-1, 1].map(direction => <Button key={direction} variant="ghost" disabled={index + direction < 0 || index + direction >= edit.project_order.length} onClick={() => { const order = [...edit.project_order]; [order[index], order[index + direction]] = [order[index + direction], order[index]]; update({ ...edit, project_order: order }); }}>Move project {index + 1} {direction < 0 ? "up" : "down"}</Button>)}</div>)}</div> : null}
        <fieldset className="grid gap-2"><legend className="mb-2 text-sm font-medium">Approved skills</legend>{Array.from(skills.values()).map(skill => <label className="flex gap-2 text-sm" key={skill.name}><input type="checkbox" checked={edit.skills.some(s => s.name.toLowerCase() === skill.name.toLowerCase())} onChange={e => update({ ...edit, skills: e.target.checked ? [...edit.skills, skill] : edit.skills.filter(s => s.name.toLowerCase() !== skill.name.toLowerCase()) })} />{skill.name}</label>)}</fieldset>
      </fieldset>
      {save.error ? <p role="alert" className="text-sm text-destructive">{save.error.message} Your local edits are preserved. Refresh history before retrying if the response was lost.</p> : null}
      {draft.storageError ? <p role="alert" className="text-sm text-warning-foreground">Browser storage is unavailable. Keep this page open until your edits are saved.</p> : null}
      <div className="flex flex-wrap gap-2"><Button disabled={busy || !draft.ready || !draft.value.request_key || edit.bullets.some(b => !b.text.trim())} onClick={() => save.mutate(draft.value)}>{save.isPending ? "Saving revision…" : "Save and validate"}</Button><Button variant="ghost" disabled={busy} onClick={() => { draft.discard(); setEditing(false); setComparedRevision(null); save.reset(); }}>Discard unsaved edits</Button></div>
    </div> : null}
    {revision.validation.issues.length ? <div className="grid gap-2 text-sm"><h4 className="font-medium">Saved revision validation issues</h4><ul className="list-inside list-disc">{revision.validation.issues.map((issue, i) => <li key={i}>{issue.message}</li>)}</ul></div> : null}
    <details><summary className="cursor-pointer text-sm">Changes and factual checks</summary><div className="mt-3 grid gap-3">
      <p className="text-sm">{revision.content.advisory_review ? 'Checks cover evidence references, selected numeric boundaries and required qualifiers. Faithful paraphrases are allowed; review their meaning against the source facts.' : 'Checks compare wording with approved sources.'} Human review is required; employment facts and complete job coverage are not independently verified.</p>
      <Field label="Compare saved revision with"><Select value={comparison} onChange={e => setComparison(e.target.value)}><option value="baseline">Original generated draft</option><option value="parent">Previous revision</option><option value="source">Approved source wording</option></Select></Field>
      <ChangeList changes={comparison === "source" ? revision.content.draft.bullets.map(b => ({ field: `bullets.${b.id}`, kind: "wording", before: b.evidence_ids.map(id => view.evidence.find(c => c.id === id)?.text ?? "Unavailable approved evidence").join(" "), after: b.text })).filter(c => c.before !== c.after) : comparison === "baseline" ? view.changes_from_baseline : view.changes_from_parent} />
    </div></details>
    <details><summary className="cursor-pointer text-sm">Evidence for each bullet</summary><ul className="mt-2 grid gap-3 text-sm">{revision.content.draft.bullets.map((bullet, index) => <li key={`${bullet.id}-${index}`} className="grid gap-2 rounded border border-border p-3"><p className="font-medium">{bullet.text}</p>{bullet.evidence_ids.map(id => { const evidence = view.evidence.find(c => c.id === id); return <div key={id}><p className="text-xs text-muted-foreground">Approved source {id}</p><blockquote>{evidence?.text ?? "Evidence unavailable"}</blockquote>{evidence?.constraints.map((c, i) => <p key={i} className="text-xs">{c}</p>)}</div>; })}</li>)}</ul></details>
    {revision.content.advisory_review ? <p className="text-sm">Detailed job coverage is separate from resume writing. This draft does not claim that every job requirement is met.</p> : revision.content.draft.coverage ? <section aria-label="Job requirement coverage" className="grid gap-2 text-sm">
      <h4 className="font-medium">Job requirement coverage</h4>
      <p>Coverage compares approved evidence with this saved draft. Evidence assessments need your review; omitted evidence is different from a missing qualification.</p>
      <ul className="grid gap-3">{revision.content.draft.coverage.map(c => {
        const requirement = revision.content.draft.requirements.find(r => r.id === c.requirement_id);
        const label = { supported: "Supported", partially_supported: "Partially supported", unsupported: "Unsupported", not_included: "Not included in this draft" }[c.status];
        const ids = [...c.full_claim_ids, ...c.partial_claim_ids];
        return <li key={c.requirement_id} className="rounded border border-border p-3">
          <p><strong>{label}</strong>: {requirement?.description}</p>
          <p className="text-muted-foreground">Posting: <q>{requirement?.quote}</q></p>
          <p>{c.explanation}</p>
          {c.status === "not_included" && <p>Available evidence: {c.available_support === "full" ? "full support" : "partial support"}. Add relevant approved content if appropriate.</p>}
          {!!c.selected_skill_names.length && <p>Supported by selected skills: {c.selected_skill_names.join(", ")}.</p>}
          {!!ids.length && <details><summary>Supporting experience</summary>{ids.map(id => <p key={id}>{c.full_claim_ids.includes(id) ? "Full" : "Partial"} support: {view.evidence.find(e => e.id === id)?.text ?? id}</p>)}</details>}
          {!!c.skill_source_ids.length && <p>Approved skill evidence: {c.skill_source_ids.map(id => view.technology_catalog.find(t => t.id === id)?.name ?? view.skill_groups.find(g => g.id === id)?.values.join(", ") ?? id).join("; ")}.</p>}
        </li>;
      })}</ul>
    </section> : <div className="text-sm"><strong>Unmet job requirements</strong>{revision.content.draft.unmet_requirement_ids.length ? <ul className="mt-1 list-inside list-disc">{revision.content.draft.requirements.filter(r => revision.content.draft.unmet_requirement_ids.includes(r.id)).map(r => <li key={r.id}>{r.description} — Posting: “{r.quote}”</li>)}</ul> : <p>No additional gaps in this revision’s requirement mapping; check it against the full posting.</p>}</div> }
    </div><SavedTextPreview kind="resume" text={revision.plain_text} revision={revision.sequence === 0 ? "Original generated draft" : `Revision ${revision.sequence}`} historical={revision.id !== view.current_revision_id} unsaved={isEditing} /></div>
    </Panel>
    <ResumeExports key={revision.id} view={view} disabled={isEditing || busy || !draft.ready || refreshing} />
  </section>;
}

function ChangeList({ changes }: { changes: ResumeChange[] }) {
  const display = (value: unknown): string => {
    if (value === null || value === undefined) return "Not present";
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.map(display).join(", ") || "None";
    if (typeof value === "object") { const v = value as { text?: string; name?: string }; return v.text ?? v.name ?? JSON.stringify(value); }
    return String(value);
  };
  if (!changes.length) return <p className="text-sm">No content changes from this comparison version.</p>;
  return <ul className="grid gap-3 text-sm">{changes.map((change, i) => <li key={i} className="grid min-w-0 gap-2 rounded border border-border p-3"><p className="font-medium">{change.kind}: {change.field.startsWith("bullets.") ? "Resume bullet" : change.field.replaceAll("_", " ")}</p><div className="grid gap-3 sm:grid-cols-2"><div className="min-w-0"><strong>Before</strong><p className="whitespace-pre-wrap break-words">{display(change.before)}</p></div><div className="min-w-0"><strong>After</strong><p className="whitespace-pre-wrap break-words">{display(change.after)}</p></div></div></li>)}</ul>;
}
