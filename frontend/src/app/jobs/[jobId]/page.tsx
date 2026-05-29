"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, ExternalLink, FileText, Pencil, RefreshCw, Save, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import {
  jobCategories,
  jobStatuses,
  remoteTypes,
  type AIReadiness,
  type JobCategory,
  type JobCreatePayload,
  type JobDetail,
  type JobLinkInput,
  type JobStatus,
  type RemoteType,
  type ResumeSuggestion
} from "@/lib/types";
import { csvToList, formatDate, listToCsv } from "@/lib/utils";

type JobEditForm = Omit<JobCreatePayload, "source_content" | "extraction_confidence" | "extraction_warnings" | "status_note">;

const linkKindLabels: Record<JobLinkInput["kind"], string> = {
  source: "Source",
  company_portal: "Company portal",
  application_portal: "Application portal",
  recruiter: "Recruiter",
  custom: "Custom"
};

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState<JobEditForm | null>(null);

  const { data: job, isLoading, error } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.job(jobId),
    enabled: Boolean(jobId)
  });
  const { data: readiness, isLoading: readinessLoading, error: readinessError } = useQuery({
    queryKey: ["ai-readiness", jobId],
    queryFn: () => api.aiReadiness(jobId),
    enabled: Boolean(jobId)
  });

  useEffect(() => {
    if (job) setForm(formFromJob(job));
  }, [job]);

  const invalidateJob = () => {
    queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
    queryClient.invalidateQueries({ queryKey: ["ai-readiness", jobId] });
  };

  const updateMutation = useMutation({
    mutationFn: (values: JobEditForm) => api.updateJob(jobId, cleanForm(values)),
    onSuccess: () => {
      setIsEditing(false);
      invalidateJob();
    }
  });

  const intelligenceMutation = useMutation({
    mutationFn: () => api.runJobIntelligence(jobId),
    onSuccess: invalidateJob
  });

  const suggestMutation = useMutation({
    mutationFn: () => api.suggestResume(jobId),
    onSuccess: invalidateJob
  });

  const cancelEdit = () => {
    if (job) setForm(formFromJob(job));
    setIsEditing(false);
  };

  const latestSuggestion = job?.latest_resume_suggestion ?? null;
  const showRetryResume = Boolean(job?.analysis && !latestSuggestion && readiness?.ready);

  return (
    <div className="grid gap-6">
      <PageHeader
        title={job ? `${job.company}: ${job.role_title}` : "Job Detail"}
        description={job ? `${job.status} - Last updated ${formatDate(job.updated_at)}` : "Review source links, extracted tracker details, and application history."}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Link href="/jobs" className="text-sm font-medium text-primary">
              Back to jobs
            </Link>
            {job && !isEditing ? (
              <Button variant="secondary" size="sm" onClick={() => setIsEditing(true)}>
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
            ) : null}
          </div>
        }
      />
      {error ? <Panel className="border-rose-200 bg-rose-50 text-sm text-rose-700">{(error as Error).message}</Panel> : null}
      {isLoading ? <Panel>Loading job...</Panel> : null}

      {job ? (
        <>
          <Panel>
            {isEditing && form ? (
              <JobEditFormView
                form={form}
                onChange={setForm}
                onSubmit={() => updateMutation.mutate(form)}
                onCancel={cancelEdit}
                isSaving={updateMutation.isPending}
                error={updateMutation.error as Error | null}
              />
            ) : (
              <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
                <div>
                  <div className="flex flex-wrap gap-2">
                    <Badge>{job.status}</Badge>
                    <Badge>{job.category}</Badge>
                    {job.location ? <Badge>{job.location}</Badge> : null}
                    {job.remote_type ? <Badge>{job.remote_type}</Badge> : null}
                    {job.fit_score !== null ? <Badge tone={job.fit_score >= 75 ? "good" : job.fit_score >= 50 ? "warn" : "bad"}>Fit {job.fit_score}</Badge> : null}
                    {readiness?.model ? <Badge>{readiness.model}</Badge> : null}
                  </div>
                  {job.summary ? <p className="mt-4 text-sm leading-6 text-muted-foreground">{job.summary}</p> : null}
                  {job.notes ? <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{job.notes}</p> : null}
                </div>
                <JobIntelligenceControl
                  readiness={readiness}
                  readinessLoading={readinessLoading}
                  readinessError={readinessError as Error | null}
                  isRunning={intelligenceMutation.isPending}
                  onRun={() => intelligenceMutation.mutate()}
                />
              </div>
            )}
            {intelligenceMutation.data?.status === "partial" ? (
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                {intelligenceMutation.data.errors.join(" ")}
              </div>
            ) : null}
            {intelligenceMutation.error ? <p className="mt-3 text-sm text-destructive">{(intelligenceMutation.error as Error).message}</p> : null}
            {suggestMutation.error ? <p className="mt-3 text-sm text-destructive">{(suggestMutation.error as Error).message}</p> : null}
          </Panel>

          {!isEditing ? (
            <>
              <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
                <Panel>
                  <h2 className="text-base font-semibold">Tracker Extraction</h2>
                  <div className="mt-4 grid gap-4 text-sm">
                    <List title="Responsibilities" items={job.responsibilities} />
                    <List title="Required Skills" items={job.required_skills} />
                    {job.extraction_warnings.length ? <List title="Warnings" items={job.extraction_warnings} tone="warn" /> : null}
                  </div>
                </Panel>
                <Panel>
                  <h2 className="text-base font-semibold">Links</h2>
                  <div className="mt-4 grid gap-2">
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
                </Panel>
              </div>

              <FitOverview suggestion={latestSuggestion} />

              <div className="grid gap-4 xl:grid-cols-2">
                <Panel>
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-base font-semibold">Deep Analysis</h2>
                    {job.analysis ? <Badge tone="good">Saved</Badge> : <Badge>Not run</Badge>}
                  </div>
                  {job.analysis ? (
                    <div className="grid gap-4 text-sm">
                      <p className="leading-6 text-muted-foreground">{job.analysis.summary}</p>
                      <List title="Responsibilities" items={job.analysis.responsibilities} />
                      <List title="Required Skills" items={job.analysis.required_skills} />
                      <List title="Preferred Skills" items={job.analysis.preferred_skills} />
                      <List title="Technologies" items={job.analysis.technologies} />
                      <List title="Interview Topics" items={job.analysis.interview_topics} />
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">Run intelligence when this application is worth deeper preparation.</p>
                  )}
                </Panel>

                <Panel>
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <h2 className="text-base font-semibold">Resume Match</h2>
                    {latestSuggestion ? <Badge tone="good">Fit {latestSuggestion.fit_score}</Badge> : <Badge>Not run</Badge>}
                  </div>
                  {latestSuggestion ? (
                    <div className="grid gap-4 text-sm">
                      <List title="Matched Skills" items={latestSuggestion.matched_skills} />
                      <List title="Missing Skills" items={latestSuggestion.missing_skills} />
                      <List title="Weak Skills" items={latestSuggestion.weak_skills} />
                      <List title="Keywords" items={latestSuggestion.keyword_suggestions} />
                      <div>
                        <h3 className="mb-2 font-medium">Bullet Suggestions</h3>
                        <div className="grid gap-3">
                          {latestSuggestion.bullet_suggestions.map((item, index) => (
                            <div key={`${item.suggested}-${index}`} className="rounded-md border border-border bg-muted/40 p-3">
                              <div className="text-xs text-muted-foreground">{item.original}</div>
                              <div className="mt-2 font-medium">{item.suggested}</div>
                              <div className="mt-1 text-xs text-muted-foreground">{item.reason}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="grid gap-3 text-sm text-muted-foreground">
                      <p>Create an active profile, then run intelligence for this job.</p>
                      {showRetryResume ? (
                        <Button variant="secondary" size="sm" onClick={() => suggestMutation.mutate()} disabled={suggestMutation.isPending}>
                          <FileText className="h-4 w-4" />
                          {suggestMutation.isPending ? "Matching..." : "Retry resume match"}
                        </Button>
                      ) : null}
                    </div>
                  )}
                </Panel>
              </div>

              <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
                <Panel>
                  <h2 className="text-base font-semibold">Status History</h2>
                  <div className="mt-4 grid gap-3">
                    {job.status_events.map((event) => (
                      <div key={event.id} className="border-b border-border pb-3 last:border-0 last:pb-0">
                        <div className="text-sm font-medium">
                          {event.from_status ?? "Created"} to {event.to_status}
                        </div>
                        <div className="text-xs text-muted-foreground">{formatDate(event.changed_at)}</div>
                        {event.note ? <p className="mt-1 text-sm text-muted-foreground">{event.note}</p> : null}
                      </div>
                    ))}
                  </div>
                </Panel>
                <Panel>
                  <h2 className="text-base font-semibold">Source Material</h2>
                  <details className="mt-3 text-sm">
                    <summary className="cursor-pointer font-medium text-primary">Show stored source content</summary>
                    <p className="mt-4 max-h-[360px] overflow-auto whitespace-pre-wrap leading-6 text-muted-foreground">{job.source_content || "No source content stored."}</p>
                  </details>
                </Panel>
              </div>

              <Button variant="ghost" onClick={() => queryClient.invalidateQueries({ queryKey: ["job", jobId] })}>
                <RefreshCw className="h-4 w-4" />
                Refresh job data
              </Button>
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function formFromJob(job: JobDetail): JobEditForm {
  return {
    company: job.company,
    role_title: job.role_title,
    category: job.category,
    location: job.location,
    remote_type: (job.remote_type as RemoteType) ?? "Unknown",
    summary: job.summary,
    responsibilities: job.responsibilities,
    required_skills: job.required_skills,
    links: job.links.map((link) => ({ kind: link.kind, label: link.label, url: link.url })),
    status: job.status,
    notes: job.notes
  };
}

function cleanForm(form: JobEditForm) {
  return {
    ...form,
    company: form.company.trim(),
    role_title: form.role_title.trim(),
    location: form.location?.trim() || null,
    summary: form.summary?.trim() || null,
    responsibilities: form.responsibilities.map((item) => item.trim()).filter(Boolean),
    required_skills: form.required_skills.map((item) => item.trim()).filter(Boolean),
    links: form.links.map((link) => ({ ...link, label: link.label.trim(), url: link.url.trim() })).filter((link) => link.url),
    notes: form.notes?.trim() || null
  };
}

function JobEditFormView({
  form,
  onChange,
  onSubmit,
  onCancel,
  isSaving,
  error
}: {
  form: JobEditForm;
  onChange: (next: JobEditForm) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isSaving: boolean;
  error: Error | null;
}) {
  const set = <K extends keyof JobEditForm>(key: K, value: JobEditForm[K]) => onChange({ ...form, [key]: value });
  const setLink = (index: number, patch: Partial<JobLinkInput>) => {
    const links = form.links.map((link, currentIndex) => (currentIndex === index ? { ...link, ...patch } : link));
    onChange({ ...form, links });
  };
  const addLink = () => onChange({ ...form, links: [...form.links, { kind: "custom", label: "Custom", url: "" }] });

  return (
    <form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Company">
          <Input value={form.company} onChange={(event) => set("company", event.target.value)} />
        </Field>
        <Field label="Role title">
          <Input value={form.role_title} onChange={(event) => set("role_title", event.target.value)} />
        </Field>
        <Field label="Category">
          <Select value={form.category} onChange={(event) => set("category", event.target.value as JobCategory)}>
            {jobCategories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Status">
          <Select value={form.status} onChange={(event) => set("status", event.target.value as JobStatus)}>
            {jobStatuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Location">
          <Input value={form.location ?? ""} onChange={(event) => set("location", event.target.value)} />
        </Field>
        <Field label="Remote">
          <Select value={form.remote_type ?? "Unknown"} onChange={(event) => set("remote_type", event.target.value as RemoteType)}>
            {remoteTypes.map((remoteType) => (
              <option key={remoteType} value={remoteType}>
                {remoteType}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Summary">
        <Textarea value={form.summary ?? ""} onChange={(event) => set("summary", event.target.value)} />
      </Field>
      <Field label="Responsibilities">
        <Textarea value={listToCsv(form.responsibilities)} onChange={(event) => set("responsibilities", csvToList(event.target.value))} />
      </Field>
      <Field label="Required skills">
        <Textarea value={listToCsv(form.required_skills)} onChange={(event) => set("required_skills", csvToList(event.target.value))} />
      </Field>
      <Field label="Notes">
        <Textarea value={form.notes ?? ""} onChange={(event) => set("notes", event.target.value)} className="min-h-28" />
      </Field>
      <div className="grid gap-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">Links</h2>
          <Button variant="secondary" size="sm" onClick={addLink}>
            Add link
          </Button>
        </div>
        {form.links.map((link, index) => (
          <div key={`${link.kind}-${index}`} className="grid gap-2 md:grid-cols-[170px_1fr_1fr]">
            <Select value={link.kind} onChange={(event) => setLink(index, { kind: event.target.value as JobLinkInput["kind"] })}>
              {Object.entries(linkKindLabels).map(([kind, label]) => (
                <option key={kind} value={kind}>
                  {label}
                </option>
              ))}
            </Select>
            <Input value={link.label} onChange={(event) => setLink(index, { label: event.target.value })} />
            <Input value={link.url} onChange={(event) => setLink(index, { url: event.target.value })} placeholder="https://..." />
          </div>
        ))}
      </div>
      {error ? <p className="text-sm text-destructive">{error.message}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={isSaving || !form.company.trim() || !form.role_title.trim()}>
          <Save className="h-4 w-4" />
          {isSaving ? "Saving..." : "Save changes"}
        </Button>
        <Button variant="secondary" onClick={onCancel} disabled={isSaving}>
          <X className="h-4 w-4" />
          Cancel
        </Button>
      </div>
    </form>
  );
}

function JobIntelligenceControl({
  readiness,
  readinessLoading,
  readinessError,
  isRunning,
  onRun
}: {
  readiness: AIReadiness | undefined;
  readinessLoading: boolean;
  readinessError: Error | null;
  isRunning: boolean;
  onRun: () => void;
}) {
  const ready = Boolean(readiness?.ready);
  return (
    <div className="rounded-md border border-border bg-muted/40 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="font-medium">Job Intelligence</div>
        {ready ? <Badge tone="good">Ready</Badge> : <Badge tone="warn">Needs setup</Badge>}
      </div>
      {readinessError ? <p className="text-sm text-destructive">{readinessError.message}</p> : null}
      {readinessLoading ? <p className="text-sm text-muted-foreground">Checking readiness...</p> : null}
      {readiness && !readiness.ready ? (
        <div className="mb-3 grid gap-2 text-sm text-muted-foreground">
          {readiness.missing_requirements.map((item) => (
            <div key={item} className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              {item}
            </div>
          ))}
          {!readiness.has_profile || !readiness.has_resume_text || !readiness.has_skills ? (
            <Link href="/profile" className="font-medium text-primary">
              Open profile
            </Link>
          ) : null}
        </div>
      ) : null}
      {readiness?.ready ? (
        <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          Model: {readiness.model}
        </div>
      ) : null}
      <Button onClick={onRun} disabled={!ready || isRunning}>
        <Sparkles className="h-4 w-4" />
        {isRunning ? "Running..." : "Run intelligence"}
      </Button>
    </div>
  );
}

function FitOverview({ suggestion }: { suggestion: ResumeSuggestion | null }) {
  if (!suggestion) {
    return (
      <Panel>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">Fit Overview</h2>
          <Badge>Not run</Badge>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">Run intelligence to see fit score, matched skills, gaps, and resume actions.</p>
      </Panel>
    );
  }

  const firstAction = suggestion.bullet_suggestions[0]?.suggested ?? suggestion.keyword_suggestions[0] ?? suggestion.missing_skills[0] ?? "Review the resume match details below.";
  return (
    <Panel>
      <div className="grid gap-5 lg:grid-cols-[160px_1fr]">
        <div>
          <div className="text-sm font-medium text-muted-foreground">Fit Score</div>
          <div className="mt-2 text-5xl font-semibold">{suggestion.fit_score}</div>
        </div>
        <div className="grid gap-4">
          <div>
            <h2 className="text-base font-semibold">Next Resume Action</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{firstAction}</p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <MiniList title="Matched" items={suggestion.matched_skills} tone="good" />
            <MiniList title="Missing" items={suggestion.missing_skills} tone="warn" />
            <MiniList title="Weak" items={suggestion.weak_skills} tone="bad" />
          </div>
        </div>
      </div>
    </Panel>
  );
}

function MiniList({ title, items, tone }: { title: string; items: string[]; tone: "good" | "warn" | "bad" }) {
  return (
    <div>
      <div className="mb-2 text-sm font-medium">{title}</div>
      <div className="flex flex-wrap gap-2">
        {items.slice(0, 4).map((item) => (
          <Badge key={item} tone={tone}>
            {item}
          </Badge>
        ))}
        {!items.length ? <span className="text-sm text-muted-foreground">None</span> : null}
      </div>
    </div>
  );
}

function List({ title, items, tone = "neutral" }: { title: string; items: string[]; tone?: "neutral" | "good" | "warn" | "bad" }) {
  return (
    <div>
      <h3 className="mb-2 font-medium">{title}</h3>
      {items.length ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <Badge key={item} tone={tone}>{item}</Badge>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground">None captured.</p>
      )}
    </div>
  );
}
