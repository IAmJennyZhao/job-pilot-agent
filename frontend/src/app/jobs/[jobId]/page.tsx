"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, FileText, Pencil, RefreshCw, Save, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { jobStatuses, type AIReadiness, type JobStatus, type ResumeSuggestion } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const jobEditSchema = z.object({
  company: z.string().min(1),
  role_title: z.string().min(1),
  job_url: z.string().url().or(z.literal("")).optional(),
  status: z.enum(jobStatuses),
  notes: z.string().optional(),
  job_description: z.string().min(1)
});

type JobEditForm = z.infer<typeof jobEditSchema>;

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
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

  const form = useForm<JobEditForm>({
    resolver: zodResolver(jobEditSchema),
    defaultValues: {
      company: "",
      role_title: "",
      job_url: "",
      status: "Saved",
      notes: "",
      job_description: ""
    }
  });

  useEffect(() => {
    if (!job) {
      return;
    }
    form.reset({
      company: job.company,
      role_title: job.role_title,
      job_url: job.job_url ?? "",
      status: job.status,
      notes: job.notes ?? "",
      job_description: job.job_description
    });
  }, [form, job]);

  const invalidateJobIntelligence = () => {
    queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
    queryClient.invalidateQueries({ queryKey: ["ai-readiness", jobId] });
  };

  const updateMutation = useMutation({
    mutationFn: (values: JobEditForm) =>
      api.updateJob(jobId, {
        ...values,
        status: values.status as JobStatus,
        job_url: values.job_url || null,
        notes: values.notes || null
      }),
    onSuccess: () => {
      setIsEditing(false);
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const intelligenceMutation = useMutation({
    mutationFn: () => api.runJobIntelligence(jobId),
    onSuccess: invalidateJobIntelligence
  });

  const suggestMutation = useMutation({
    mutationFn: () => api.suggestResume(jobId),
    onSuccess: invalidateJobIntelligence
  });

  const cancelEdit = () => {
    if (job) {
      form.reset({
        company: job.company,
        role_title: job.role_title,
        job_url: job.job_url ?? "",
        status: job.status,
        notes: job.notes ?? "",
        job_description: job.job_description
      });
    }
    setIsEditing(false);
  };

  const latestSuggestion = job?.latest_resume_suggestion ?? null;
  const showRetryResume = Boolean(job?.analysis && !latestSuggestion && readiness?.ready);

  return (
    <div className="grid gap-6">
      <PageHeader
        title={job ? `${job.company}: ${job.role_title}` : "Job Detail"}
        description={job ? `${job.status} - Last updated ${formatDate(job.updated_at)}` : "Review job analysis and resume match results."}
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
            {isEditing ? (
              <form className="grid gap-4" onSubmit={form.handleSubmit((values) => updateMutation.mutate(values))}>
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Company" error={form.formState.errors.company?.message}>
                    <Input {...form.register("company")} />
                  </Field>
                  <Field label="Role title" error={form.formState.errors.role_title?.message}>
                    <Input {...form.register("role_title")} />
                  </Field>
                  <Field label="Job URL" error={form.formState.errors.job_url?.message}>
                    <Input {...form.register("job_url")} placeholder="https://..." />
                  </Field>
                  <Field label="Status" error={form.formState.errors.status?.message}>
                    <Select {...form.register("status")}>
                      {jobStatuses.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
                <Field label="Notes">
                  <Textarea {...form.register("notes")} className="min-h-28" />
                </Field>
                <Field label="Job description" error={form.formState.errors.job_description?.message}>
                  <Textarea {...form.register("job_description")} className="min-h-64" />
                </Field>
                {updateMutation.error ? <p className="text-sm text-destructive">{(updateMutation.error as Error).message}</p> : null}
                <div className="flex flex-wrap gap-2">
                  <Button type="submit" disabled={updateMutation.isPending}>
                    <Save className="h-4 w-4" />
                    {updateMutation.isPending ? "Saving..." : "Save changes"}
                  </Button>
                  <Button variant="secondary" onClick={cancelEdit} disabled={updateMutation.isPending}>
                    <X className="h-4 w-4" />
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
                <div>
                  <div className="flex flex-wrap gap-2">
                    <Badge>{job.status}</Badge>
                    {job.fit_score !== null ? <Badge tone={job.fit_score >= 75 ? "good" : job.fit_score >= 50 ? "warn" : "bad"}>Fit {job.fit_score}</Badge> : null}
                    {readiness?.model ? <Badge>{readiness.model}</Badge> : null}
                  </div>
                  <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{job.notes || "No notes yet."}</p>
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
              <FitOverview suggestion={latestSuggestion} />

              <Panel>
                <h2 className="text-base font-semibold">Job Description</h2>
                <p className="mt-4 max-h-[360px] overflow-auto whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{job.job_description}</p>
              </Panel>
            </>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-2">
            <Panel>
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold">Analysis</h2>
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
                <p className="text-sm text-muted-foreground">Run intelligence to extract structured responsibilities, skills, keywords, and interview topics.</p>
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

          <Button variant="ghost" onClick={() => queryClient.invalidateQueries({ queryKey: ["job", jobId] })}>
            <RefreshCw className="h-4 w-4" />
            Refresh job data
          </Button>
        </>
      ) : null}
    </div>
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

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="mb-2 font-medium">{title}</h3>
      {items.length ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <Badge key={item}>{item}</Badge>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground">None captured.</p>
      )}
    </div>
  );
}
