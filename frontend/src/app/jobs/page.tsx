"use client";

import { validateJobFields } from "@/lib/job-validation";
import { IntakeDecisions } from "@/components/intake-review";
import type { IntakeFacts, IntakeFactKey } from "@/lib/intake-types";
import { useConfirm } from "@/components/ui/confirm-provider";

import { keepPreviousData, useMutation, useMutationState, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ExternalLink, FileText, Plus, Save, Search, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useDraft } from "@/lib/use-draft";
import { isIntakeDraft, isIntakeReviewDraft } from "@/lib/intake-draft";
import { DraftRecovery } from "@/components/draft-recovery";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ListEditor } from "@/components/ui/list-editor";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import {
  jobCategories,
  jobStatuses,
  remoteTypes,
  type JobCategory,
  type JobCreatePayload,
  type JobExtractPreview,
  type JobLinkInput,
  type JobListItem,
  type JobStatus,
  type RemoteType
} from "@/lib/types";
import { formatDate } from "@/lib/utils";

type IntakeState = {
  source_url: string;
  source_content: string;
};

type ReviewState = JobCreatePayload & {
  duplicateCount: number;
  facts?: IntakeFacts;
  sourceInput?: IntakeState;
  fullDescriptionReviewed?: boolean;
};

const healthLabels: Record<string, string> = { active: "Active opportunities", stale: "Stale", "missing-data": "Missing data", "needs-analysis": "Needs analysis", "missing-pay": "Missing pay", "missing-fit": "Missing fit", "low-confidence": "Low confidence" };
type HealthFilter = string;

const linkKindLabels: Record<JobLinkInput["kind"], string> = {
  source: "Job Posting",
  company_portal: "Company Careers",
  application_portal: "Application Portal",
  recruiter: "Recruiter/Contact",
  company_info: "Company Info",
  custom: "Custom"
};

const defaultLinks: JobLinkInput[] = [
  { kind: "source", label: "Job Posting", url: "" }
];

const editableLinkKinds: JobLinkInput["kind"][] = [
  "source",
  "application_portal",
  "company_portal",
  "recruiter",
  "company_info",
  "custom"
];

function statusFromUrl(value: string | null): JobStatus | "" {
  if (!value) return "";
  return (jobStatuses as readonly string[]).includes(value) ? (value as JobStatus) : "";
}

function healthFromUrl(value: string | null): HealthFilter {
  if (value && value in healthLabels) return value;
  return "";
}

function toApiHealthFilter(value: HealthFilter) { return value.replaceAll("-", "_"); }

function isHiddenStatus(status: JobStatus | "") {
  return status === "Archived" || status === "Ghosted" || status === "Rejected";
}

export default function JobsPage() {
  return <Suspense fallback={<Panel>Loading tracker...</Panel>}><JobsContent /></Suspense>;
}
function JobsContent() {
  const router = useRouter();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const setFilter = (updates: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(updates)) value ? next.set(key, value) : next.delete(key);
    window.history.replaceState(null, "", `/jobs${next.size ? `?${next}` : ""}`);
  };
  const search = params.get("search") ?? "";
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(search), 250); return () => window.clearTimeout(timer); }, [search]);
  const pendingJobIds = useMutationState({ filters: { mutationKey: ["jobs-write"], status: "pending" }, select: mutation => (mutation.state.variables as { id: string }).id });
  const statusFilter = statusFromUrl(params.get("status"));
  const healthFilter = healthFromUrl(params.get("health"));
  const categoryFilter = params.get("category") as JobCategory | "" || "";
  const savedSince = params.get("since") ?? "";
  const funnelStage = params.get("funnel") ?? "";
  const funnelStopped = params.get("stopped") === "true";
  const funnelFrom = params.get("from") ?? "";
  const showHidden = params.get("hidden") === "true" || isHiddenStatus(statusFilter) || Boolean(funnelStage);
  const sort = params.get("sort") ?? "updated";
  const [showIntake, setShowIntake] = useState(false);
  const [savedJob, setSavedJob] = useState<{ id: string; company: string } | null>(null);
  const returnTo = `/jobs${params.size ? `?${params}` : ""}`;
  const [selectedJob, setSelectedJob] = useState<JobListItem | null>(null);
  const [sourceOpen, setSourceOpen] = useState(true);
  const intakeDraft = useDraft<IntakeState>("job-intake", { source_url: "", source_content: "" }, isIntakeDraft);
  const { value: intake, setValue: setIntake } = intakeDraft;
  const reviewDraft = useDraft<ReviewState | null>("job-review", null, isIntakeReviewDraft);
  const { value: review, setValue: setReview } = reviewDraft;
  const hasReview = Boolean(review);
  useEffect(() => { setSourceOpen(!hasReview); }, [hasReview]);

  const { data: rawJobs = [], isLoading, error, isFetching, refetch } = useQuery({
    queryKey: ["jobs", showHidden, debouncedSearch, statusFilter, healthFilter, categoryFilter, funnelStage, funnelFrom, savedSince, funnelStopped],
    queryFn: () => api.jobs({ includeArchived: showHidden, search: debouncedSearch.trim() || undefined, status: statusFilter, category: categoryFilter, healthFilter: toApiHealthFilter(healthFilter), funnelStage, funnelFrom, savedSince, funnelStopped }),
    placeholderData: keepPreviousData
  });
  const jobs = [...rawJobs].sort((a, b) => sort === "company" ? a.company.localeCompare(b.company) : sort === "pay" ? (a.pay_currency ?? "Unknown").localeCompare(b.pay_currency ?? "Unknown") || (b.pay_annual_max ?? b.pay_annual_min ?? -1) - (a.pay_annual_max ?? a.pay_annual_min ?? -1) : Date.parse(b.updated_at) - Date.parse(a.updated_at));
  const extractMutation = useMutation({
    mutationFn: api.extractJobPreview,
    onSuccess: (data) => {
      setReview({ ...reviewFromPreview(data), facts: data.preference_facts, sourceInput: { ...intake }, fullDescriptionReviewed: false });
    }
  });

  const createMutation = useMutation({
    mutationFn: api.saveIntake,
    onSuccess: (job, variables) => {
      setSavedJob(job);
      setShowIntake(false);
      setIntake({ source_url: "", source_content: "" });
      setReview(null);
      intakeDraft.clear();
      reviewDraft.clear();
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      window.scrollTo({ top: 0, behavior: "smooth" });
      if (variables.decision === "continue") router.push(`/jobs/${job.id}?tailoring=prepare#tailoring-preparation`);
    }
  });

  const updateMutation = useMutation({
    mutationKey: ["jobs-write"],
    mutationFn: ({ id, payload }: { id: string; payload: Partial<JobCreatePayload> & { status?: JobStatus } }) => api.updateJob(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const archiveMutation = useMutation({
    mutationKey: ["jobs-write"],
    mutationFn: (id: string) => api.updateJob(id, { status: "Archived" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const startManualFallback = () => {
    setReview({ ...blankReview(intake), facts: {}, sourceInput: { ...intake }, fullDescriptionReviewed: false });
    createMutation.reset();
  };

  const discardIntake = () => {
    intakeDraft.discard(); reviewDraft.discard();
    extractMutation.reset(); createMutation.reset(); setShowIntake(false);
  };
  const changeReview = (next: ReviewState) => {
    const facts = { ...next.facts };
    const invalidate = (...keys: IntakeFactKey[]) => keys.forEach(key => { facts[key] = { value: null, origin: "unknown", quote: "" }; });
    if (review) {
      if (["pay_min", "pay_max", "pay_currency", "pay_period", "pay_raw"].some(key => review[key as keyof ReviewState] !== next[key as keyof ReviewState])) invalidate("salary_component", "salary_band");
      if (review.location !== next.location || review.remote_type !== next.remote_type) invalidate("nyc_compatible", "salary_band");
      if (review.role_title !== next.role_title) invalidate("role_family");
      if (review.company !== next.company) invalidate("employer_source", "company_stage", "employee_count", "hours_week");
      if (JSON.stringify(review.links) !== JSON.stringify(next.links)) invalidate("employer_source");
    }
    setReview({ ...next, facts });
  };

  const changeStatusFilter = (status: JobStatus | "") => setFilter({ status, hidden: isHiddenStatus(status) ? "true" : params.get("hidden") ?? "" });
  const changeShowHidden = (value: boolean) => setFilter({ hidden: value ? "true" : "", status: !value && isHiddenStatus(statusFilter) ? "" : statusFilter, funnel: "", from: "", stopped: "" });

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Job Tracker"
        action={<Button onClick={() => setShowIntake(!showIntake)} aria-expanded={showIntake} aria-controls="job-intake"><Plus className="h-4 w-4" />{showIntake ? "Hide add job" : "Add job"}</Button>}
      />

      {savedJob ? <Panel className="text-sm"><div role="status">Saved {savedJob.company}. <Link className="font-semibold underline" href={`/jobs/${savedJob.id}`}>Open saved job</Link></div></Panel> : null}
      <div className="grid min-w-0 gap-4">
        <section id="job-intake" hidden={!showIntake}><Panel>
          <DraftRecovery name="job intake" draft={intakeDraft} />
          <DraftRecovery name="job review" draft={reviewDraft} />
          <fieldset disabled={!intakeDraft.ready || !reviewDraft.ready || extractMutation.isPending || createMutation.isPending} className="min-w-0">
          <div className="mb-5 grid gap-1">
            <h2 className="text-lg font-semibold">Add job</h2>
            {!review ? <p className="text-sm text-muted-foreground">Paste a posting, add a URL, or enter manually.</p> : null}
          </div>

          {(intakeDraft.dirty || reviewDraft.dirty) ? <p role="status" className="mb-4 text-xs text-muted-foreground">Draft kept on this browser, including after refresh or closing the tab.</p> : null}
          <details open={sourceOpen} onToggle={event => setSourceOpen(event.currentTarget.open)} className={review ? "rounded-md border border-border p-3" : ""}>
          <summary className="cursor-pointer text-sm font-medium">Posting source and extraction</summary>
          <div className="mt-4 grid gap-4">
            <div className="grid items-start gap-4 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <Field label="Job URL">
              <Input
                value={intake.source_url}
                onChange={(event) => setIntake((current) => ({ ...current, source_url: event.target.value }))}
                placeholder="https://..."
              />
            </Field>
            <Field label="Pasted page content">
              <Textarea
                value={intake.source_content}
                onChange={(event) => setIntake((current) => ({ ...current, source_content: event.target.value }))}
                className="min-h-28"
                placeholder="Paste the job description or full job page text."
              />
            </Field>
            </div>
            {extractMutation.error ? (
              <div className="rounded-md border border-warning-foreground/20 bg-warning p-3 text-sm text-warning-foreground">
                <div>{(extractMutation.error as Error).message}</div>
                <Button className="mt-3" size="sm" variant="secondary" onClick={async () => { if (!review || await confirm("Replace the current review with a blank manual entry?")) startManualFallback(); }}>
                  Use manual fallback
                </Button>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={async () => { if (review && !await confirm("Replace the current review with newly extracted fields?")) return;
                  extractMutation.mutate({
                    source_url: intake.source_url || null,
                    source_content: intake.source_content || null
                  }); }}
                disabled={extractMutation.isPending || (!intake.source_url.trim() && !intake.source_content.trim())}
              >
                <Sparkles className="h-4 w-4" />
                {extractMutation.isPending ? "Extracting..." : "Extract fields"}
              </Button>
              <Button variant="secondary" onClick={async () => { if (!review || await confirm("Replace the current review with a blank manual entry?")) startManualFallback(); }}>
                Manual entry
              </Button>
            </div>
            {extractMutation.isPending ? <p role="status" className="text-sm">Extracting job basics. Your source text stays in this draft.</p> : null}
            {!review ? <Button variant="ghost" className="w-fit" onClick={discardIntake}>Not pursuing</Button> : null}
          </div>
          </details>

          {review ? (
            <div className="mt-6">
              <IntakeDecisions review={{ job: cleanReview(review, intake.source_url), facts: review.facts ?? {}, full_description_reviewed: review.fullDescriptionReviewed ?? false }}
                valid={!Object.keys(validateJobFields(review)).length && Boolean(review.company.trim() && review.role_title.trim())}
                stale={JSON.stringify(review.sourceInput) !== JSON.stringify(intake)} busy={createMutation.isPending} error={createMutation.error}
                onFacts={facts => setReview({ ...review, facts })} onReviewed={fullDescriptionReviewed => setReview({ ...review, fullDescriptionReviewed })}
                onSave={payload => createMutation.mutate(payload)} onDiscard={discardIntake}>
                {actions => <ReviewEditor review={review} onChange={changeReview} actions={actions} />}
              </IntakeDecisions>
            </div>
          ) : null}
        </fieldset></Panel></section>

        <Panel className="min-w-0 overflow-hidden">
          <div className="mb-4 grid gap-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-semibold">{funnelStage ? funnelStopped ? `Jobs with no later stage after ${funnelStage}` : funnelFrom ? `Jobs ${funnelStage.toLowerCase()} after ${funnelFrom}` : `Jobs that ${["Rejected", "Withdrawn", "Ghosted"].includes(funnelStage) ? "ended as" : "reached"} ${funnelStage}` : "Applications"}</h2>
                <Badge>{jobs.length} shown</Badge>
              </div>
              {funnelStage ? <p className="text-sm text-muted-foreground">{funnelStopped ? "Historical cohort · excludes closed and archived jobs" : "Historical cohort · includes closed outcomes · excludes archived jobs"}</p> : <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border text-primary"
                  checked={showHidden}
                  onChange={(event) => changeShowHidden(event.target.checked)}
                />
                Include archived, rejected & ghosted
              </label>}
            </div>
            <div className="grid gap-2 sm:grid-cols-2 2xl:grid-cols-[minmax(180px,1fr)_180px_190px_220px]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(event) => setFilter({ search: event.target.value })}
                  className="pl-9"
                  aria-label="Search jobs" placeholder="Search company, role, notes..."
                />
              </div>
              <Select aria-label="Current status" value={statusFilter} onChange={(event) => changeStatusFilter(event.target.value as JobStatus | "")}>
                <option value="">Any current status</option>
                {jobStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </Select>
              <Select aria-label="Job health" value={healthFilter} onChange={(event) => setFilter({ health: event.target.value })}>
                <option value="">All health</option>
                {Object.entries(healthLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </Select>
              <Select aria-label="Job category" value={categoryFilter} onChange={(event) => setFilter({ category: event.target.value })}>
                <option value="">All categories</option>
                {jobCategories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          {funnelStopped ? <p className="mb-3 text-sm text-muted-foreground">Furthest recorded stage, including inferred progression; excludes closed and archived jobs. Current status may have moved back.</p> : null}
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
            {funnelStage ? <Badge>{funnelStopped ? `No later stage after ${funnelStage}` : funnelFrom ? `${funnelFrom} → ${funnelStage}` : `Reached ${funnelStage}`} · excludes archived</Badge> : null}
            {[...params.entries()].filter(([key]) => ["search", "status", "health", "category", "funnel", "since"].includes(key)).map(([key, value]) => <button key={key} className="rounded-full border border-border px-3 py-1" onClick={() => setFilter(key === "funnel" ? { funnel: "", from: "", stopped: "", hidden: "" } : { [key]: "" })} aria-label={`Remove ${key} filter`}>{key === "since" ? `Saved since ${value} (UTC)` : healthLabels[value] ?? value} ×</button>)}
            {[...params.keys()].some(key => key !== "sort") ? <Button variant="ghost" size="sm" onClick={() => window.history.replaceState(null, "", `/jobs${sort !== "updated" ? `?sort=${encodeURIComponent(sort)}` : ""}`)}>Clear filters</Button> : null}
            <label className="ml-auto flex items-center gap-2 whitespace-nowrap">Sort by <Select aria-label="Sort jobs" value={sort} onChange={event => setFilter({ sort: event.target.value })}><option value="updated">Recently updated</option><option value="company">Company A–Z</option><option value="pay">Pay by currency, highest first</option></Select></label>
          </div>
          {updateMutation.error || archiveMutation.error ? <p role="alert" className="mb-3 text-sm text-destructive">Could not save: {((updateMutation.error || archiveMutation.error) as Error).message}. Your previous saved values are shown; try again.</p> : null}
          <p role="status" className="mb-2 text-xs text-muted-foreground">{isFetching || search !== debouncedSearch ? "Updating results… Previous results remain visible." : `${jobs.length} jobs shown`}{sort === "pay" ? " · Grouped by currency; no exchange-rate conversion." : ""}</p>
          {error ? <div role="alert"><p className="text-sm text-destructive">{(error as Error).message}</p><Button variant="secondary" onClick={() => refetch()}>Retry loading jobs</Button></div> : null}
          {isLoading ? <p className="text-sm text-muted-foreground">Loading jobs...</p> : null}
          <div className="grid gap-3 md:grid-cols-2 2xl:hidden">
            {jobs.map(job => <article key={job.id} className="grid min-w-0 gap-3 rounded-md border border-border p-3">
              <div><div className="text-sm font-semibold">{job.company}</div><Link className="font-medium text-primary underline" href={`/jobs/${job.id}?returnTo=${encodeURIComponent(returnTo)}`}>{job.role_title}</Link></div>
              <div className="flex flex-wrap gap-2"><Badge>{job.remote_type}</Badge></div>
              <label className="grid gap-1 text-sm">Category<Select aria-label={`Category for ${job.company} ${job.role_title}`} value={job.category} disabled={pendingJobIds.includes(job.id)} onChange={event => updateMutation.mutate({ id: job.id, payload: { category: event.target.value as JobCategory } })}>{jobCategories.map(category => <option key={category} value={category}>{category}</option>)}</Select></label>
              {job.links[0] ? <a className="text-sm text-primary underline" href={(job.links.find(link => link.kind === "source") ?? job.links[0]).url} target="_blank" rel="noreferrer">Open job posting</a> : null}
              <p className="text-sm text-muted-foreground">{job.location || "Location not listed"}</p>
              <label className="grid gap-1 text-sm">Status<Select aria-label={`Status for ${job.company} ${job.role_title}`} value={job.status} disabled={pendingJobIds.includes(job.id)} onChange={event => updateMutation.mutate({ id: job.id, payload: { status: event.target.value as JobStatus } })}>{jobStatuses.map(status => <option key={status} value={status}>{status}</option>)}</Select></label>
              <PayEditor job={job} disabled={pendingJobIds.includes(job.id)} onSave={payload => updateMutation.mutateAsync({ id: job.id, payload })} />
              <div className="flex items-center justify-between gap-2"><span className="text-xs text-muted-foreground">Updated {formatDate(job.updated_at)}</span><Button size="sm" variant="secondary" onClick={() => setSelectedJob(job)}>Preview</Button></div>
            </article>)}
            {!jobs.length && !isLoading && !error ? <p className="py-6 text-sm">No jobs match. Clear filters or add a job.</p> : null}
          </div>
          <div className="hidden overflow-x-auto 2xl:block">
            <table className="w-full min-w-[1050px] text-left text-sm">
              <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4">Company</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="min-w-44 py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Location</th>
                  <th className="py-2 pr-4">Pay</th>
                  <th className="py-2 pr-4">Source</th>
                  <th className="py-2 pr-4">Updated</th>
                  <th className="py-2 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <JobRow
                    key={job.id}
                    job={job}
                    returnTo={returnTo}
                    busy={pendingJobIds.includes(job.id)}
                    onSelect={() => setSelectedJob(job)}
                    onStatus={(nextStatus) => updateMutation.mutate({ id: job.id, payload: { status: nextStatus } })}
                    onCategory={(nextCategory) => updateMutation.mutate({ id: job.id, payload: { category: nextCategory } })}
                    onPay={(payload) => updateMutation.mutateAsync({ id: job.id, payload })}
                    onArchive={() => archiveMutation.mutate(job.id)}
                  />
                ))}
              </tbody>
            </table>
            {!jobs.length && !isLoading && !error ? <p className="py-8 text-sm text-muted-foreground">No jobs match the current filters.</p> : null}
          </div>
        </Panel>
      </div>

      {selectedJob ? <JobDrawer job={selectedJob} returnTo={returnTo} onClose={() => setSelectedJob(null)} /> : null}
    </div>
  );
}

function reviewFromPreview(preview: JobExtractPreview): ReviewState {
  return {
    company: preview.company,
    role_title: preview.role_title,
    category: preview.category,
    location: preview.location,
    remote_type: preview.remote_type,
    summary: preview.summary,
    responsibilities: preview.responsibilities,
    required_skills: preview.required_skills,
    pay_min: preview.pay_min,
    pay_max: preview.pay_max,
    pay_currency: preview.pay_currency,
    pay_period: preview.pay_period,
    pay_raw: preview.pay_raw,
    benefits: preview.benefits,
    source_content: preview.source_content,
    links: mergeLinks(preview.links, preview.source_url),
    status: "Saved",
    status_note: null,
    notes: null,
    extraction_confidence: preview.confidence,
    extraction_warnings: preview.warnings,
    duplicateCount: preview.duplicate_candidates.length
  };
}

function blankReview(intake: IntakeState): ReviewState {
  return {
    company: "",
    role_title: "",
    category: "Other",
    location: null,
    remote_type: "Unknown",
    summary: "",
    responsibilities: [],
    required_skills: [],
    pay_min: null,
    pay_max: null,
    pay_currency: null,
    pay_period: "unknown",
    pay_raw: null,
    benefits: [],
    source_content: intake.source_content,
    links: mergeLinks([], intake.source_url || null),
    status: "Saved",
    status_note: null,
    notes: null,
    extraction_confidence: null,
    extraction_warnings: ["Manual fallback was used."],
    duplicateCount: 0
  };
}

function mergeLinks(links: JobLinkInput[], sourceUrl: string | null): JobLinkInput[] {
  const rows = defaultLinks.map((row) => ({ ...row }));
  for (const link of links) {
    const index = rows.findIndex((row) => row.kind === link.kind && !row.url);
    if (index >= 0) rows[index] = { ...link };
    else rows.push({ ...link });
  }
  if (sourceUrl && !rows.some((row) => row.url.trim().toLowerCase() === sourceUrl.trim().toLowerCase())) {
    rows[0] = { kind: "source", label: "Job Posting", url: sourceUrl };
  }
  return rows;
}

function cleanReview(review: ReviewState, fallbackSourceUrl: string): JobCreatePayload {
  const links = review.links
    .map((link) => ({ ...link, label: link.label.trim() || linkKindLabels[link.kind], url: link.url.trim() }))
    .filter((link) => link.url);
  if (fallbackSourceUrl && !links.some((link) => link.url.toLowerCase() === fallbackSourceUrl.trim().toLowerCase())) {
    links.unshift({ kind: "source", label: "Job Posting", url: fallbackSourceUrl.trim() });
  }
  return {
    company: review.company.trim(),
    role_title: review.role_title.trim(),
    category: review.category,
    location: review.location?.trim() || null,
    remote_type: review.remote_type,
    summary: review.summary?.trim() || null,
    pay_min: review.pay_min,
    pay_max: review.pay_max,
    pay_currency: review.pay_currency?.trim() || null,
    pay_period: review.pay_period,
    pay_raw: review.pay_raw?.trim() || null,
    benefits: review.benefits ?? [],
    source_content: review.source_content,
    responsibilities: review.responsibilities.map((item) => item.trim()).filter(Boolean),
    required_skills: review.required_skills.map((item) => item.trim()).filter(Boolean),
    links,
    status: "Saved",
    status_note: review.status_note,
    notes: review.notes?.trim() || null,
    extraction_confidence: review.extraction_confidence,
    extraction_warnings: review.extraction_warnings
  };
}

function ReviewEditor({
  review,
  onChange,
  actions
}: {
  review: ReviewState;
  onChange: (next: ReviewState) => void;
  actions: ReactNode;
}) {
  const errors = validateJobFields(review);
  const payInvalid = Boolean(errors.pay_min || errors.pay_max);
  const linksInvalid = Object.keys(errors).some(key => key.startsWith("link_"));
  const [payOpen, setPayOpen] = useState(payInvalid);
  const [linksOpen, setLinksOpen] = useState(linksInvalid);
  useEffect(() => { if (payInvalid) setPayOpen(true); }, [payInvalid]);
  useEffect(() => { if (linksInvalid) setLinksOpen(true); }, [linksInvalid]);
  const set = <K extends keyof ReviewState>(key: K, value: ReviewState[K]) => onChange({ ...review, [key]: value });
  const setLink = (index: number, patch: Partial<JobLinkInput>) => {
    const nextPatch = patch.kind ? { ...patch, label: patch.label ?? linkKindLabels[patch.kind] } : patch;
    const links = review.links.map((link, currentIndex) => (currentIndex === index ? { ...link, ...nextPatch } : link));
    onChange({ ...review, links });
  };
  const removeLink = (index: number) => {
    onChange({ ...review, links: review.links.filter((_link, currentIndex) => currentIndex !== index) });
  };

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">Job basics</h3>
        <Badge tone={review.extraction_confidence && review.extraction_confidence >= 80 ? "good" : "warn"}>
          Confidence {review.extraction_confidence ?? "manual"}
        </Badge>
      </div>
      {(review.extraction_warnings ?? []).length ? (
        <details className="text-sm"><summary className="cursor-pointer font-medium text-warning-foreground">Extraction notes ({review.extraction_warnings!.length})</summary><div className="mt-2 grid gap-1 text-xs text-warning-foreground">
          {(review.extraction_warnings ?? []).map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div></details>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Company">
          <Input value={review.company} onChange={(event) => set("company", event.target.value)} />
        </Field>
        <Field label="Role title">
          <Input value={review.role_title} onChange={(event) => set("role_title", event.target.value)} />
        </Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Category">
          <Select value={review.category} onChange={(event) => set("category", event.target.value as JobCategory)}>
            {jobCategories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Remote">
          <Select value={review.remote_type ?? "Unknown"} onChange={(event) => set("remote_type", event.target.value as RemoteType)}>
            {remoteTypes.map((remoteType) => (
              <option key={remoteType} value={remoteType}>
                {remoteType}
              </option>
            ))}
          </Select>
        </Field>
      <Field label="Location">
        <Input value={review.location ?? ""} onChange={(event) => set("location", event.target.value)} />
      </Field>
      </div>
      <details open={payOpen} onToggle={event => setPayOpen(event.currentTarget.open)} className="border-t border-border pt-3"><summary className="cursor-pointer text-sm"><span className="font-medium">Pay</span><span className="ml-2 text-muted-foreground">{formatPay({ pay_min: review.pay_min ?? null, pay_max: review.pay_max ?? null, pay_currency: review.pay_currency ?? null, pay_period: review.pay_period ?? null, pay_raw: review.pay_raw ?? null })}</span>{payInvalid ? <span className="ml-2 text-destructive">Corrections needed</span> : null}</summary><div className="mt-3 grid gap-4">
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Pay minimum" error={errors.pay_min}>
          <Input type="number" min={0} value={review.pay_min ?? ""} onChange={(event) => set("pay_min", event.target.value ? Number(event.target.value) : null)} />
        </Field>
        <Field label="Pay maximum" error={errors.pay_max}>
          <Input type="number" min={0} value={review.pay_max ?? ""} onChange={(event) => set("pay_max", event.target.value ? Number(event.target.value) : null)} />
        </Field>
        <Field label="Pay currency">
          <Input value={review.pay_currency ?? ""} onChange={(event) => set("pay_currency", event.target.value)} placeholder="USD" />
        </Field>
        <Field label="Pay period">
          <Select value={review.pay_period ?? "unknown"} onChange={(event) => set("pay_period", event.target.value)}>
            {["unknown", "hour", "day", "week", "month", "year", "contract"].map((period) => (
              <option key={period} value={period}>
                {period}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Raw pay text">
        <Input value={review.pay_raw ?? ""} onChange={(event) => set("pay_raw", event.target.value)} placeholder="$120k-$160k, equity, bonus..." />
      </Field>
      </div></details>
      {actions}
      <Field label="Summary">
        <Textarea value={review.summary ?? ""} onChange={(event) => set("summary", event.target.value)} />
      </Field>
      <details className="border-t border-border pt-3"><summary className="cursor-pointer text-sm font-medium">Additional job details</summary><div className="mt-3 grid gap-4">
      <ListEditor label="Main responsibilities" value={review.responsibilities ?? []} onChange={value => set("responsibilities", value)} />
      <ListEditor label="Skills" value={review.required_skills ?? []} onChange={value => set("required_skills", value)} />
      <ListEditor label="Benefits" value={review.benefits ?? []} onChange={value => set("benefits", value)} />
      <Field label="Notes">
        <Textarea value={review.notes ?? ""} onChange={(event) => set("notes", event.target.value)} />
      </Field>
      </div></details>
      <details open={linksOpen} onToggle={event => setLinksOpen(event.currentTarget.open)} className="border-t border-border pt-3"><summary className="cursor-pointer text-sm font-medium">Posting and other links ({review.links.length}){linksInvalid ? <span className="ml-2 text-destructive">Corrections needed</span> : null}</summary><div className="mt-3">
      <div className="grid gap-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-medium">Links</div>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onChange({ ...review, links: [...review.links, { kind: "source", label: "Job Posting", url: "" }] })}
          >
            Add link
          </Button>
        </div>
        {review.links.map((link, index) => (
          <div key={`${link.kind}-${index}`} className="grid gap-2 sm:grid-cols-[100px_minmax(0,0.7fr)_minmax(0,1fr)_36px]">
            <Select aria-label={`Link ${index + 1} type`} value={link.kind} onChange={(event) => setLink(index, { kind: event.target.value as JobLinkInput["kind"] })}>
              {editableLinkKinds.map((kind) => (
                <option key={kind} value={kind}>
                  {linkKindLabels[kind]}
                </option>
              ))}
            </Select>
            <Input aria-label={`Link ${index + 1} label`} value={link.label} onChange={(event) => setLink(index, { label: event.target.value })} />
            <Field label={`Link ${index + 1} URL`} error={errors[`link_${index}`]}><Input type="url" value={link.url} onChange={(event) => setLink(index, { url: event.target.value })} placeholder="https://..." /></Field>
            <Button variant="ghost" size="icon" onClick={() => removeLink(index)} title="Remove link">
              <X className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>
      </div></details>
    </div>
  );
}

function JobRow({
  job,
  onStatus,
  onCategory,
  onPay,
  onArchive,
  onSelect,
  returnTo,
  busy
}: {
  job: JobListItem;
  onStatus: (status: JobStatus) => void;
  onCategory: (category: JobCategory) => void;
  onPay: (payload: Partial<JobCreatePayload>) => Promise<unknown>;
  onArchive: () => void;
  onSelect: () => void;
  returnTo: string;
  busy: boolean;
}) {
  const confirm = useConfirm();
  const source = job.links.find((link) => link.kind === "source") ?? job.links[0];
  return (
    <tr className="border-b border-border last:border-0">
      <td className="min-w-36 py-3 pr-4 align-top font-medium">{job.company}</td>
      <td className="min-w-52 py-3 pr-4 align-top">
        <Link className="font-medium text-primary underline-offset-2 hover:underline" href={`/jobs/${job.id}?returnTo=${encodeURIComponent(returnTo)}`}>{job.role_title}</Link>
        {busy ? <span role="status" className="block text-xs">Saving...</span> : null}
        {job.summary ? <div className="mt-1 line-clamp-2 max-w-[300px] text-xs text-muted-foreground">{job.summary}</div> : null}
      </td>
      <td className="py-3 pr-4 align-top">
        <Select disabled={busy} aria-label={`Category for ${job.company} ${job.role_title}`} value={job.category} onChange={(event) => onCategory(event.target.value as JobCategory)} className="min-w-48">
          {jobCategories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </Select>
      </td>
      <td className="py-3 pr-4 align-top">
        <Select disabled={busy} aria-label={`Status for ${job.company} ${job.role_title}`} value={job.status} onChange={(event) => onStatus(event.target.value as JobStatus)} className="min-w-44">
          {jobStatuses.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
      </td>
      <td className="py-3 pr-4 align-top text-muted-foreground">
        <div>{job.location || "Unknown"}</div>
        <div className="text-xs">{job.remote_type || "Unknown"}</div>
      </td>
      <td className="py-3 pr-4 align-top text-muted-foreground">
        <PayEditor job={job} disabled={busy} onSave={onPay} />
      </td>
      <td className="py-3 pr-4 align-top">
        {source ? (
          <a href={source.url} target="_blank" rel="noreferrer" aria-label={`Open posting for ${job.company} ${job.role_title}`} className="inline-flex h-9 w-9 items-center justify-center rounded border border-border hover:bg-accent"><ExternalLink className="h-4 w-4" /></a>
        ) : (
          <span className="text-muted-foreground">None</span>
        )}
      </td>
      <td className="py-3 pr-4 align-top text-muted-foreground">{formatDate(job.updated_at)}</td>
      <td className="py-3 pr-4 align-top">
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={onSelect}>
            Preview
          </Button>
          {job.status !== "Archived" && job.status !== "Ghosted" ? (
            <Button variant="secondary" size="icon" disabled={busy} onClick={async () => { if (await confirm(`Archive ${job.company} - ${job.role_title}? You can restore it using the status filter.`)) onArchive(); }} aria-label={`Archive ${job.company} ${job.role_title}`} title="Archive job">
              <Archive className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function PayEditor({ job, onSave, disabled = false }: { job: JobListItem; disabled?: boolean; onSave: (payload: Partial<JobCreatePayload>) => Promise<unknown> }) {
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState({
    pay_min: job.pay_min,
    pay_max: job.pay_max,
    pay_currency: job.pay_currency ?? "USD",
    pay_period: job.pay_period ?? "unknown",
    pay_raw: job.pay_raw ?? ""
  });

  useEffect(() => {
    setDraft({
      pay_min: job.pay_min,
      pay_max: job.pay_max,
      pay_currency: job.pay_currency ?? "USD",
      pay_period: job.pay_period ?? "unknown",
      pay_raw: job.pay_raw ?? ""
    });
  }, [job.pay_min, job.pay_max, job.pay_currency, job.pay_period, job.pay_raw]);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const payErrors = validateJobFields(draft);
  const save = async () => {
    if (Object.keys(payErrors).length) return;
    if (draft.pay_min !== null && draft.pay_max !== null && draft.pay_min > draft.pay_max) { setSaveError("Minimum pay must not exceed maximum pay."); return; }
    setSaving(true);
    setSaveError("");
    try { await onSave({
      pay_min: draft.pay_min,
      pay_max: draft.pay_max,
      pay_currency: draft.pay_currency.trim() || null,
      pay_period: draft.pay_period,
      pay_raw: draft.pay_raw.trim() || null
    });
    setIsOpen(false);
    } catch (error) { setSaveError((error as Error).message); } finally { setSaving(false); }
  };

  return (
    <div className="relative min-w-48">
      <button disabled={disabled} className="text-left disabled:opacity-55" onClick={() => setIsOpen((current) => !current)}>
        <div className="font-medium text-foreground">{formatPay(job)}</div>
        <div className="text-xs text-muted-foreground">{formatAnnualPay(job)}</div><span className="text-xs text-primary underline">Edit compensation</span>
      </button>
      {isOpen ? (
        <Dialog title="Edit compensation" onClose={() => { if (!saving) setIsOpen(false); }}>
          <fieldset disabled={saving} className="grid min-w-0 gap-3">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Min" error={payErrors.pay_min}>
                <Input type="number" value={draft.pay_min ?? ""} onChange={(event) => setDraft((current) => ({ ...current, pay_min: event.target.value ? Number(event.target.value) : null }))} />
              </Field>
              <Field label="Max" error={payErrors.pay_max}>
                <Input type="number" value={draft.pay_max ?? ""} onChange={(event) => setDraft((current) => ({ ...current, pay_max: event.target.value ? Number(event.target.value) : null }))} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Currency">
                <Input value={draft.pay_currency} onChange={(event) => setDraft((current) => ({ ...current, pay_currency: event.target.value }))} />
              </Field>
              <Field label="Period">
                <Select value={draft.pay_period} onChange={(event) => setDraft((current) => ({ ...current, pay_period: event.target.value }))}>
                  {["unknown", "hour", "day", "week", "month", "year", "contract"].map((period) => (
                    <option key={period} value={period}>
                      {period}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Field label="Raw pay">
              <Input value={draft.pay_raw} onChange={(event) => setDraft((current) => ({ ...current, pay_raw: event.target.value }))} />
            </Field>
            {saveError ? <p role="alert" className="text-destructive">{saveError}</p> : null}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setIsOpen(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={save} disabled={saving || Boolean(Object.keys(payErrors).length)}>
                <Save className="h-4 w-4" />
                Save
              </Button>
            </div>
          </fieldset>
        </Dialog>
      ) : null}
    </div>
  );
}

function JobDrawer({ job, onClose, returnTo }: { job: JobListItem; onClose: () => void; returnTo: string }) {
  return (
    <Dialog title={`${job.company}: ${job.role_title}`} onClose={onClose}>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge>{job.status}</Badge>
          <Badge>{job.category}</Badge>
          {job.extraction_confidence !== null ? <Badge tone={job.extraction_confidence >= 80 ? "good" : "warn"}>Confidence {job.extraction_confidence}%</Badge> : null}
        </div>
        {job.summary ? <p className="mt-4 text-sm leading-6 text-muted-foreground">{job.summary}</p> : null}
        <div className="mt-4 grid gap-3 rounded-md border border-border bg-muted/40 p-3 text-sm">
          <InfoRow label="Location" value={[job.location, job.remote_type].filter(Boolean).join(" - ") || "Unknown"} />
          <InfoRow label="Pay" value={formatPay(job)} />
          <InfoRow label="Annual" value={formatAnnualPay(job)} />
        </div>
        <Link href={`/jobs/${job.id}?returnTo=${encodeURIComponent(returnTo)}`} className="mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-md bg-primary text-sm text-primary-foreground">
            <FileText className="h-4 w-4" />
            View Full Details
        </Link>
        <DrawerList title="Responsibilities" items={job.responsibilities} />
        <DrawerList title="Required Skills" items={job.required_skills} />
        <div className="mt-5">
          <h3 className="mb-2 text-sm font-semibold">Links</h3>
          <div className="grid gap-2">
            {job.links.length ? (
              job.links.map((link) => (
                <a key={link.id} href={link.url} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
                  <span>{link.label || linkKindLabels[link.kind]}</span>
                  <ExternalLink className="h-4 w-4 text-muted-foreground" />
                </a>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No links saved.</p>
            )}
          </div>
        </div>
    </Dialog>
  );
}

function formatPay(job: { pay_min: number | null; pay_max: number | null; pay_currency: string | null; pay_period: string | null; pay_raw: string | null }) {
  if (job.pay_raw) return job.pay_raw;
  const currency = job.pay_currency ?? "USD";
  const suffix = job.pay_period && job.pay_period !== "unknown" ? ` / ${job.pay_period}` : "";
  if (job.pay_min !== null && job.pay_max !== null) return `${currency} ${job.pay_min.toLocaleString()}-${job.pay_max.toLocaleString()}${suffix}`;
  if (job.pay_min !== null) return `${currency} ${job.pay_min.toLocaleString()}+${suffix}`;
  if (job.pay_max !== null) return `Up to ${currency} ${job.pay_max.toLocaleString()}${suffix}`;
  return "Not listed";
}

function formatAnnualPay(job: { pay_annual_min: number | null; pay_annual_max: number | null; pay_currency: string | null }) {
  const currency = job.pay_currency ?? "USD";
  if (job.pay_annual_min !== null && job.pay_annual_max !== null) return `${currency} ${job.pay_annual_min.toLocaleString()}-${job.pay_annual_max.toLocaleString()} / year`;
  if (job.pay_annual_min !== null) return `${currency} ${job.pay_annual_min.toLocaleString()}+ / year`;
  if (job.pay_annual_max !== null) return `Up to ${currency} ${job.pay_annual_max.toLocaleString()} / year`;
  return "Annual not calculated";
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

function DrawerList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-5">
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      {items.length ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <Badge key={item}>{item}</Badge>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">None captured.</p>
      )}
    </div>
  );
}
