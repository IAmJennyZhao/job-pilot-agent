"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, ExternalLink, Pencil, RefreshCw, Save, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import {
  jobCategories,
  jobStatuses,
  remoteTypes,
  type AIReadiness,
  type AdvancedJobAnalysis,
  type CompanyResearch,
  type JobCategory,
  type JobCreatePayload,
  type JobDetail,
  type JobLinkInput,
  type JobStatus,
  type RemoteType
} from "@/lib/types";
import { csvToList, formatDate, listToCsv } from "@/lib/utils";

type JobEditForm = Omit<JobCreatePayload, "source_content" | "extraction_confidence" | "extraction_warnings" | "status_note">;

const linkKindLabels: Record<JobLinkInput["kind"], string> = {
  source: "Job Posting",
  company_portal: "Company Careers",
  application_portal: "Application Portal",
  recruiter: "Recruiter/Contact",
  company_info: "Company Info",
  custom: "Custom"
};

const additionalLinkKinds: JobLinkInput["kind"][] = [
  "application_portal",
  "company_portal",
  "recruiter",
  "company_info",
  "custom"
];

const advancedSteps = [
  "Reading the posting",
  "Researching the company",
  "Summarizing employee sentiment",
  "Comparing resume fit",
  "Preparing interview signals"
];

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
  const { data: advancedResponse } = useQuery({
    queryKey: ["advanced-analysis", jobId],
    queryFn: () => api.advancedAnalysis(jobId),
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
    queryClient.invalidateQueries({ queryKey: ["advanced-analysis", jobId] });
  };

  const updateMutation = useMutation({
    mutationFn: (values: JobEditForm) => api.updateJob(jobId, cleanForm(values)),
    onSuccess: () => {
      setIsEditing(false);
      invalidateJob();
    }
  });

  const advancedMutation = useMutation({
    mutationFn: (refreshCompany: boolean) => api.runAdvancedAnalysis(jobId, refreshCompany),
    onSuccess: invalidateJob
  });

  const cancelEdit = () => {
    if (job) setForm(formFromJob(job));
    setIsEditing(false);
  };

  const advancedAnalysis = useMemo(
    () => advancedMutation.data?.analysis ?? advancedResponse?.analysis ?? job?.latest_advanced_analysis ?? null,
    [advancedMutation.data, advancedResponse, job]
  );
  const companyResearch = advancedMutation.data?.company_research ?? advancedResponse?.company_research ?? null;
  const advancedErrors = advancedMutation.data?.errors ?? advancedResponse?.errors ?? advancedAnalysis?.errors ?? [];

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
              <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
                <JobOverview job={job} />
                <AdvancedAnalysisControl
                  readiness={readiness}
                  readinessLoading={readinessLoading}
                  readinessError={readinessError as Error | null}
                  isRunning={advancedMutation.isPending}
                  savedAt={advancedAnalysis?.updated_at ?? null}
                  onRun={() => advancedMutation.mutate(false)}
                  onRefresh={() => advancedMutation.mutate(true)}
                />
              </div>
            )}
            <ProcessSteps active={advancedMutation.isPending} steps={advancedSteps} />
            {advancedMutation.data?.status === "partial" ? (
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                {advancedMutation.data.errors.length
                  ? advancedMutation.data.errors.join(" ")
                  : "Advanced analysis completed with partial coverage."}
              </div>
            ) : null}
            {advancedMutation.error ? <p className="mt-3 text-sm text-destructive">{(advancedMutation.error as Error).message}</p> : null}
          </Panel>

          {!isEditing ? (
            <>
              <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
                <Panel>
                  <h2 className="text-base font-semibold">Tracker Summary</h2>
                  <div className="mt-4 grid gap-4 text-sm">
                    {job.summary ? <p className="leading-6 text-muted-foreground">{job.summary}</p> : null}
                    <List title="Responsibilities" items={job.responsibilities} />
                    <List title="Concise Skills" items={job.required_skills} />
                    <List title="Benefits" items={job.benefits} />
                    {job.extraction_warnings.length ? <List title="Extraction Warnings" items={job.extraction_warnings} tone="warn" /> : null}
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

              <AdvancedAnalysisView
                analysis={advancedAnalysis}
                companyResearch={companyResearch}
                errors={advancedErrors}
              />

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
    pay_min: job.pay_min,
    pay_max: job.pay_max,
    pay_currency: job.pay_currency,
    pay_period: job.pay_period,
    pay_raw: job.pay_raw,
    benefits: job.benefits,
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
    benefits: (form.benefits ?? []).map((item) => item.trim()).filter(Boolean),
    links: form.links
      .map((link) => ({ ...link, label: link.label.trim() || linkKindLabels[link.kind], url: link.url.trim() }))
      .filter((link) => link.url),
    notes: form.notes?.trim() || null,
    pay_currency: form.pay_currency?.trim() || null,
    pay_raw: form.pay_raw?.trim() || null
  };
}

function JobOverview({ job }: { job: JobDetail }) {
  const source = job.links.find((link) => link.kind === "source") ?? job.links[0];
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <Badge>{job.status}</Badge>
        <Badge>{job.category}</Badge>
        {job.extraction_confidence !== null ? <Badge tone={job.extraction_confidence >= 80 ? "good" : "warn"}>Confidence {job.extraction_confidence}</Badge> : null}
      </div>
      <div className="mt-5 grid gap-3 text-sm md:grid-cols-2">
        <InfoRow label="Company" value={job.company} />
        <InfoRow label="Role" value={job.role_title} />
        <InfoRow label="Location" value={job.location || "Unknown"} />
        <InfoRow label="Remote" value={job.remote_type || "Unknown"} />
        <InfoRow label="Pay" value={formatPay(job)} />
        <InfoRow
          label="Job Posting"
          value={source ? source.label || linkKindLabels[source.kind] : "Not saved"}
          href={source?.url}
        />
      </div>
      {job.notes ? <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{job.notes}</p> : null}
    </div>
  );
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
    const nextPatch = patch.kind ? { ...patch, label: patch.label ?? linkKindLabels[patch.kind] } : patch;
    const links = form.links.map((link, currentIndex) => (currentIndex === index ? { ...link, ...nextPatch } : link));
    onChange({ ...form, links });
  };
  const addLink = () => onChange({ ...form, links: [...form.links, { kind: "custom", label: "Custom", url: "" }] });
  const removeLink = (index: number) => onChange({ ...form, links: form.links.filter((_link, currentIndex) => currentIndex !== index) });

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
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Pay minimum">
          <Input type="number" value={form.pay_min ?? ""} onChange={(event) => set("pay_min", event.target.value ? Number(event.target.value) : null)} />
        </Field>
        <Field label="Pay maximum">
          <Input type="number" value={form.pay_max ?? ""} onChange={(event) => set("pay_max", event.target.value ? Number(event.target.value) : null)} />
        </Field>
        <Field label="Pay currency">
          <Input value={form.pay_currency ?? ""} onChange={(event) => set("pay_currency", event.target.value)} placeholder="USD" />
        </Field>
        <Field label="Pay period">
          <Select value={form.pay_period ?? "unknown"} onChange={(event) => set("pay_period", event.target.value)}>
            {["unknown", "hour", "day", "week", "month", "year", "contract"].map((period) => (
              <option key={period} value={period}>
                {period}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Raw pay text">
        <Input value={form.pay_raw ?? ""} onChange={(event) => set("pay_raw", event.target.value)} />
      </Field>
      <Field label="Benefits">
        <Textarea value={listToCsv(form.benefits ?? [])} onChange={(event) => set("benefits", csvToList(event.target.value))} />
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
          <div key={`${link.kind}-${index}`} className="grid gap-2 md:grid-cols-[170px_1fr_1fr_40px]">
            {link.kind === "source" ? (
              <Input value="Job Posting" disabled />
            ) : (
              <Select value={link.kind} onChange={(event) => setLink(index, { kind: event.target.value as JobLinkInput["kind"] })}>
                {additionalLinkKinds.map((kind) => (
                  <option key={kind} value={kind}>
                    {linkKindLabels[kind]}
                  </option>
                ))}
              </Select>
            )}
            <Input value={link.label} onChange={(event) => setLink(index, { label: event.target.value })} />
            <Input value={link.url} onChange={(event) => setLink(index, { url: event.target.value })} placeholder="https://..." />
            {link.kind !== "source" ? (
              <Button variant="ghost" size="icon" onClick={() => removeLink(index)} title="Remove link">
                <X className="h-4 w-4" />
              </Button>
            ) : (
              <span />
            )}
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

function AdvancedAnalysisControl({
  readiness,
  readinessLoading,
  readinessError,
  isRunning,
  savedAt,
  onRun,
  onRefresh
}: {
  readiness: AIReadiness | undefined;
  readinessLoading: boolean;
  readinessError: Error | null;
  isRunning: boolean;
  savedAt: string | null;
  onRun: () => void;
  onRefresh: () => void;
}) {
  const canRun = Boolean(readiness?.has_openai_api_key && readiness.has_openai_model);
  const setupNotes = readiness
    ? readiness.missing_requirements.filter((item) => item === "OPENAI_API_KEY" || item === "OPENAI_MODEL")
    : [];
  const skippedNotes = readiness
    ? [
        ...readiness.missing_requirements.filter((item) => item !== "OPENAI_API_KEY" && item !== "OPENAI_MODEL"),
        ...(readiness.has_openai_research_model ? [] : ["OPENAI_RESEARCH_MODEL for company research"])
      ]
    : [];

  return (
    <div className="rounded-md border border-border bg-muted/40 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="font-medium">Advanced Detailed Analysis</div>
        {canRun ? <Badge tone="good">Ready</Badge> : <Badge tone="warn">Needs setup</Badge>}
      </div>
      {readinessError ? <p className="text-sm text-destructive">{readinessError.message}</p> : null}
      {readinessLoading ? <p className="text-sm text-muted-foreground">Checking readiness...</p> : null}
      {setupNotes.length ? (
        <div className="mb-3 grid gap-2 text-sm text-muted-foreground">
          {setupNotes.map((item) => (
            <div key={item} className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              {item}
            </div>
          ))}
        </div>
      ) : null}
      {skippedNotes.length && canRun ? (
        <div className="mb-3 grid gap-2 text-sm text-muted-foreground">
          {skippedNotes.map((item) => (
            <div key={item} className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              {item} may be unavailable.
            </div>
          ))}
          {!readiness?.has_profile || !readiness.has_resume_text || !readiness.has_skills ? (
            <Link href="/profile" className="font-medium text-primary">
              Open profile
            </Link>
          ) : null}
        </div>
      ) : null}
      {readiness?.model ? (
        <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          Extraction model: {readiness.model}
        </div>
      ) : null}
      {readiness?.research_model ? (
        <div className="mb-3 text-sm text-muted-foreground">Research model: {readiness.research_model}</div>
      ) : null}
      {savedAt ? <div className="mb-3 text-xs text-muted-foreground">Last run {formatDate(savedAt)}</div> : null}
      <div className="flex flex-wrap gap-2">
        <Button onClick={onRun} disabled={!canRun || isRunning}>
          <Sparkles className="h-4 w-4" />
          {isRunning ? "Running..." : savedAt ? "Run again" : "Run analysis"}
        </Button>
        {savedAt ? (
          <Button variant="secondary" onClick={onRefresh} disabled={!canRun || isRunning}>
            <RefreshCw className="h-4 w-4" />
            Refresh company research
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function AdvancedAnalysisView({
  analysis,
  companyResearch,
  errors
}: {
  analysis: AdvancedJobAnalysis | null;
  companyResearch: CompanyResearch | null;
  errors: string[];
}) {
  if (!analysis) {
    return (
      <Panel>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">Advanced Detailed Analysis</h2>
          <Badge>Not run</Badge>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">Run advanced analysis when this application needs deeper company, resume, and interview prep.</p>
      </Panel>
    );
  }

  const insights = analysis.job_insights;
  const sentiment = analysis.company_sentiment ?? (companyResearch ? {
    sentiment: companyResearch.sentiment,
    summary: companyResearch.summary,
    themes: companyResearch.themes,
    source_links: companyResearch.source_links,
    confidence: companyResearch.confidence,
    coverage_note: companyResearch.coverage_note
  } : null);
  const sourceLinks = analysis.source_links.length ? analysis.source_links : sentiment?.source_links ?? [];

  return (
    <Panel>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Advanced Detailed Analysis</h2>
          <p className="mt-1 text-sm text-muted-foreground">Reusable company research plus job-specific prep signals.</p>
        </div>
        <Badge tone={analysis.status === "complete" ? "good" : "warn"}>{analysis.status}</Badge>
      </div>

      {errors.length ? (
        <div className="mb-5 grid gap-1 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {errors.map((error) => (
            <div key={error}>{error}</div>
          ))}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <Section title="Job And Role Insights" unavailable={!insights ? errorFor(errors, "Posting analysis failed") : null}>
          {insights ? (
            <div className="grid gap-4">
              {insights.summary ? <p className="leading-6 text-muted-foreground">{insights.summary}</p> : null}
              <List title="Role Focus" items={insights.role_focus ?? []} />
              <List title="Responsibilities" items={insights.responsibilities ?? []} />
              <List title="Must-Have Skills" items={insights.must_have_skills ?? []} />
              <List title="Nice-To-Have Skills" items={insights.nice_to_have_skills ?? []} />
              {insights.seniority_signal ? <InfoRow label="Seniority Signal" value={insights.seniority_signal} /> : null}
              <List title="Concerns" items={insights.concerns ?? []} tone="warn" />
            </div>
          ) : null}
        </Section>

        <Section title="Company And Employee Sentiment" unavailable={!sentiment ? errorFor(errors, "Company research failed") : null}>
          {sentiment ? (
            <div className="grid gap-4">
              <div className="flex flex-wrap gap-2">
                {sentiment.sentiment ? <Badge>{sentiment.sentiment}</Badge> : null}
                {typeof sentiment.confidence === "number" ? <Badge tone={sentiment.confidence >= 70 ? "good" : "warn"}>Confidence {sentiment.confidence}</Badge> : null}
              </div>
              {sentiment.summary ? <p className="leading-6 text-muted-foreground">{sentiment.summary}</p> : null}
              <List title="Themes" items={sentiment.themes ?? []} />
              {sentiment.coverage_note ? <p className="text-sm text-muted-foreground">{sentiment.coverage_note}</p> : null}
              <SourceLinks links={sourceLinks} />
            </div>
          ) : null}
        </Section>

        <Section title="Resume Fit" unavailable={analysis.top_company_fit.length || analysis.resume_keywords.length || analysis.risks_gaps.length ? null : errorFor(errors, "Resume fit failed") ?? errorFor(errors, "Resume fit skipped")}>
          <div className="grid gap-4">
            <List title="Top Company Fit" items={analysis.top_company_fit} tone="good" />
            <List title="Resume Keywords" items={analysis.resume_keywords} />
            <List title="Risks And Gaps" items={analysis.risks_gaps} tone="warn" />
          </div>
        </Section>

        <Section title="Expected Questions" unavailable={analysis.expected_questions.length ? null : errorFor(errors, "Interview prep failed")}>
          <QuestionList questions={analysis.expected_questions} />
        </Section>
      </div>
    </Panel>
  );
}

function ProcessSteps({ active, steps }: { active: boolean; steps: string[] }) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setIndex(0);
      return;
    }
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % steps.length), 1400);
    return () => window.clearInterval(timer);
  }, [active, steps.length]);

  if (!active) return null;
  return (
    <div className="mt-4 rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
      {steps[index]}
    </div>
  );
}

function Section({
  title,
  unavailable,
  children
}: {
  title: string;
  unavailable?: string | null;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-4">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {unavailable ? <p className="text-sm text-muted-foreground">Unavailable: {unavailable}</p> : children}
    </div>
  );
}

function SourceLinks({ links }: { links: Array<{ title?: string; url?: string }> }) {
  if (!links.length) return null;
  return (
    <div>
      <h3 className="mb-2 font-medium">Sources</h3>
      <div className="grid gap-2">
        {links.map((link, index) => (
          link.url ? (
            <a key={`${link.url}-${index}`} href={link.url} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-3 rounded-md border border-border bg-white px-3 py-2 text-sm">
              <span>{link.title || link.url}</span>
              <ExternalLink className="h-4 w-4 text-muted-foreground" />
            </a>
          ) : null
        ))}
      </div>
    </div>
  );
}

function QuestionList({ questions }: { questions: Array<{ question: string; type: string; why_it_matters: string }> }) {
  if (!questions.length) return <p className="text-sm text-muted-foreground">No questions generated.</p>;
  return (
    <div className="grid gap-3">
      {questions.map((question, index) => (
        <div key={`${question.question}-${index}`} className="rounded-md border border-border bg-white p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{question.type}</Badge>
            <span className="font-medium">{question.question}</span>
          </div>
          <p className="mt-2 text-muted-foreground">{question.why_it_matters}</p>
        </div>
      ))}
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

function InfoRow({ label, value, href }: { label: string; value: string; href?: string }) {
  return (
    <div className="rounded-md border border-border bg-white p-3">
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-2 font-medium text-primary">
          {value}
          <ExternalLink className="h-4 w-4" />
        </a>
      ) : (
        <div className="mt-1 font-medium">{value}</div>
      )}
    </div>
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

function errorFor(errors: string[], prefix: string) {
  return errors.find((error) => error.startsWith(prefix)) ?? null;
}
