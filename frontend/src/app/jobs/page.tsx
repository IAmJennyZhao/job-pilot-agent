"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ExternalLink, FileText, Plus, Save, Search, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
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
import { cn, csvToList, formatDate, listToCsv } from "@/lib/utils";

type IntakeState = {
  source_url: string;
  source_content: string;
};

type ReviewState = JobCreatePayload & {
  duplicateCount: number;
};

type HealthFilter = "" | "stale" | "missing-data";

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

const extractionSteps = [
  "Reading the source material",
  "Extracting company, role, location, and pay",
  "Paraphrasing responsibilities and core skills",
  "Checking for duplicate applications",
  "Preparing editable review fields"
];

function statusFromUrl(value: string | null): JobStatus | "" {
  if (!value) return "";
  return (jobStatuses as readonly string[]).includes(value) ? (value as JobStatus) : "";
}

function healthFromUrl(value: string | null): HealthFilter {
  if (value === "stale" || value === "missing-data") return value;
  return "";
}

function toApiHealthFilter(value: HealthFilter): "stale" | "missing_data" | "" {
  return value === "missing-data" ? "missing_data" : value;
}

function isHiddenStatus(status: JobStatus | "") {
  return status === "Archived" || status === "Ghosted";
}

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<JobStatus | "">("");
  const [healthFilter, setHealthFilter] = useState<HealthFilter>("");
  const [categoryFilter, setCategoryFilter] = useState<JobCategory | "">("");
  const [selectedJob, setSelectedJob] = useState<JobListItem | null>(null);
  const [intake, setIntake] = useState<IntakeState>({ source_url: "", source_content: "" });
  const [preview, setPreview] = useState<JobExtractPreview | null>(null);
  const [review, setReview] = useState<ReviewState | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const nextStatus = statusFromUrl(params.get("status"));
    setStatusFilter(nextStatus);
    setHealthFilter(healthFromUrl(params.get("health")));
    if (isHiddenStatus(nextStatus)) setShowArchived(true);
  }, []);

  const { data: jobs = [], isLoading, error } = useQuery({
    queryKey: ["jobs", showArchived, search, statusFilter, healthFilter, categoryFilter],
    queryFn: () =>
      api.jobs({
        includeArchived: showArchived || isHiddenStatus(statusFilter),
        search: search.trim() || undefined,
        status: statusFilter,
        category: categoryFilter,
        healthFilter: toApiHealthFilter(healthFilter)
      })
  });

  const extractMutation = useMutation({
    mutationFn: api.extractJobPreview,
    onSuccess: (data) => {
      setPreview(data);
      setReview(reviewFromPreview(data));
    }
  });

  const createMutation = useMutation({
    mutationFn: api.createJob,
    onSuccess: () => {
      setIntake({ source_url: "", source_content: "" });
      setPreview(null);
      setReview(null);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<JobCreatePayload> & { status?: JobStatus } }) => api.updateJob(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => api.updateJob(id, { status: "Archived" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const startManualFallback = () => {
    setPreview(null);
    setReview(blankReview(intake));
  };

  const saveReview = () => {
    if (!review) return;
    createMutation.mutate(cleanReview(review, intake.source_url));
  };

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Job Tracker"
        description="Extract a job from a posting, review it, then manage the application pipeline from a searchable tracker."
      />

      <div className={cn("grid gap-4 transition-[grid-template-columns] duration-500 ease-in-out", review ? "xl:grid-cols-2" : "xl:grid-cols-[430px_1fr]")}>
        <Panel>
          <div className="mb-4 flex items-center gap-2">
            <Plus className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">Add Job</h2>
          </div>

          <div className="grid gap-4">
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
                className="min-h-44"
                placeholder="Paste the job description or full job page text."
              />
            </Field>
            {extractMutation.error ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <div>{(extractMutation.error as Error).message}</div>
                <Button className="mt-3" size="sm" variant="secondary" onClick={startManualFallback}>
                  Use manual fallback
                </Button>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() =>
                  extractMutation.mutate({
                    source_url: intake.source_url || null,
                    source_content: intake.source_content || null
                  })
                }
                disabled={extractMutation.isPending || (!intake.source_url.trim() && !intake.source_content.trim())}
              >
                <Sparkles className="h-4 w-4" />
                {extractMutation.isPending ? "Extracting..." : "Extract fields"}
              </Button>
              <Button variant="secondary" onClick={startManualFallback}>
                Manual entry
              </Button>
            </div>
            <ProcessSteps active={extractMutation.isPending} steps={extractionSteps} />
          </div>

          {review ? (
            <div className="mt-6 border-t border-border pt-5">
              <ReviewEditor review={review} onChange={setReview} preview={preview} />
              {createMutation.error ? <p className="mt-3 text-sm text-destructive">{(createMutation.error as Error).message}</p> : null}
              <Button className="mt-4 w-full" onClick={saveReview} disabled={createMutation.isPending || !review.company.trim() || !review.role_title.trim()}>
                <Save className="h-4 w-4" />
                {createMutation.isPending ? "Saving..." : "Save reviewed job"}
              </Button>
            </div>
          ) : null}
        </Panel>

        <Panel className="overflow-hidden">
          <div className="mb-4 grid gap-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-semibold">Applications</h2>
                <Badge>{jobs.length} shown</Badge>
              </div>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border text-primary"
                  checked={showArchived}
                  onChange={(event) => setShowArchived(event.target.checked)}
                />
                Show hidden
              </label>
            </div>
            <div className="grid gap-2 lg:grid-cols-[1fr_180px_190px_220px]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="pl-9"
                  placeholder="Search company, role, notes, status, URL..."
                />
              </div>
              <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as JobStatus | "")}>
                <option value="">All statuses</option>
                {jobStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </Select>
              <Select value={healthFilter} onChange={(event) => setHealthFilter(event.target.value as HealthFilter)}>
                <option value="">All health</option>
                <option value="stale">Stale</option>
                <option value="missing-data">Missing data</option>
              </Select>
              <Select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value as JobCategory | "")}>
                <option value="">All categories</option>
                {jobCategories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          {error ? <p className="text-sm text-destructive">{(error as Error).message}</p> : null}
          {isLoading ? <p className="text-sm text-muted-foreground">Loading jobs...</p> : null}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1280px] text-left text-sm">
              <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4">Company</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 pr-4">Status</th>
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
                    onSelect={() => setSelectedJob(job)}
                    onStatus={(nextStatus) => updateMutation.mutate({ id: job.id, payload: { status: nextStatus } })}
                    onCategory={(nextCategory) => updateMutation.mutate({ id: job.id, payload: { category: nextCategory } })}
                    onPay={(payload) => updateMutation.mutate({ id: job.id, payload })}
                    onArchive={() => archiveMutation.mutate(job.id)}
                  />
                ))}
              </tbody>
            </table>
            {!jobs.length && !isLoading ? <p className="py-8 text-sm text-muted-foreground">No jobs match the current filters.</p> : null}
          </div>
        </Panel>
      </div>

      {selectedJob ? <JobDrawer job={selectedJob} onClose={() => setSelectedJob(null)} /> : null}
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
    status: review.status,
    status_note: review.status_note,
    notes: review.notes?.trim() || null,
    extraction_confidence: review.extraction_confidence,
    extraction_warnings: review.extraction_warnings
  };
}

function ReviewEditor({
  review,
  onChange,
  preview
}: {
  review: ReviewState;
  onChange: (next: ReviewState) => void;
  preview: JobExtractPreview | null;
}) {
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
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={review.extraction_confidence && review.extraction_confidence >= 80 ? "good" : "warn"}>
          Confidence {review.extraction_confidence ?? "manual"}
        </Badge>
        {review.duplicateCount ? <Badge tone="warn">{review.duplicateCount} possible duplicate</Badge> : null}
      </div>
      {preview?.duplicate_candidates.length ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {preview.duplicate_candidates.map((candidate) => (
            <div key={candidate.id}>
              Possible duplicate:{" "}
              <Link href={`/jobs/${candidate.id}`} className="font-medium underline">
                {candidate.company} - {candidate.role_title}
              </Link>
            </div>
          ))}
        </div>
      ) : null}
      {(review.extraction_warnings ?? []).length ? (
        <div className="grid gap-1 text-xs text-amber-700">
          {(review.extraction_warnings ?? []).map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      ) : null}
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Company">
          <Input value={review.company} onChange={(event) => set("company", event.target.value)} />
        </Field>
        <Field label="Role title">
          <Input value={review.role_title} onChange={(event) => set("role_title", event.target.value)} />
        </Field>
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
      </div>
      <Field label="Location">
        <Input value={review.location ?? ""} onChange={(event) => set("location", event.target.value)} />
      </Field>
      <Field label="Summary">
        <Textarea value={review.summary ?? ""} onChange={(event) => set("summary", event.target.value)} />
      </Field>
      <Field label="Main responsibilities">
        <Textarea value={listToCsv(review.responsibilities)} onChange={(event) => set("responsibilities", csvToList(event.target.value))} />
      </Field>
      <Field label="Skills">
        <Textarea value={listToCsv(review.required_skills)} onChange={(event) => set("required_skills", csvToList(event.target.value))} />
      </Field>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Pay minimum">
          <Input type="number" value={review.pay_min ?? ""} onChange={(event) => set("pay_min", event.target.value ? Number(event.target.value) : null)} />
        </Field>
        <Field label="Pay maximum">
          <Input type="number" value={review.pay_max ?? ""} onChange={(event) => set("pay_max", event.target.value ? Number(event.target.value) : null)} />
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
      <Field label="Benefits">
        <Textarea value={listToCsv(review.benefits ?? [])} onChange={(event) => set("benefits", csvToList(event.target.value))} />
      </Field>
      <Field label="Notes">
        <Textarea value={review.notes ?? ""} onChange={(event) => set("notes", event.target.value)} />
      </Field>
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
    </div>
  );
}

function JobRow({
  job,
  onStatus,
  onCategory,
  onPay,
  onArchive,
  onSelect
}: {
  job: JobListItem;
  onStatus: (status: JobStatus) => void;
  onCategory: (category: JobCategory) => void;
  onPay: (payload: Partial<JobCreatePayload>) => void;
  onArchive: () => void;
  onSelect: () => void;
}) {
  const source = job.links.find((link) => link.kind === "source") ?? job.links[0];
  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-3 pr-4 align-top font-medium">{job.company}</td>
      <td className="py-3 pr-4 align-top">
        <button className="text-left font-medium text-primary" onClick={onSelect}>
          {job.role_title}
        </button>
        {job.summary ? <div className="mt-1 line-clamp-2 max-w-[300px] text-xs text-muted-foreground">{job.summary}</div> : null}
      </td>
      <td className="py-3 pr-4 align-top">
        <Select value={job.category} onChange={(event) => onCategory(event.target.value as JobCategory)} className="min-w-48">
          {jobCategories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </Select>
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
      <td className="py-3 pr-4 align-top text-muted-foreground">
        <div>{job.location || "Unknown"}</div>
        <div className="text-xs">{job.remote_type || "Unknown"}</div>
      </td>
      <td className="py-3 pr-4 align-top text-muted-foreground">
        <PayEditor job={job} onSave={onPay} />
      </td>
      <td className="py-3 pr-4 align-top">
        {source ? (
          <a href={source.url} target="_blank" rel="noreferrer" title="Open source link">
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
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={onSelect}>
            Details
          </Button>
          {job.status !== "Archived" && job.status !== "Ghosted" ? (
            <Button variant="secondary" size="icon" onClick={onArchive} title="Archive job">
              <Archive className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function PayEditor({ job, onSave }: { job: JobListItem; onSave: (payload: Partial<JobCreatePayload>) => void }) {
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

  const save = () => {
    onSave({
      pay_min: draft.pay_min,
      pay_max: draft.pay_max,
      pay_currency: draft.pay_currency.trim() || null,
      pay_period: draft.pay_period,
      pay_raw: draft.pay_raw.trim() || null
    });
    setIsOpen(false);
  };

  return (
    <div className="relative min-w-48">
      <button className="text-left" onClick={() => setIsOpen((current) => !current)}>
        <div className="font-medium text-foreground">{formatPay(job)}</div>
        <div className="text-xs text-muted-foreground">{formatAnnualPay(job)}</div>
      </button>
      {isOpen ? (
        <div className="absolute right-0 z-20 mt-2 w-80 rounded-md border border-border bg-white p-3 shadow-xl">
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Min">
                <Input type="number" value={draft.pay_min ?? ""} onChange={(event) => setDraft((current) => ({ ...current, pay_min: event.target.value ? Number(event.target.value) : null }))} />
              </Field>
              <Field label="Max">
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
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setIsOpen(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={save}>
                <Save className="h-4 w-4" />
                Save
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function JobDrawer({ job, onClose }: { job: JobListItem; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-30 bg-black/20" onClick={onClose}>
      <aside
        className="ml-auto h-full w-full max-w-xl overflow-y-auto border-l border-border bg-white p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm text-muted-foreground">{job.company}</div>
            <h2 className="mt-1 text-xl font-semibold">{job.role_title}</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} title="Close drawer">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge>{job.status}</Badge>
          <Badge>{job.category}</Badge>
          {job.extraction_confidence !== null ? <Badge tone="good">Confidence {job.extraction_confidence}</Badge> : null}
        </div>
        {job.summary ? <p className="mt-4 text-sm leading-6 text-muted-foreground">{job.summary}</p> : null}
        <div className="mt-4 grid gap-3 rounded-md border border-border bg-muted/40 p-3 text-sm">
          <InfoRow label="Location" value={[job.location, job.remote_type].filter(Boolean).join(" - ") || "Unknown"} />
          <InfoRow label="Pay" value={formatPay(job)} />
          <InfoRow label="Annual" value={formatAnnualPay(job)} />
        </div>
        <Link href={`/jobs/${job.id}`} className="mt-4 block">
          <Button className="h-12 w-full text-sm">
            <FileText className="h-4 w-4" />
            View Full Details
          </Button>
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
        <div className="mt-6 flex gap-2">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </aside>
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
    <div className="rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
      {steps[index]}
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
