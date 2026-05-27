"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain, FileText, Pencil, RefreshCw, Save, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { jobStatuses, type JobStatus } from "@/lib/types";
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

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
    }
  });

  const suggestMutation = useMutation({
    mutationFn: () => api.suggestResume(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
    }
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
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div>
                  <div className="flex flex-wrap gap-2">
                    <Badge>{job.status}</Badge>
                    {job.fit_score !== null ? <Badge tone={job.fit_score >= 75 ? "good" : job.fit_score >= 50 ? "warn" : "bad"}>Fit {job.fit_score}</Badge> : null}
                  </div>
                  <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{job.notes || "No notes yet."}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => analyzeMutation.mutate()} disabled={analyzeMutation.isPending}>
                    <Brain className="h-4 w-4" />
                    {analyzeMutation.isPending ? "Analyzing..." : "Analyze JD"}
                  </Button>
                  <Button variant="secondary" onClick={() => suggestMutation.mutate()} disabled={suggestMutation.isPending}>
                    <FileText className="h-4 w-4" />
                    {suggestMutation.isPending ? "Matching..." : "Suggest resume"}
                  </Button>
                </div>
              </div>
            )}
            {analyzeMutation.error ? <p className="mt-3 text-sm text-destructive">{(analyzeMutation.error as Error).message}</p> : null}
            {suggestMutation.error ? <p className="mt-3 text-sm text-destructive">{(suggestMutation.error as Error).message}</p> : null}
          </Panel>

          {!isEditing ? (
            <Panel>
              <h2 className="text-base font-semibold">Job Description</h2>
              <p className="mt-4 max-h-[360px] overflow-auto whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{job.job_description}</p>
            </Panel>
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
                <p className="text-sm text-muted-foreground">Run analysis to extract structured responsibilities, skills, keywords, and interview topics.</p>
              )}
            </Panel>

            <Panel>
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-base font-semibold">Resume Match</h2>
                {job.latest_resume_suggestion ? <Badge tone="good">Fit {job.latest_resume_suggestion.fit_score}</Badge> : <Badge>Not run</Badge>}
              </div>
              {job.latest_resume_suggestion ? (
                <div className="grid gap-4 text-sm">
                  <List title="Matched Skills" items={job.latest_resume_suggestion.matched_skills} />
                  <List title="Missing Skills" items={job.latest_resume_suggestion.missing_skills} />
                  <List title="Weak Skills" items={job.latest_resume_suggestion.weak_skills} />
                  <List title="Keywords" items={job.latest_resume_suggestion.keyword_suggestions} />
                  <div>
                    <h3 className="mb-2 font-medium">Bullet Suggestions</h3>
                    <div className="grid gap-3">
                      {job.latest_resume_suggestion.bullet_suggestions.map((item, index) => (
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
                <p className="text-sm text-muted-foreground">Create an active profile, then run resume suggestions for this job.</p>
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
