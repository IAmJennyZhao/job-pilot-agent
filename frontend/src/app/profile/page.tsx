"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileSearch,
  FileText,
  Mail,
  Save,
  Search,
  Trash2,
  Upload,
  UserRound
} from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { CoverLetterTemplate, CoverageGapResponse, ResumeOption, ResumeProfile } from "@/lib/types";
import { cn, csvToList, formatDate, listToCsv } from "@/lib/utils";

type TabKey = "overview" | "resumes" | "templates" | "gaps";

const tabs: Array<{ key: TabKey; label: string; icon: React.ElementType }> = [
  { key: "overview", label: "Overview", icon: UserRound },
  { key: "resumes", label: "Resume Options", icon: FileText },
  { key: "templates", label: "Cover Letters", icon: Mail },
  { key: "gaps", label: "Coverage Gaps", icon: Search }
];

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = React.useState<TabKey>("overview");
  const { data: profile, isLoading, error } = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const { data: resumeOptions = [] } = useQuery({ queryKey: ["resume-options"], queryFn: api.resumeOptions });
  const { data: templates = [] } = useQuery({ queryKey: ["cover-letter-templates"], queryFn: api.coverLetterTemplates });

  const invalidateProfileAssets = () => {
    queryClient.invalidateQueries({ queryKey: ["profile"] });
    queryClient.invalidateQueries({ queryKey: ["resume-options"] });
    queryClient.invalidateQueries({ queryKey: ["cover-letter-templates"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Profile Library"
        description="Manage the aggregate profile, resume options, and reusable cover letter templates used during job review."
      />
      {error ? <Panel className="border-rose-200 bg-rose-50 text-sm text-rose-700">{(error as Error).message}</Panel> : null}
      {isLoading ? <Panel>Loading profile...</Panel> : null}
      <ProfileReadinessPanel profile={profile ?? null} resumeOptions={resumeOptions} templates={templates} />
      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition",
                active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-white text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>
      {activeTab === "overview" ? <OverviewTab profile={profile ?? null} onSaved={invalidateProfileAssets} /> : null}
      {activeTab === "resumes" ? <ResumeOptionsTab resumeOptions={resumeOptions} onChanged={invalidateProfileAssets} /> : null}
      {activeTab === "templates" ? <CoverLetterTemplatesTab templates={templates} onChanged={invalidateProfileAssets} /> : null}
      {activeTab === "gaps" ? <CoverageGapsTab /> : null}
    </div>
  );
}

function ProfileReadinessPanel({
  profile,
  resumeOptions,
  templates
}: {
  profile: ResumeProfile | null;
  resumeOptions: ResumeOption[];
  templates: CoverLetterTemplate[];
}) {
  const checks = [
    { label: "Aggregate profile", ready: Boolean(profile) },
    { label: "Profile skills", ready: Boolean(profile?.skills.length) },
    { label: "Ready resume", ready: resumeOptions.some((option) => option.status === "ready") },
    { label: "Cover template", ready: Boolean(templates.length) }
  ];
  const ready = checks.every((item) => item.ready);

  return (
    <Panel>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Application Asset Readiness</h2>
          <p className="mt-1 text-sm text-muted-foreground">Job review uses these assets for resume and template recommendations.</p>
        </div>
        <Badge tone={ready ? "good" : "warn"}>{ready ? "Ready" : "Needs assets"}</Badge>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        {checks.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-sm">
            {item.ready ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertCircle className="h-4 w-4 text-amber-600" />}
            {item.label}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function OverviewTab({ profile, onSaved }: { profile: ResumeProfile | null; onSaved: () => void }) {
  const [form, setForm] = React.useState(() => profileFormFromProfile(profile));
  React.useEffect(() => setForm(profileFormFromProfile(profile)), [profile]);
  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        name: form.name || null,
        target_roles: csvToList(form.target_roles),
        summary: form.summary || null,
        skills: csvToList(form.skills),
        skill_groups: parseSkillGroups(form.skill_groups),
        certifications: csvToList(form.certifications),
        resume_text: form.resume_text,
        experience: parseJsonList(form.experience_json, profile?.experience ?? []),
        projects: parseJsonList(form.projects_json, profile?.projects ?? []),
        education: parseJsonList(form.education_json, profile?.education ?? [])
      };
      return profile ? api.updateProfile(profile.id, payload) : api.saveProfile(payload);
    },
    onSuccess: onSaved
  });

  return (
    <Panel>
      <SectionHeader icon={UserRound} title={profile ? "Aggregate Profile" : "Create Aggregate Profile"} />
      <div className="grid gap-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="Name">
            <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </Field>
          <Field label="Target roles">
            <Input value={form.target_roles} onChange={(event) => setForm({ ...form, target_roles: event.target.value })} />
          </Field>
        </div>
        <Field label="Summary">
          <Textarea value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} />
        </Field>
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="Skills">
            <Textarea value={form.skills} onChange={(event) => setForm({ ...form, skills: event.target.value })} />
          </Field>
          <Field label="Skill groups">
            <Textarea value={form.skill_groups} onChange={(event) => setForm({ ...form, skill_groups: event.target.value })} />
          </Field>
        </div>
        <Field label="Certifications">
          <Textarea value={form.certifications} onChange={(event) => setForm({ ...form, certifications: event.target.value })} />
        </Field>
        <div className="grid gap-4 lg:grid-cols-3">
          <Field label="Experience">
            <Textarea className="min-h-48 font-mono text-xs" value={form.experience_json} onChange={(event) => setForm({ ...form, experience_json: event.target.value })} />
          </Field>
          <Field label="Projects">
            <Textarea className="min-h-48 font-mono text-xs" value={form.projects_json} onChange={(event) => setForm({ ...form, projects_json: event.target.value })} />
          </Field>
          <Field label="Education">
            <Textarea className="min-h-48 font-mono text-xs" value={form.education_json} onChange={(event) => setForm({ ...form, education_json: event.target.value })} />
          </Field>
        </div>
        <Field label="Raw resume text">
          <Textarea className="min-h-48" value={form.resume_text} onChange={(event) => setForm({ ...form, resume_text: event.target.value })} />
        </Field>
        {mutation.error ? <p className="text-sm text-destructive">{(mutation.error as Error).message}</p> : null}
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          <Save className="h-4 w-4" />
          {mutation.isPending ? "Saving..." : "Save profile"}
        </Button>
      </div>
    </Panel>
  );
}

function ResumeOptionsTab({ resumeOptions, onChanged }: { resumeOptions: ResumeOption[]; onChanged: () => void }) {
  const [file, setFile] = React.useState<File | null>(null);
  const importMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a PDF file first.");
      return api.importResumeOption(file);
    },
    onSuccess: () => {
      setFile(null);
      onChanged();
    }
  });
  const createMutation = useMutation({
    mutationFn: () =>
      api.createResumeOption({
        title: "New Resume Option",
        status: "draft",
        parsed_text: "",
        skills: [],
        skill_groups: [],
        target_roles: [],
        target_keywords: [],
        projects: [],
        experience: [],
        education: [],
        certifications: []
      }),
    onSuccess: onChanged
  });

  return (
    <div className="grid gap-4">
      <Panel>
        <SectionHeader icon={Upload} title="Import Resume PDF" />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Input type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <Button onClick={() => importMutation.mutate()} disabled={importMutation.isPending || !file}>
            <Upload className="h-4 w-4" />
            {importMutation.isPending ? "Importing..." : "Import PDF"}
          </Button>
          <Button variant="secondary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
            <FileText className="h-4 w-4" />
            New option
          </Button>
        </div>
        {importMutation.error ? <p className="mt-3 text-sm text-destructive">{(importMutation.error as Error).message}</p> : null}
      </Panel>
      {resumeOptions.length ? (
        resumeOptions.map((option) => <ResumeOptionEditor key={option.id} option={option} onChanged={onChanged} />)
      ) : (
        <Panel className="text-sm text-muted-foreground">No resume options yet.</Panel>
      )}
    </div>
  );
}

function ResumeOptionEditor({ option, onChanged }: { option: ResumeOption; onChanged: () => void }) {
  const [form, setForm] = React.useState(() => resumeFormFromOption(option));
  React.useEffect(() => setForm(resumeFormFromOption(option)), [option]);
  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateResumeOption(option.id, {
        title: form.title,
        candidate_name: form.candidate_name || null,
        status: form.status,
        summary: form.summary || null,
        target_roles: csvToList(form.target_roles),
        target_keywords: csvToList(form.target_keywords),
        skills: csvToList(form.skills),
        skill_groups: parseSkillGroups(form.skill_groups),
        certifications: csvToList(form.certifications),
        experience: parseJsonList(form.experience_json, option.experience),
        projects: parseJsonList(form.projects_json, option.projects),
        education: parseJsonList(form.education_json, option.education),
        parsed_text: form.parsed_text
      }),
    onSuccess: onChanged
  });
  const confirmMutation = useMutation({
    mutationFn: (merge: boolean) => api.confirmResumeOption(option.id, merge),
    onSuccess: onChanged
  });
  const deleteMutation = useMutation({ mutationFn: () => api.deleteResumeOption(option.id), onSuccess: onChanged });

  return (
    <Panel>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold">{option.title}</h2>
            <Badge tone={option.status === "ready" ? "good" : "warn"}>{option.status}</Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {option.source_filename ? `${option.source_filename} - ` : ""}
            Updated {formatDate(option.updated_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {option.source_filename ? (
            <a href={api.resumeOptionDownloadUrl(option.id)} className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm font-medium text-muted-foreground hover:text-foreground">
              <Download className="h-4 w-4" />
              PDF
            </a>
          ) : null}
          <Button variant="secondary" size="sm" onClick={() => confirmMutation.mutate(false)} disabled={confirmMutation.isPending}>
            <CheckCircle2 className="h-4 w-4" />
            Ready
          </Button>
          <Button variant="secondary" size="sm" onClick={() => confirmMutation.mutate(true)} disabled={confirmMutation.isPending}>
            <UserRound className="h-4 w-4" />
            Ready + merge
          </Button>
          <Button variant="ghost" size="sm" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="grid gap-4">
        <div className="grid gap-4 lg:grid-cols-3">
          <Field label="Title">
            <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          </Field>
          <Field label="Candidate name">
            <Input value={form.candidate_name} onChange={(event) => setForm({ ...form, candidate_name: event.target.value })} />
          </Field>
          <Field label="Status">
            <Select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as ResumeOption["status"] })}>
              <option value="draft">draft</option>
              <option value="ready">ready</option>
            </Select>
          </Field>
        </div>
        <Field label="Summary">
          <Textarea value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} />
        </Field>
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="Target roles">
            <Textarea value={form.target_roles} onChange={(event) => setForm({ ...form, target_roles: event.target.value })} />
          </Field>
          <Field label="Target keywords">
            <Textarea value={form.target_keywords} onChange={(event) => setForm({ ...form, target_keywords: event.target.value })} />
          </Field>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="Skills">
            <Textarea value={form.skills} onChange={(event) => setForm({ ...form, skills: event.target.value })} />
          </Field>
          <Field label="Skill groups">
            <Textarea value={form.skill_groups} onChange={(event) => setForm({ ...form, skill_groups: event.target.value })} />
          </Field>
        </div>
        <Field label="Certifications">
          <Textarea value={form.certifications} onChange={(event) => setForm({ ...form, certifications: event.target.value })} />
        </Field>
        <div className="grid gap-4 lg:grid-cols-3">
          <Field label="Experience">
            <Textarea className="min-h-48 font-mono text-xs" value={form.experience_json} onChange={(event) => setForm({ ...form, experience_json: event.target.value })} />
          </Field>
          <Field label="Projects">
            <Textarea className="min-h-48 font-mono text-xs" value={form.projects_json} onChange={(event) => setForm({ ...form, projects_json: event.target.value })} />
          </Field>
          <Field label="Education">
            <Textarea className="min-h-48 font-mono text-xs" value={form.education_json} onChange={(event) => setForm({ ...form, education_json: event.target.value })} />
          </Field>
        </div>
        <Field label="Parsed resume text">
          <Textarea className="min-h-56" value={form.parsed_text} onChange={(event) => setForm({ ...form, parsed_text: event.target.value })} />
        </Field>
        {saveMutation.error ? <p className="text-sm text-destructive">{(saveMutation.error as Error).message}</p> : null}
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Save className="h-4 w-4" />
          {saveMutation.isPending ? "Saving..." : "Save resume option"}
        </Button>
      </div>
    </Panel>
  );
}

function CoverLetterTemplatesTab({ templates, onChanged }: { templates: CoverLetterTemplate[]; onChanged: () => void }) {
  const createMutation = useMutation({
    mutationFn: () => api.createCoverLetterTemplate({ title: "New Cover Letter Template", target_roles: [], target_keywords: [], body: "" }),
    onSuccess: onChanged
  });
  return (
    <div className="grid gap-4">
      <Panel>
        <div className="flex items-center justify-between gap-3">
          <SectionHeader icon={Mail} title="Cover Letter Templates" />
          <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
            <Mail className="h-4 w-4" />
            New template
          </Button>
        </div>
      </Panel>
      {templates.length ? (
        templates.map((template) => <CoverLetterTemplateEditor key={template.id} template={template} onChanged={onChanged} />)
      ) : (
        <Panel className="text-sm text-muted-foreground">No cover letter templates yet.</Panel>
      )}
    </div>
  );
}

function CoverLetterTemplateEditor({ template, onChanged }: { template: CoverLetterTemplate; onChanged: () => void }) {
  const [form, setForm] = React.useState(() => ({
    title: template.title,
    target_roles: listToCsv(template.target_roles),
    target_keywords: listToCsv(template.target_keywords),
    body: template.body,
    notes: template.notes ?? ""
  }));
  React.useEffect(() => {
    setForm({
      title: template.title,
      target_roles: listToCsv(template.target_roles),
      target_keywords: listToCsv(template.target_keywords),
      body: template.body,
      notes: template.notes ?? ""
    });
  }, [template]);
  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateCoverLetterTemplate(template.id, {
        title: form.title,
        target_roles: csvToList(form.target_roles),
        target_keywords: csvToList(form.target_keywords),
        body: form.body,
        notes: form.notes || null
      }),
    onSuccess: onChanged
  });
  const deleteMutation = useMutation({ mutationFn: () => api.deleteCoverLetterTemplate(template.id), onSuccess: onChanged });
  return (
    <Panel>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{template.title}</h2>
          <p className="mt-1 text-xs text-muted-foreground">Updated {formatDate(template.updated_at)}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
      <div className="grid gap-4">
        <Field label="Title">
          <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
        </Field>
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="Target roles">
            <Textarea value={form.target_roles} onChange={(event) => setForm({ ...form, target_roles: event.target.value })} />
          </Field>
          <Field label="Target keywords">
            <Textarea value={form.target_keywords} onChange={(event) => setForm({ ...form, target_keywords: event.target.value })} />
          </Field>
        </div>
        <Field label="Body">
          <Textarea className="min-h-56" value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} />
        </Field>
        <Field label="Notes">
          <Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
        </Field>
        {saveMutation.error ? <p className="text-sm text-destructive">{(saveMutation.error as Error).message}</p> : null}
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Save className="h-4 w-4" />
          {saveMutation.isPending ? "Saving..." : "Save template"}
        </Button>
      </div>
    </Panel>
  );
}

function CoverageGapsTab() {
  const [result, setResult] = React.useState<CoverageGapResponse | null>(null);
  const mutation = useMutation({ mutationFn: api.generateCoverageGaps, onSuccess: setResult });
  return (
    <Panel>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <SectionHeader icon={FileSearch} title="Coverage Gaps" />
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          <Search className="h-4 w-4" />
          {mutation.isPending ? "Checking..." : "Generate gaps"}
        </Button>
      </div>
      {mutation.error ? <p className="mt-3 text-sm text-destructive">{(mutation.error as Error).message}</p> : null}
      {result ? (
        <div className="mt-5 grid gap-3">
          <p className="text-sm text-muted-foreground">
            {result.jobs_considered} recent jobs considered - {formatDate(result.generated_at)}
          </p>
          {result.gaps.length ? (
            result.gaps.map((gap) => (
              <div key={`${gap.asset_type}-${gap.title}`} className="rounded-md border border-border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={gap.asset_type === "resume" ? "neutral" : "warn"}>{gap.asset_type === "resume" ? "Resume" : "Cover letter"}</Badge>
                  <h3 className="text-sm font-semibold">{gap.title}</h3>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{gap.rationale}</p>
                <TagList items={gap.target_keywords} />
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No coverage gaps found.</p>
          )}
        </div>
      ) : null}
    </Panel>
  );
}

function SectionHeader({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4 text-primary" />
      <h2 className="text-base font-semibold">{title}</h2>
    </div>
  );
}

function TagList({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className="rounded-md border border-border bg-muted px-2 py-1 text-xs text-muted-foreground">
          {item}
        </span>
      ))}
    </div>
  );
}

function profileFormFromProfile(profile: ResumeProfile | null) {
  return {
    name: profile?.name ?? "",
    target_roles: listToCsv(profile?.target_roles),
    summary: profile?.summary ?? "",
    skills: listToCsv(profile?.skills),
    skill_groups: formatSkillGroups(profile?.skill_groups ?? []),
    certifications: listToCsv(profile?.certifications),
    experience_json: formatJson(profile?.experience ?? []),
    projects_json: formatJson(profile?.projects ?? []),
    education_json: formatJson(profile?.education ?? []),
    resume_text: profile?.resume_text ?? ""
  };
}

function resumeFormFromOption(option: ResumeOption) {
  return {
    title: option.title,
    candidate_name: option.candidate_name ?? "",
    status: option.status,
    summary: option.summary ?? "",
    target_roles: listToCsv(option.target_roles),
    target_keywords: listToCsv(option.target_keywords),
    skills: listToCsv(option.skills),
    skill_groups: formatSkillGroups(option.skill_groups),
    certifications: listToCsv(option.certifications),
    experience_json: formatJson(option.experience),
    projects_json: formatJson(option.projects),
    education_json: formatJson(option.education),
    parsed_text: option.parsed_text
  };
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function parseJsonList(value: string, fallback: Record<string, unknown>[]) {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function formatSkillGroups(groups: Array<{ category: string; skills: string[] }>) {
  return groups.map((group) => `${group.category}: ${group.skills.join(", ")}`).join("\n");
}

function parseSkillGroups(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [category, skills = ""] = line.includes(":") ? line.split(/:(.*)/).filter(Boolean) : ["Skills", line];
      return { category: category.trim() || "Skills", skills: csvToList(skills) };
    })
    .filter((group) => group.skills.length);
}
