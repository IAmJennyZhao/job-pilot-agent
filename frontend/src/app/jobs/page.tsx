"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ExternalLink, Plus, Save } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { jobStatuses, type JobListItem, type JobStatus } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const jobSchema = z.object({
  company: z.string().min(1),
  role_title: z.string().min(1),
  job_url: z.string().url().or(z.literal("")).optional(),
  job_description: z.string().min(1),
  notes: z.string().optional()
});

type JobForm = z.infer<typeof jobSchema>;

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const { data: jobs = [], isLoading, error } = useQuery({
    queryKey: ["jobs", showArchived],
    queryFn: () => api.jobs(showArchived)
  });
  const form = useForm<JobForm>({
    resolver: zodResolver(jobSchema),
    defaultValues: {
      company: "",
      role_title: "",
      job_url: "",
      job_description: "",
      notes: ""
    }
  });

  const createMutation = useMutation({
    mutationFn: api.createJob,
    onSuccess: () => {
      form.reset();
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: JobStatus }) => api.updateJob(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const archiveMutation = useMutation({
    mutationFn: api.archiveJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const onSubmit = (values: JobForm) => {
    createMutation.mutate({
      ...values,
      job_url: values.job_url || null,
      notes: values.notes || null
    });
  };

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Job Tracker"
        description="Save job descriptions, track status, and keep notes ready for AI analysis."
      />

      <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
        <Panel>
          <div className="mb-4 flex items-center gap-2">
            <Plus className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">Add Job</h2>
          </div>
          <form className="grid gap-4" onSubmit={form.handleSubmit(onSubmit)}>
            <Field label="Company" error={form.formState.errors.company?.message}>
              <Input {...form.register("company")} />
            </Field>
            <Field label="Role title" error={form.formState.errors.role_title?.message}>
              <Input {...form.register("role_title")} />
            </Field>
            <Field label="Job URL" error={form.formState.errors.job_url?.message}>
              <Input {...form.register("job_url")} placeholder="https://..." />
            </Field>
            <Field label="Job description" error={form.formState.errors.job_description?.message}>
              <Textarea {...form.register("job_description")} className="min-h-44" />
            </Field>
            <Field label="Notes">
              <Textarea {...form.register("notes")} />
            </Field>
            {createMutation.error ? <p className="text-sm text-destructive">{(createMutation.error as Error).message}</p> : null}
            <Button type="submit" disabled={createMutation.isPending}>
              <Save className="h-4 w-4" />
              {createMutation.isPending ? "Saving..." : "Save job"}
            </Button>
          </form>
        </Panel>

        <Panel className="overflow-hidden">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold">Saved Jobs</h2>
              <Badge>{showArchived ? `${jobs.length} shown` : `${jobs.length} active`}</Badge>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-primary"
                checked={showArchived}
                onChange={(event) => setShowArchived(event.target.checked)}
              />
              Show archived
            </label>
          </div>
          {error ? <p className="text-sm text-destructive">{(error as Error).message}</p> : null}
          {isLoading ? <p className="text-sm text-muted-foreground">Loading jobs...</p> : null}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1120px] text-left text-sm">
              <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4">Company</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Fit</th>
                  <th className="py-2 pr-4">Top gaps</th>
                  <th className="py-2 pr-4">Job URL</th>
                  <th className="py-2 pr-4">Updated</th>
                  <th className="py-2 pr-4">Notes</th>
                  <th className="py-2 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <JobRow
                    key={job.id}
                    job={job}
                    onStatus={(status) => updateMutation.mutate({ id: job.id, status })}
                    onArchive={() => archiveMutation.mutate(job.id)}
                  />
                ))}
              </tbody>
            </table>
            {!jobs.length && !isLoading ? <p className="py-8 text-sm text-muted-foreground">No jobs saved yet.</p> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function JobRow({ job, onStatus, onArchive }: { job: JobListItem; onStatus: (status: JobStatus) => void; onArchive: () => void }) {
  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-3 pr-4 align-top font-medium">{job.company}</td>
      <td className="py-3 pr-4 align-top">
        <Link href={`/jobs/${job.id}`} className="font-medium text-primary">
          {job.role_title}
        </Link>
      </td>
      <td className="py-3 pr-4 align-top">
        <Select value={job.status} onChange={(event) => onStatus(event.target.value as JobStatus)}>
          {jobStatuses.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
      </td>
      <td className="py-3 pr-4 align-top">{job.fit_score ?? "--"}</td>
      <td className="py-3 pr-4 align-top">
        {job.top_gaps.length ? (
          <div className="grid gap-2">
            <div className="flex max-w-[260px] flex-wrap gap-1.5">
              {job.top_gaps.map((gap) => (
                <Badge key={gap} tone={job.top_gaps_source === "resume_match" ? "warn" : "neutral"}>
                  {gap}
                </Badge>
              ))}
            </div>
            <span className="text-xs text-muted-foreground">
              {job.top_gaps_source === "resume_match" ? "Resume match" : "Analysis"}
            </span>
          </div>
        ) : (
          <span className="text-muted-foreground">Not analyzed</span>
        )}
      </td>
      <td className="py-3 pr-4 align-top">
        {job.job_url ? (
          <a href={job.job_url} target="_blank" rel="noreferrer" title="Open job URL">
            <Button variant="secondary" size="icon">
              <ExternalLink className="h-4 w-4" />
            </Button>
          </a>
        ) : (
          <span className="text-muted-foreground">None</span>
        )}
      </td>
      <td className="py-3 pr-4 align-top text-muted-foreground">{formatDate(job.updated_at)}</td>
      <td className="py-3 pr-4 align-top">
        <div className="line-clamp-3 max-w-[240px] text-xs text-muted-foreground">{job.notes || "No notes"}</div>
      </td>
      <td className="py-3 pr-4 align-top">
        {job.status !== "Archived" ? (
          <Button variant="secondary" size="icon" onClick={onArchive} title="Archive job">
            <Archive className="h-4 w-4" />
          </Button>
        ) : null}
      </td>
    </tr>
  );
}
