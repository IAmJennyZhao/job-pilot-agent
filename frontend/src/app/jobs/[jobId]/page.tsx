"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, ChevronDown, ExternalLink, FileText, Mail, Pencil, RefreshCw, Save, Sparkles, X } from "lucide-react";
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
  type AssetRecommendation,
  type CompanyResearch,
  type CoverLetterTemplate,
  type JobCategory,
  type JobCreatePayload,
  type JobDetail,
  type JobLinkInput,
  type JobStatus,
  type JobStatusEvent,
  type JobStatusEventPayload,
  type RemoteType,
  type ResumeOption
} from "@/lib/types";
import { cn, csvToList, formatDate, listToCsv } from "@/lib/utils";

type JobEditForm = Omit<JobCreatePayload, "source_content" | "extraction_confidence" | "extraction_warnings" | "status_note">;

const linkKindLabels: Record<JobLinkInput["kind"], string> = {
  source: "Job Posting",
  company_portal: "Company Careers",
  application_portal: "Application Portal",
  recruiter: "Recruiter/Contact",
  company_info: "Company Info",
  custom: "Custom"
};

const editableLinkKinds: JobLinkInput["kind"][] = [
  "source",
  "application_portal",
  "company_portal",
  "recruiter",
  "company_info",
  "custom"
];

const advancedSteps = [
  "Reading the posting",
  "Searching public company sources",
  "Summarizing employee sentiment",
  "Comparing resume fit",
  "Preparing interview signals"
];

const softSkillPattern = /\b(collaboration|communication|stakeholder|cross-functional|teamwork|leadership|written|verbal|presentation|interpersonal|relationship)\b/i;
const displayStopWords = new Set(["a", "an", "and", "as", "for", "in", "of", "on", "or", "the", "to", "with"]);

function compactText(value: string | null | undefined, limit = 140) {
  const text = (value ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit + 1).replace(/\s+\S*$/, "").replace(/[.,;:]$/, "")}...`;
}

function displayKey(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9+#.]+/g, " ")
    .split(" ")
    .filter((token) => token && !displayStopWords.has(token))
    .join(" ");
}

function isSimilarDisplayKey(candidate: string, usedKeys: Set<string>) {
  if (!candidate || usedKeys.has(candidate)) return true;
  const candidateTokens = new Set(candidate.split(" "));
  for (const usedKey of usedKeys) {
    const usedTokens = new Set(usedKey.split(" "));
    const overlap = [...candidateTokens].filter((token) => usedTokens.has(token));
    if (overlap.length >= 2 && overlap.length / Math.min(candidateTokens.size, usedTokens.size) >= 0.75) {
      return true;
    }
  }
  return false;
}

function compactItems(
  items: Array<string | null | undefined>,
  {
    limit = 5,
    techOnly = false,
    usedKeys = new Set<string>(),
    textLimit = 64
  }: {
    limit?: number;
    techOnly?: boolean;
    usedKeys?: Set<string>;
    textLimit?: number;
  } = {}
) {
  const result: string[] = [];
  for (const item of items) {
    const text = compactText(item, textLimit);
    if (!text) continue;
    if (techOnly && softSkillPattern.test(text)) continue;
    const key = displayKey(text);
    if (isSimilarDisplayKey(key, usedKeys)) continue;
    usedKeys.add(key);
    result.push(text);
    if (result.length >= limit) break;
  }
  return result;
}

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
  const { data: resumeOptions = [] } = useQuery({
    queryKey: ["resume-options"],
    queryFn: api.resumeOptions
  });
  const { data: coverLetterTemplates = [] } = useQuery({
    queryKey: ["cover-letter-templates"],
    queryFn: api.coverLetterTemplates
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
  const statusMutation = useMutation({
    mutationFn: (status: JobStatus) => api.updateJob(jobId, { status }),
    onSuccess: invalidateJob
  });

  const advancedMutation = useMutation({
    mutationFn: (refreshCompany: boolean) => api.runAdvancedAnalysis(jobId, refreshCompany),
    onSuccess: invalidateJob
  });
  const reviewMutation = useMutation({
    mutationFn: () => api.runJobIntelligence(jobId),
    onSuccess: invalidateJob
  });
  const aiAssetRankMutation = useMutation({
    mutationFn: () => api.rankAssets(jobId),
    onSuccess: invalidateJob
  });
  const assetSelectionMutation = useMutation({
    mutationFn: (payload: { selected_resume_option_id?: string | null; selected_cover_letter_template_id?: string | null }) =>
      api.updateJob(jobId, payload),
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
  const assetRecommendation =
    aiAssetRankMutation.data ?? reviewMutation.data?.asset_recommendation ?? job?.latest_asset_recommendation ?? null;

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
                <JobOverview
                  job={job}
                  onStatusChange={(status) => {
                    if (status !== job.status) statusMutation.mutate(status);
                  }}
                  isSavingStatus={statusMutation.isPending}
                />
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
            {statusMutation.error ? <p className="mt-3 text-sm text-destructive">{(statusMutation.error as Error).message}</p> : null}
          </Panel>

          {!isEditing ? (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
              <MergedJobDetail job={job} analysis={advancedAnalysis} companyResearch={companyResearch} errors={advancedErrors} />
              <div className="grid content-start gap-4">
                <Panel>
                  <ApplicationAssetsPanel
                    job={job}
                    recommendation={assetRecommendation}
                    resumeOptions={resumeOptions}
                    coverLetterTemplates={coverLetterTemplates}
                    isReviewing={reviewMutation.isPending}
                    isRankingAi={aiAssetRankMutation.isPending}
                    isSaving={assetSelectionMutation.isPending}
                    onRunReview={() => reviewMutation.mutate()}
                    onRankAi={() => aiAssetRankMutation.mutate()}
                    onSelectResume={(id) => assetSelectionMutation.mutate({ selected_resume_option_id: id })}
                    onSelectCoverLetter={(id) => assetSelectionMutation.mutate({ selected_cover_letter_template_id: id })}
                    error={(reviewMutation.error || aiAssetRankMutation.error || assetSelectionMutation.error) as Error | null}
                  />
                </Panel>
                <Panel>
                  <JobLinks links={job.links} />
                </Panel>
                <Panel>
                  <StatusHistoryEditor
                    job={job}
                    onChanged={invalidateJob}
                    onStatusChange={(status) => {
                      if (status !== job.status) statusMutation.mutate(status);
                    }}
                    isSavingStatus={statusMutation.isPending}
                  />
                </Panel>
              </div>
              <Button variant="ghost" className="justify-self-start xl:col-span-2" onClick={() => queryClient.invalidateQueries({ queryKey: ["job", jobId] })}>
                <RefreshCw className="h-4 w-4" />
                Refresh job data
              </Button>
            </div>
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

function QuickStatusSelect({
  value,
  onChange,
  disabled
}: {
  value: JobStatus;
  onChange: (status: JobStatus) => void;
  disabled?: boolean;
}) {
  return (
    <Select
      value={value}
      onChange={(event) => onChange(event.target.value as JobStatus)}
      disabled={disabled}
      className="h-8 w-auto min-w-44 px-2 text-xs font-medium"
      aria-label="Change job status"
    >
      {jobStatuses.map((status) => (
        <option key={status} value={status}>
          {status}
        </option>
      ))}
    </Select>
  );
}

function JobOverview({
  job,
  onStatusChange,
  isSavingStatus
}: {
  job: JobDetail;
  onStatusChange: (status: JobStatus) => void;
  isSavingStatus: boolean;
}) {
  const source = job.links.find((link) => link.kind === "source") ?? job.links[0];
  const companyLink = job.links.find((link) => link.kind === "company_info" || link.kind === "company_portal");
  const annualPay = formatAnnualPay(job);
  const payDisplay = annualPay === "Annual not calculated" ? formatPay(job) : `${formatPay(job)} · ${annualPay}`;
  const locationDisplay = [job.location, job.remote_type].filter(Boolean).join(" · ") || "Unknown";
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Application Status:</span>
        <QuickStatusSelect value={job.status} onChange={onStatusChange} disabled={isSavingStatus} />
        <Badge>{job.category}</Badge>
        {job.extraction_confidence !== null ? <Badge tone={job.extraction_confidence >= 80 ? "good" : "warn"}>Confidence {job.extraction_confidence}</Badge> : null}
      </div>
      <div className="mt-5 grid gap-3 text-sm md:grid-cols-2">
        <InfoRow label="Company" value={job.company} href={companyLink?.url} />
        <InfoRow label="Role" value={job.role_title} />
        <InfoRow label="Location" value={locationDisplay} />
        <InfoRow label="Pay" value={payDisplay} />
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

function MergedJobDetail({
  job,
  analysis,
  companyResearch,
  errors
}: {
  job: JobDetail;
  analysis: AdvancedJobAnalysis | null;
  companyResearch: CompanyResearch | null;
  errors: string[];
}) {
  const insights = analysis?.job_insights ?? null;
  const sentiment = analysis?.company_sentiment ?? (companyResearch ? {
    sentiment: companyResearch.sentiment,
    summary: companyResearch.summary,
    themes: companyResearch.themes,
    highlight_phrases: companyResearch.highlight_phrases,
    source_links: companyResearch.source_links,
    confidence: companyResearch.confidence,
    coverage_note: companyResearch.coverage_note
  } : null);
  const highlightPhrases = analysis?.highlight_phrases ?? {};
  const skillKeys = new Set<string>();
  const insightKeys = new Set<string>();
  const roleSignals = compactItems([...(insights?.role_focus ?? []), insights?.seniority_signal], { limit: 4, usedKeys: insightKeys, textLimit: 56 });
  const responsibilities = compactItems(insights?.responsibilities?.length ? insights.responsibilities : job.responsibilities, { limit: 7, usedKeys: insightKeys, textLimit: 1000 });
  const mustHaveTech = compactItems([...(job.required_skills ?? []), ...(insights?.must_have_skills ?? [])], { limit: 10, techOnly: true, usedKeys: skillKeys, textLimit: 1000 });
  const niceToHaveTech = compactItems(insights?.nice_to_have_skills ?? [], { limit: 7, techOnly: true, usedKeys: skillKeys, textLimit: 1000 });
  const benefits = compactItems(job.benefits, { limit: 5, textLimit: 48 });
  const companySignals = compactItems([sentiment?.summary, ...(sentiment?.themes ?? [])], { limit: 7, textLimit: 1000 });
  const fitSignals = compactItems(analysis?.top_company_fit ?? [], { limit: 5, textLimit: 1000 });
  const resumeKeywords = compactItems(analysis?.resume_keywords ?? [], { limit: 8, techOnly: true, textLimit: 38 });
  const risksGaps = compactItems(analysis?.risks_gaps ?? [], { limit: 5, textLimit: 1000 });
  const sourceLinks = analysis?.source_links.length ? analysis.source_links : sentiment?.source_links ?? [];
  return (
    <div className="grid gap-4">
      <Panel>
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Role Snapshot</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {compactText(insights?.summary || job.summary || "No summary captured.", 120)}
            </p>
          </div>
          {analysis ? <Badge tone={analysis.status === "complete" ? "good" : "warn"}>{analysis.status}</Badge> : <Badge>Tracker only</Badge>}
        </div>

        {errors.length ? (
          <div className="mb-5 grid gap-1 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            {errors.map((error) => (
              <div key={error}>{compactText(error, 120)}</div>
            ))}
          </div>
        ) : null}

        <div className="grid gap-5">
          <Section title="Role Signals">
            <List items={roleSignals.length ? roleSignals : [job.category]} />
          </Section>
          <Section title="Responsibilities">
            <BulletList items={responsibilities} highlights={highlightPhrases.responsibilities} />
          </Section>
          <div className="grid gap-5 md:grid-cols-2">
            <Section title="Skills">
              <List items={mustHaveTech} />
            </Section>
            <Section title="Nice to Have">
              <List items={niceToHaveTech} />
            </Section>
          </div>
          <Section title="Pay And Benefits">
            <div className="grid gap-3 md:grid-cols-2">
              <InfoRow label="Pay" value={formatPay(job)} />
              <InfoRow label="Annual Equivalent" value={formatAnnualPay(job)} />
            </div>
            <div className="mt-4">
              <List items={benefits} />
            </div>
          </Section>
          {job.extraction_warnings.length ? (
            <Section title="Extraction Warnings">
              <List items={compactItems(job.extraction_warnings, { limit: 4, textLimit: 90 })} tone="warn" />
            </Section>
          ) : null}
        </div>
      </Panel>

      {analysis ? (
        <>
          <Panel>
            <h2 className="mb-5 text-base font-semibold">Fit And Gaps</h2>
            <div className="grid gap-5 md:grid-cols-3">
              <div>
                <h3 className="mb-2 text-sm font-medium text-green-700">Fit</h3>
                <BulletList items={fitSignals} highlights={highlightPhrases.fit} />
              </div>
              <List title="Keywords" items={resumeKeywords} />
              <div>
                <h3 className="mb-2 text-sm font-medium text-amber-700">Gaps</h3>
                <BulletList items={risksGaps} highlights={highlightPhrases.gaps} />
              </div>
            </div>
          </Panel>
          {sentiment ? (
            <Panel>
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-base font-semibold">Company Signals</h2>
                <div className="flex flex-wrap gap-2">
                  {sentiment.sentiment ? <Badge>{sentiment.sentiment}</Badge> : null}
                  {typeof sentiment.confidence === "number" ? <Badge tone={sentiment.confidence >= 70 ? "good" : "warn"}>{sentiment.confidence}% coverage</Badge> : null}
                </div>
              </div>
              <BulletList items={companySignals} highlights={sentiment.highlight_phrases} />
              {sentiment.coverage_note ? <p className="mt-4 text-sm text-muted-foreground">{compactText(sentiment.coverage_note, 180)}</p> : null}
              <SourceLinks links={sourceLinks} />
            </Panel>
          ) : null}
          <Panel>
            <h2 className="mb-5 text-base font-semibold">Interview Prep</h2>
            <QuestionList questions={analysis.expected_questions} />
          </Panel>
        </>
      ) : (
        <Panel>
          <h2 className="text-base font-semibold">Prep Signals</h2>
          <p className="mt-2 text-sm text-muted-foreground">Run Advanced Detailed Analysis to add fit, company, and interview prep signals.</p>
        </Panel>
      )}
    </div>
  );
}

function ApplicationAssetsPanel({
  job,
  recommendation,
  resumeOptions,
  coverLetterTemplates,
  isReviewing,
  isRankingAi,
  isSaving,
  onRunReview,
  onRankAi,
  onSelectResume,
  onSelectCoverLetter,
  error
}: {
  job: JobDetail;
  recommendation: AssetRecommendation | null;
  resumeOptions: ResumeOption[];
  coverLetterTemplates: CoverLetterTemplate[];
  isReviewing: boolean;
  isRankingAi: boolean;
  isSaving: boolean;
  onRunReview: () => void;
  onRankAi: () => void;
  onSelectResume: (id: string | null) => void;
  onSelectCoverLetter: (id: string | null) => void;
  error: Error | null;
}) {
  const readyResumes = resumeOptions.filter((option) => option.status === "ready");
  const latestSource = recommendation?.source === "ai" ? "AI ranking" : recommendation ? "Keyword score" : "No ranking";
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Application Assets</h2>
          <p className="mt-1 text-xs text-muted-foreground">{latestSource}</p>
        </div>
        {recommendation ? <Badge tone={recommendation.source === "ai" ? "good" : "neutral"}>{recommendation.source}</Badge> : null}
      </div>
      <div className="grid gap-3">
        <Field label="Selected resume">
          <Select
            value={job.selected_resume_option_id ?? ""}
            onChange={(event) => onSelectResume(event.target.value || null)}
            disabled={isSaving}
          >
            <option value="">Not selected</option>
            {readyResumes.map((option) => (
              <option key={option.id} value={option.id}>
                {option.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Selected cover letter">
          <Select
            value={job.selected_cover_letter_template_id ?? ""}
            onChange={(event) => onSelectCoverLetter(event.target.value || null)}
            disabled={isSaving}
          >
            <option value="">Not selected</option>
            {coverLetterTemplates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.title}
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={onRunReview} disabled={isReviewing}>
            <Sparkles className="h-4 w-4" />
            {isReviewing ? "Reviewing..." : "Initial review"}
          </Button>
          <Button variant="secondary" size="sm" onClick={onRankAi} disabled={isRankingAi}>
            <RefreshCw className="h-4 w-4" />
            {isRankingAi ? "Ranking..." : "AI rank"}
          </Button>
        </div>
        {error ? <p className="text-sm text-destructive">{error.message}</p> : null}
      </div>
      {recommendation ? (
        <div className="mt-5 grid gap-4">
          <AssetRankingList
            title="Resume ranking"
            icon={FileText}
            rankings={recommendation.resume_rankings}
            selectedId={job.selected_resume_option_id}
            onSelect={onSelectResume}
          />
          <AssetRankingList
            title="Cover letter ranking"
            icon={Mail}
            rankings={recommendation.cover_letter_rankings}
            selectedId={job.selected_cover_letter_template_id}
            onSelect={onSelectCoverLetter}
          />
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">Run initial review to rank saved assets for this job.</p>
      )}
    </div>
  );
}

function AssetRankingList({
  title,
  icon: Icon,
  rankings,
  selectedId,
  onSelect
}: {
  title: string;
  icon: React.ElementType;
  rankings: AssetRecommendation["resume_rankings"];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-primary" />
        {title}
      </div>
      <div className="grid gap-2">
        {rankings.length ? (
          rankings.slice(0, 3).map((ranking) => (
            <button
              key={ranking.asset_id}
              type="button"
              onClick={() => onSelect(ranking.asset_id)}
              className={cn(
                "rounded-md border p-3 text-left text-sm transition",
                selectedId === ranking.asset_id ? "border-primary bg-primary/5" : "border-border hover:bg-muted"
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{ranking.title}</span>
                <Badge tone={ranking.score >= 60 ? "good" : ranking.score >= 30 ? "warn" : "neutral"}>{ranking.score}</Badge>
              </div>
              {ranking.reasons[0] ? <p className="mt-1 text-xs text-muted-foreground">{ranking.reasons[0]}</p> : null}
            </button>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">No assets to rank.</p>
        )}
      </div>
    </div>
  );
}

function JobLinks({ links }: { links: JobDetail["links"] }) {
  return (
    <div>
      <h2 className="text-base font-semibold">Links</h2>
      <div className="mt-4 grid gap-2">
        {links.length ? (
          links.map((link) => (
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
  const addLink = () => onChange({ ...form, links: [...form.links, { kind: "source", label: "Job Posting", url: "" }] });
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
          <div key={`${link.kind}-${index}`} className="grid gap-2 md:grid-cols-[120px_minmax(140px,0.8fr)_minmax(240px,1.4fr)_40px]">
            <Select value={link.kind} onChange={(event) => setLink(index, { kind: event.target.value as JobLinkInput["kind"] })}>
              {editableLinkKinds.map((kind) => (
                <option key={kind} value={kind}>
                  {linkKindLabels[kind]}
                </option>
              ))}
            </Select>
            <Input value={link.label} onChange={(event) => setLink(index, { label: event.target.value })} />
            <Input value={link.url} onChange={(event) => setLink(index, { url: event.target.value })} placeholder="https://..." />
            <Button variant="ghost" size="icon" onClick={() => removeLink(index)} title="Remove link">
              <X className="h-4 w-4" />
            </Button>
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

function StatusHistoryEditor({
  job,
  onChanged,
  onStatusChange,
  isSavingStatus
}: {
  job: JobDetail;
  onChanged: () => void;
  onStatusChange: (status: JobStatus) => void;
  isSavingStatus: boolean;
}) {
  const sortedEvents = [...job.status_events].sort((a, b) => new Date(a.changed_at).getTime() - new Date(b.changed_at).getTime());
  const [isEditing, setIsEditing] = useState(false);
  const [newEvent, setNewEvent] = useState<JobStatusEventPayload>({
    to_status: job.status,
    changed_at: toDateTimeLocalValue(new Date().toISOString()),
    note: ""
  });

  const createMutation = useMutation({
    mutationFn: (payload: JobStatusEventPayload) => api.createStatusEvent(job.id, normalizeStatusPayload(payload)),
    onSuccess: onChanged
  });
  const updateMutation = useMutation({
    mutationFn: ({ eventId, payload }: { eventId: string; payload: Partial<JobStatusEventPayload> }) =>
      api.updateStatusEvent(job.id, eventId, normalizeStatusPayload(payload)),
    onSuccess: onChanged
  });
  const deleteMutation = useMutation({
    mutationFn: (eventId: string) => api.deleteStatusEvent(job.id, eventId),
    onSuccess: onChanged
  });

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Status History</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {isEditing ? "Correct accidental status changes or add missing steps. The latest event sets the current status." : "Application timeline for this job."}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <QuickStatusSelect value={job.status} onChange={onStatusChange} disabled={isSavingStatus} />
          <Button variant="secondary" size="sm" onClick={() => setIsEditing((current) => !current)}>
            {isEditing ? <X className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
            {isEditing ? "Done" : "Edit"}
          </Button>
        </div>
      </div>
      {!isEditing ? (
        <div className="mt-4 grid gap-3">
          {sortedEvents.length ? (
            sortedEvents.map((event) => <StatusEventDisplayRow key={event.id} event={event} />)
          ) : (
            <p className="text-sm text-muted-foreground">No status history yet.</p>
          )}
        </div>
      ) : (
        <>
          <div className="mt-4 grid gap-3">
            {sortedEvents.map((event) => (
              <StatusEventRow
                key={event.id}
                event={event}
                isSaving={updateMutation.isPending}
                isDeleting={deleteMutation.isPending}
                onSave={(payload) => updateMutation.mutate({ eventId: event.id, payload })}
                onDelete={() => deleteMutation.mutate(event.id)}
              />
            ))}
          </div>
          <div className="mt-5 rounded-md border border-border bg-muted/30 p-3">
            <div className="mb-3 text-sm font-semibold">Add status step</div>
            <div className="grid items-center gap-2 md:grid-cols-[180px_220px_minmax(0,1fr)_88px]">
              <Select value={newEvent.to_status} onChange={(event) => setNewEvent((current) => ({ ...current, to_status: event.target.value as JobStatus }))}>
                {jobStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </Select>
              <Input type="datetime-local" value={newEvent.changed_at ?? ""} onChange={(event) => setNewEvent((current) => ({ ...current, changed_at: event.target.value }))} />
              <Input value={newEvent.note ?? ""} onChange={(event) => setNewEvent((current) => ({ ...current, note: event.target.value }))} placeholder="Notes" />
              <Button onClick={() => createMutation.mutate(newEvent)} disabled={createMutation.isPending}>
                Add
              </Button>
            </div>
          </div>
          {createMutation.error || updateMutation.error || deleteMutation.error ? (
            <p className="mt-3 text-sm text-destructive">
              {((createMutation.error || updateMutation.error || deleteMutation.error) as Error).message}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

function StatusEventDisplayRow({ event }: { event: JobStatusEvent }) {
  return (
    <div className="rounded-md border border-border bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-medium">
          {event.from_status ?? "Created"} to {event.to_status}
        </div>
        <span className="text-xs text-muted-foreground">{formatDate(event.changed_at)}</span>
      </div>
      {event.note ? <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{event.note}</p> : null}
    </div>
  );
}

function StatusEventRow({
  event,
  isSaving,
  isDeleting,
  onSave,
  onDelete
}: {
  event: JobStatusEvent;
  isSaving: boolean;
  isDeleting: boolean;
  onSave: (payload: Partial<JobStatusEventPayload>) => void;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState<JobStatusEventPayload>({
    to_status: event.to_status,
    changed_at: toDateTimeLocalValue(event.changed_at),
    note: event.note ?? ""
  });

  useEffect(() => {
    setDraft({
      to_status: event.to_status,
      changed_at: toDateTimeLocalValue(event.changed_at),
      note: event.note ?? ""
    });
  }, [event.to_status, event.changed_at, event.note]);

  return (
    <div className="rounded-md border border-border bg-white p-3">
      <div className="mb-2 text-xs text-muted-foreground">
        {event.from_status ?? "Created"} to {event.to_status} - {formatDate(event.changed_at)}
      </div>
      <div className="grid items-center gap-2 md:grid-cols-[180px_220px_minmax(0,1fr)_88px_88px]">
        <Select value={draft.to_status} onChange={(input) => setDraft((current) => ({ ...current, to_status: input.target.value as JobStatus }))}>
          {jobStatuses.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
        <Input type="datetime-local" value={draft.changed_at ?? ""} onChange={(input) => setDraft((current) => ({ ...current, changed_at: input.target.value }))} />
        <Input value={draft.note ?? ""} onChange={(input) => setDraft((current) => ({ ...current, note: input.target.value }))} placeholder="Notes" />
        <Button variant="secondary" onClick={() => onSave(draft)} disabled={isSaving}>
          Save
        </Button>
        <Button variant="ghost" onClick={onDelete} disabled={isDeleting}>
          Delete
        </Button>
      </div>
    </div>
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
        ...(readiness.has_tavily_api_key ? [] : ["TAVILY_API_KEY for public company retrieval"])
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
      <div className="mb-3 text-sm text-muted-foreground">
        Company retrieval: {readiness?.has_tavily_api_key ? "Tavily enabled" : "limited fallback"}
      </div>
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
    <section className="border-t border-border pt-4 first:border-t-0 first:pt-0">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {unavailable ? <p className="text-sm text-muted-foreground">Unavailable: {unavailable}</p> : children}
    </section>
  );
}

function SourceLinks({ links }: { links: Array<{ title?: string; url?: string }> }) {
  const [open, setOpen] = useState(false);
  const valid = links.filter((l) => l.url);
  if (!valid.length) return null;
  return (
    <div className="mt-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", open && "rotate-180")} />
        Sources ({valid.length})
      </button>
      {open && (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {valid.map((link, index) => (
            <a key={`${link.url}-${index}`} href={link.url} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
              <span className="line-clamp-1">{link.title || link.url}</span>
              <ExternalLink className="h-4 w-4 text-muted-foreground" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

const questionTypeColors: Record<string, string> = {
  technical: "bg-violet-100 text-violet-800 border-violet-200",
  behavioral: "bg-amber-100 text-amber-800 border-amber-200",
  resume: "bg-blue-100 text-blue-800 border-blue-200",
  company: "bg-teal-100 text-teal-800 border-teal-200",
  role_specific: "bg-rose-100 text-rose-800 border-rose-200",
  system_design: "bg-indigo-100 text-indigo-800 border-indigo-200",
  mixed: "bg-gray-100 text-gray-700 border-gray-200",
};

function QuestionList({ questions }: { questions: Array<{ question: string; type: string; why_it_matters: string }> }) {
  const [filter, setFilter] = useState<string>("all");
  if (!questions.length) return <p className="text-sm text-muted-foreground">No questions generated.</p>;
  const types = [...new Set(questions.map((q) => q.type))];
  const visible = filter === "all" ? questions : questions.filter((q) => q.type === filter);
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          onClick={() => setFilter("all")}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            filter === "all" ? "bg-foreground text-background border-foreground" : "border-border hover:bg-muted text-muted-foreground"
          )}
        >
          All ({questions.length})
        </button>
        {types.map((type) => (
          <button
            key={type}
            onClick={() => setFilter(type)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
              filter === type
                ? (questionTypeColors[type] ?? "bg-muted border-border text-foreground")
                : "border-border hover:bg-muted text-muted-foreground"
            )}
          >
            {type.replace("_", " ")} ({questions.filter((q) => q.type === type).length})
          </button>
        ))}
      </div>
      <div className="grid gap-3">
        {visible.map((question, index) => (
          <div key={`${question.question}-${index}`} className="rounded-md border border-border p-3 text-sm">
            <div className="flex flex-wrap items-start gap-2">
              <span className={cn("shrink-0 rounded border px-1.5 py-0.5 text-xs font-medium", questionTypeColors[question.type] ?? "bg-muted text-muted-foreground border-border")}>
                {question.type.replace("_", " ")}
              </span>
              <span className="font-medium leading-snug">{question.question}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function selectSparseHighlights(items: string[], highlights: string[] = []) {
  const normalizedHighlights = highlights
    .map((highlight) => highlight.replace(/\s+/g, " ").trim())
    .filter(Boolean);
  const maxHighlightedItems = Math.max(1, Math.ceil(items.length / 2));
  const usedHighlights = new Set<string>();
  let highlightedItems = 0;

  return items.map((item) => {
    if (highlightedItems >= maxHighlightedItems) return null;
    const itemKey = item.toLowerCase();
    const highlight = normalizedHighlights.find((candidate) => {
      const candidateKey = candidate.toLowerCase();
      return !usedHighlights.has(candidateKey) && itemKey.includes(candidateKey);
    });
    if (!highlight) return null;
    usedHighlights.add(highlight.toLowerCase());
    highlightedItems += 1;
    return highlight;
  });
}

function HighlightedText({ text, highlight }: { text: string; highlight: string | null }) {
  if (!highlight) return <>{text}</>;
  const start = text.toLowerCase().indexOf(highlight.toLowerCase());
  if (start < 0) return <>{text}</>;
  const end = start + highlight.length;
  return (
    <>
      {text.slice(0, start)}
      <strong className="font-semibold text-foreground">{text.slice(start, end)}</strong>
      {text.slice(end)}
    </>
  );
}

function BulletList({ items, highlights = [] }: { items: string[]; highlights?: string[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">None captured.</p>;
  const selectedHighlights = selectSparseHighlights(items, highlights);
  return (
    <ul className="grid gap-1.5 text-sm">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2">
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/50" />
          <span><HighlightedText text={item} highlight={selectedHighlights[i]} /></span>
        </li>
      ))}
    </ul>
  );
}

function List({ title, items, tone = "neutral" }: { title?: string; items: string[]; tone?: "neutral" | "good" | "warn" | "bad" }) {
  return (
    <div>
      {title ? <h3 className="mb-2 font-medium">{title}</h3> : null}
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

function formatAnnualPay(job: { pay_annual_min: number | null; pay_annual_max: number | null; pay_currency: string | null }) {
  const currency = job.pay_currency ?? "USD";
  if (job.pay_annual_min !== null && job.pay_annual_max !== null) return `${currency} ${job.pay_annual_min.toLocaleString()}-${job.pay_annual_max.toLocaleString()} / year`;
  if (job.pay_annual_min !== null) return `${currency} ${job.pay_annual_min.toLocaleString()}+ / year`;
  if (job.pay_annual_max !== null) return `Up to ${currency} ${job.pay_annual_max.toLocaleString()} / year`;
  return "Annual not calculated";
}

function toDateTimeLocalValue(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function normalizeStatusPayload<T extends Partial<JobStatusEventPayload>>(payload: T): T {
  return {
    ...payload,
    changed_at: payload.changed_at ? new Date(payload.changed_at).toISOString() : payload.changed_at,
    note: payload.note?.trim() || null
  };
}
