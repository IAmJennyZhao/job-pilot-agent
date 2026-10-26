"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { useDraft } from "@/lib/use-draft";
import { isRequestDraft } from "@/lib/intake-draft";
import { DraftRecovery } from "@/components/draft-recovery";
import type { IntakeEvaluation, IntakeFactKey, IntakeFacts, IntakeReview, IntakeSave } from "@/lib/intake-types";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";

const factFields: { key: IntakeFactKey; label: string; options?: string[] }[] = [
  { key: "salary_component", label: "Salary component", options: ["base", "total"] },
  { key: "salary_band", label: "Salary band applies to NYC", options: ["applicable", "unclear"] },
  { key: "nyc_compatible", label: "Can live in NYC", options: ["yes", "no"] },
  { key: "employer_source", label: "Employer/application destination", options: ["direct", "agency"] },
  { key: "required_years", label: "Minimum mandatory years" },
  { key: "preferred_years", label: "Preferred years (not mandatory)" },
  { key: "role_family", label: "Role family", options: ["software_engineer", "ai_engineer", "applied_ai_developer", "full_stack_engineer", "backend_engineer", "other"] },
  { key: "employment_type", label: "Employment type", options: ["full_time", "part_time", "contract", "internship", "other"] },
  { key: "company_stage", label: "Company stage", options: ["startup", "established"] },
  { key: "employee_count", label: "Company employee count" },
  { key: "hours_week", label: "Expected team hours per week" },
];

export function PreferenceFlags({ evaluation }: { evaluation: IntakeEvaluation }) {
  const renderFlag = (flag: IntakeEvaluation["flags"][number]) => <li key={flag.key} className="rounded-md border border-border p-3 text-sm">
    <strong className={flag.level === "red" ? "text-destructive" : flag.level === "amber" ? "text-warning-foreground" : "text-primary"}>{flag.level === "red" ? "Concern" : flag.level === "amber" ? "Check" : "Matches"}: </strong>{flag.message}
    {flag.evidence?.origin === "posting" && flag.evidence.quote ? <blockquote className="mt-1 whitespace-pre-wrap break-words text-xs text-muted-foreground">Posting: “{flag.evidence.quote}”</blockquote> : flag.evidence?.origin === "user" ? <p className="mt-1 text-xs text-muted-foreground">Your correction</p> : null}
  </li>;
  return <div className="grid gap-3" aria-label="Preference checks">
    <p className="text-sm">{evaluation.message}</p>
    {!evaluation.available ? <Link className="text-sm underline" href="/profile?tab=sources">Activate sources in Application Assets</Link> : <>
      <ul className="grid gap-2 sm:grid-cols-2">{evaluation.flags.filter(f => !f.secondary).map(renderFlag)}</ul>
      <details><summary className="cursor-pointer text-sm">Company size, stage and working hours</summary><ul className="mt-2 grid gap-2">{evaluation.flags.filter(f => f.secondary).map(renderFlag)}</ul></details>
      <p className="text-xs text-muted-foreground">Preferences: {evaluation.preference_version}</p>
    </>}
  </div>;
}

export function IntakeDecisions({ review, valid, stale, busy, error, onFacts, onReviewed, onSave, onDiscard }: {
  review: IntakeReview; valid: boolean; stale: boolean; busy: boolean; error: Error | null;
  onFacts: (facts: IntakeFacts) => void; onReviewed: (reviewed: boolean) => void;
  onSave: (payload: IntakeSave) => void; onDiscard: () => void;
}) {
  const serialized = JSON.stringify(review);
  const [debounced, setDebounced] = useState(serialized);
  useEffect(() => { const timer = setTimeout(() => setDebounced(serialized), 250); return () => clearTimeout(timer); }, [serialized]);
  const checks = useQuery({ queryKey: ["intake-evaluation", debounced], queryFn: () => api.evaluateIntake(JSON.parse(debounced)), enabled: valid && !stale && serialized === debounced, retry: false, refetchInterval: 30_000 });
  const retryDraft = useDraft<{ fingerprint: string; key: string } | null>("job-intake-save", null, isRequestDraft);
  const [allowDuplicate, setAllowDuplicate] = useState(false);
  useEffect(() => { setAllowDuplicate(false); }, [serialized]);
  const ready = valid && !stale && !busy && serialized === debounced && !checks.isFetching && !!checks.data && !checks.error && retryDraft.ready;
  const save = (decision: IntakeSave["decision"]) => {
    if (!ready || !checks.data) return;
    const payload = { ...review, decision, expected_evaluation_hash: checks.data.evaluation_hash, allow_duplicate: allowDuplicate };
    const fingerprint = JSON.stringify(payload);
    const key = retryDraft.value?.fingerprint === fingerprint ? retryDraft.value.key : crypto.randomUUID();
    retryDraft.setValue({ fingerprint, key });
    onSave({ ...payload, request_key: key });
  };
  return <div className="mt-5 grid gap-4 border-t border-border pt-5">
    <h3 className="font-semibold">Review preferences and choose your next step</h3>
    <DraftRecovery name="intake save request" draft={retryDraft} />
    {stale ? <p role="alert" className="text-sm text-warning-foreground">The source changed or this is an older draft. Extract again or start manual entry before saving.</p> : !valid ? <p className="text-sm">Enter a valid company, title, salary range and links to check preferences.</p> : checks.isFetching || serialized !== debounced ? <p role="status" className="text-sm">Checking preferences…</p> : checks.data ? <PreferenceFlags evaluation={checks.data} /> : null}
    {checks.error ? <p role="alert" className="text-sm text-destructive">{checks.error.message} <Button variant="secondary" onClick={() => checks.refetch()}>Retry checks</Button></p> : null}
    <details><summary className="cursor-pointer text-sm font-medium">Review or correct preference facts</summary>
      <p className="my-2 text-xs text-muted-foreground">Use Unknown when the posting is unclear. Corrections are recorded as your input. Direct means the hiring employer and direct application destination are confirmed.</p>
      <div className="grid gap-3 sm:grid-cols-2">{factFields.map(field => {
        const fact = review.facts[field.key];
        const change = (value: string) => onFacts({ ...review.facts, [field.key]: { value: value === "" ? null : field.options ? value : Number(value), origin: value === "" ? "unknown" : "user", quote: "" } });
        return <div key={field.key}><Field label={field.label}>
          {field.options ? <Select value={fact?.value ?? ""} onChange={e => change(e.target.value)}><option value="">Unknown</option>{field.options.map(o => <option key={o} value={o}>{o.replaceAll("_", " ")}</option>)}</Select> : <Input type="number" min={0} max={field.key === "employee_count" ? 10000000 : field.key === "hours_week" ? 168 : 80} step="any" value={fact?.value ?? ""} onChange={e => change(e.target.value)} />}
        </Field>{fact?.origin === "posting" ? <span className="text-xs text-muted-foreground">Posting: {fact.quote}</span> : fact?.origin === "user" ? <span className="text-xs text-muted-foreground">Your correction</span> : null}</div>;
      })}</div>
    </details>
    <details><summary className="cursor-pointer text-sm">Full source description</summary><pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">{review.job.source_content || "No description provided."}</pre></details>
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={review.full_description_reviewed} disabled={!review.job.source_content.trim()} onChange={e => onReviewed(e.target.checked)} />I reviewed the full job description for later tailoring.</label>
    {checks.data?.duplicate_candidates.length ? <div className="grid gap-2 rounded-md border border-border p-3 text-sm">
      <p>Possible duplicates — open the saved job to continue there:</p>
      {checks.data.duplicate_candidates.map(job => <Link className="underline" key={job.id} href={`/jobs/${job.id}`}>{job.company} — {job.role_title}</Link>)}
      <label className="flex gap-2"><input type="checkbox" checked={allowDuplicate} onChange={e => setAllowDuplicate(e.target.checked)} />This is a separate posting; save another job.</label>
    </div> : null}
    {error ? <div role="alert" className="text-sm text-destructive">{error.message} <Button variant="secondary" onClick={() => checks.refetch()}>Refresh checks</Button></div> : null}
    <div className="flex flex-wrap gap-2">
      <Button variant="ghost" disabled={busy} onClick={() => { retryDraft.discard(); onDiscard(); }}>Not pursuing</Button>
      <Button variant="secondary" disabled={!ready} onClick={() => save("save_later")}>Save for later</Button>
      <Button disabled={!ready} onClick={() => save("continue")}>{busy ? "Saving…" : "Continue to tailoring"}</Button>
    </div>
    <p className="text-xs text-muted-foreground">Both save options keep the job as Saved. Continue acknowledges the current flags and opens tailoring preparation.</p>
  </div>;
}
