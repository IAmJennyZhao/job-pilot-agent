"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  FileSearch,
  FileText,
  Mail,
  Pencil,
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
import { useDraft } from "@/lib/use-draft";
import { RecordEditor } from "@/components/ui/record-editor";
import { cn, csvToList, formatDate, listToCsv } from "@/lib/utils";

type TabKey = "base" | "resumes" | "templates" | "coverage";

const tabs: Array<{ key: TabKey; label: string; icon: React.ElementType }> = [
  { key: "base", label: "Base Profile", icon: UserRound },
  { key: "resumes", label: "Resume Variants", icon: FileText },
  { key: "templates", label: "Cover Letters", icon: Mail },
  { key: "coverage", label: "Coverage Audit", icon: Search }
];

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = React.useState<TabKey>("base");
  const { data: profile, isLoading, error } = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const { data: resumeOptions = [], isLoading: resumesLoading, error: resumesError } = useQuery({ queryKey: ["resume-options"], queryFn: api.resumeOptions });
  const { data: templates = [], isLoading: templatesLoading, error: templatesError } = useQuery({ queryKey: ["cover-letter-templates"], queryFn: api.coverLetterTemplates });

  const invalidateProfileAssets = () => {
    queryClient.invalidateQueries({ queryKey: ["profile"] });
    queryClient.invalidateQueries({ queryKey: ["resume-options"] });
    queryClient.invalidateQueries({ queryKey: ["cover-letter-templates"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Application Assets"
        description="Base profile, resume variants, cover letter templates, and coverage audit."
      />
      {error ? <Panel className="border-destructive/25 bg-destructive/10 text-sm text-destructive">{(error as Error).message}</Panel> : null}
      {isLoading ? <Panel>Loading application assets...</Panel> : null}
      {resumesError || templatesError ? <Panel><div role="alert">Could not load assets: {((resumesError || templatesError) as Error).message}</div></Panel> : null}
      {!isLoading && !resumesLoading && !templatesLoading && !error && !resumesError && !templatesError ? <ReadinessStrip profile={profile ?? null} resumeOptions={resumeOptions} templates={templates} onSelect={setActiveTab} /> : null}
      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              aria-pressed={active}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition",
                active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card-strong/75 text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>
      {activeTab === "base" && !isLoading && !error ? <BaseProfileTab profile={profile ?? null} onSaved={invalidateProfileAssets} /> : null}
      {activeTab === "resumes" && !resumesLoading && !resumesError ? <ResumeVariantsTab resumeOptions={resumeOptions} onChanged={invalidateProfileAssets} /> : null}
      {activeTab === "templates" && !templatesLoading && !templatesError ? <CoverLetterTemplatesTab templates={templates} onChanged={invalidateProfileAssets} /> : null}
      {activeTab === "coverage" ? <CoverageAuditTab /> : null}
    </div>
  );
}

function ReadinessStrip({
  profile,
  resumeOptions,
  templates,
  onSelect
}: {
  profile: ResumeProfile | null;
  resumeOptions: ResumeOption[];
  templates: CoverLetterTemplate[];
  onSelect: (tab: TabKey) => void;
}) {
  const checks = [
    { tab: "base" as TabKey, label: "Base profile", ready: Boolean(profile) },
    { tab: "base" as TabKey, label: "Skills", ready: Boolean(profile?.skills.length) },
    { tab: "resumes" as TabKey, label: "Ready resume", ready: resumeOptions.some((option) => option.status === "ready") },
    { tab: "templates" as TabKey, label: "Cover template", ready: Boolean(templates.length) }
  ];
  const ready = checks.every((item) => item.ready);
  const StatusIcon = ready ? CheckCircle2 : AlertCircle;

  return (
    <Panel className="p-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-2">
          <StatusIcon className={cn("h-4 w-4", ready ? "text-success-foreground" : "text-warning-foreground")} />
          <span className="text-sm font-semibold">{ready ? "Ready for job review" : "Needs assets"}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {checks.map((item) => (
            <button type="button" onClick={() => onSelect(item.tab)}
              key={item.label}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium",
                item.ready ? "border-success-foreground/20 bg-success text-success-foreground" : "border-warning-foreground/20 bg-warning text-warning-foreground"
              )}
            >
              {item.ready ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function BaseProfileTab({ profile, onSaved }: { profile: ResumeProfile | null; onSaved: () => void }) {
  const draft = useDraft("base-profile", profileFormFromProfile(profile));
  const { value: form, setValue: setForm } = draft;
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
    onSuccess: () => { draft.clear(); onSaved(); }
  });

  return (
    <Panel><fieldset disabled={mutation.isPending} className="min-w-0">
      <SectionHeader icon={UserRound} title={profile ? "Base Profile" : "Create Base Profile"} />
      <div className="mt-4 grid gap-4">
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
          <Field label="Certifications">
            <Textarea value={form.certifications} onChange={(event) => setForm({ ...form, certifications: event.target.value })} />
          </Field>
        </div>
        <AdvancedDetails>
          <Field label="Skill groups">
            <Textarea value={form.skill_groups} onChange={(event) => setForm({ ...form, skill_groups: event.target.value })} />
          </Field>
          <div className="grid gap-4 lg:grid-cols-3">
            <RecordEditor title="Experience" value={form.experience_json} onChange={value => setForm({ ...form, experience_json: value })} />
            <RecordEditor title="Projects" value={form.projects_json} onChange={value => setForm({ ...form, projects_json: value })} />
            <RecordEditor title="Education" value={form.education_json} onChange={value => setForm({ ...form, education_json: value })} />
          </div>
          <Field label="Raw resume text">
            <Textarea className="min-h-48" value={form.resume_text} onChange={(event) => setForm({ ...form, resume_text: event.target.value })} />
          </Field>
        </AdvancedDetails>
        <DraftNotice dirty={draft.dirty} storageError={draft.storageError} saved={mutation.isSuccess} />
        {mutation.error ? <p className="text-sm text-destructive">{(mutation.error as Error).message}</p> : null}
        <Button className="justify-self-start" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          <Save className="h-4 w-4" />
          {mutation.isPending ? "Saving..." : "Save profile"}
        </Button>
      </div>
    </fieldset></Panel>
  );
}

function ResumeVariantsTab({ resumeOptions, onChanged }: { resumeOptions: ResumeOption[]; onChanged: () => void }) {
  const [file, setFile] = React.useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = React.useState(0);
  const [expandedResumeId, setExpandedResumeId] = React.useState<string | null>(null);
  const pendingResumeId = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (!resumeOptions.length) {
      if (!pendingResumeId.current) setExpandedResumeId(null);
      return;
    }
    if (pendingResumeId.current) {
      if (resumeOptions.some((option) => option.id === pendingResumeId.current)) {
        setExpandedResumeId(pendingResumeId.current);
        pendingResumeId.current = null;
      }
      return;
    }
    if (!expandedResumeId || !resumeOptions.some((option) => option.id === expandedResumeId)) {
      setExpandedResumeId(resumeOptions[0].id);
    }
  }, [expandedResumeId, resumeOptions]);

  const importMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a PDF file first.");
      return api.importResumeOption(file);
    },
    onSuccess: (option) => {
      pendingResumeId.current = option.id;
      setExpandedResumeId(option.id);
      setFile(null);
      setFileInputKey((value) => value + 1);
      onChanged();
    }
  });
  const createMutation = useMutation({
    mutationFn: () =>
      api.createResumeOption({
        title: "New Resume Variant",
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
    onSuccess: (option) => {
      pendingResumeId.current = option.id;
      setExpandedResumeId(option.id);
      onChanged();
    }
  });

  return (
    <div className="grid gap-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <SectionHeader icon={Upload} title="Resume Variants" />
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            aria-label="Resume PDF"
            key={fileInputKey}
            className="sm:w-72"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <Button onClick={() => importMutation.mutate()} disabled={importMutation.isPending || !file}>
            <Upload className="h-4 w-4" />
            {importMutation.isPending ? "Importing..." : "Import PDF"}
          </Button>
          <Button variant="secondary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
            <FileText className="h-4 w-4" />
            New variant
          </Button>
        </div>
      </div>
      {createMutation.error ? <p role="alert" className="text-destructive">{createMutation.error.message}</p> : null}
      {importMutation.error ? <p className="text-sm text-destructive">{(importMutation.error as Error).message}</p> : null}
      {resumeOptions.length ? (
        resumeOptions.map((option) =>
          option.id === expandedResumeId ? (
            <ResumeOptionEditor
              key={option.id}
              option={option}
              onChanged={onChanged}
              onDeleted={() => setExpandedResumeId(null)}
            />
          ) : (
            <ResumeOptionCard
              key={option.id}
              option={option}
              onEdit={() => setExpandedResumeId(option.id)}
              onChanged={onChanged}
            />
          )
        )
      ) : (
        <Panel className="text-sm text-muted-foreground">No resume variants yet.</Panel>
      )}
    </div>
  );
}

function ResumeOptionCard({
  option,
  onEdit,
  onChanged
}: {
  option: ResumeOption;
  onEdit: () => void;
  onChanged: () => void;
}) {
  const draft = useDraft(`resume-${option.id}`, resumeFormFromOption(option));
  const confirmMutation = useMutation({
    mutationFn: () => api.confirmResumeOption(option.id, false),
    onSuccess: onChanged
  });
  const deleteMutation = useMutation({ mutationFn: () => api.deleteResumeOption(option.id), onSuccess: onChanged });

  const deleteOption = () => {
    if (window.confirm(`Delete ${option.title}? This cannot be undone.`)) {
      deleteMutation.mutate();
    }
  };

  return (
    <Panel className="p-4">
      {confirmMutation.error || deleteMutation.error ? <p role="alert" className="text-destructive">{((confirmMutation.error || deleteMutation.error) as Error).message}</p> : null}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <AssetHeading
          title={option.title}
          badge={<Badge tone={option.status === "ready" ? "good" : "warn"}>{option.status}</Badge>}
          meta={`${option.source_filename ? `${option.source_filename} - ` : ""}Updated ${formatDate(option.updated_at)}`}
        />
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={onEdit}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => confirmMutation.mutate()}
            disabled={confirmMutation.isPending || option.status === "ready" || draft.dirty}
          >
            <CheckCircle2 className="h-4 w-4" />
            Ready
          </Button>
          {option.source_filename ? (
            <a href={api.resumeOptionDownloadUrl(option.id)} className="inline-flex h-8 items-center gap-2 rounded-md border border-border bg-secondary px-3 text-xs font-medium text-secondary-foreground hover:border-primary/35 hover:bg-accent">
              <Download className="h-4 w-4" />
              PDF
            </a>
          ) : null}
          <Button variant="ghost" size="sm" onClick={deleteOption} disabled={deleteMutation.isPending}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>
      {draft.dirty ? <p className="mt-2 text-sm">Unsaved draft available. Edit and save it before marking ready.</p> : null}
      <div className="mt-3 grid gap-2">
        <PreviewTags label="Roles" items={option.target_roles} />
        <PreviewTags label="Skills/keywords" items={[...option.skills, ...option.target_keywords]} />
      </div>
    </Panel>
  );
}

function ResumeOptionEditor({
  option,
  onChanged,
  onDeleted
}: {
  option: ResumeOption;
  onChanged: () => void;
  onDeleted: () => void;
}) {
  const draft = useDraft(`resume-${option.id}`, resumeFormFromOption(option));
  const { value: form, setValue: setForm } = draft;
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
    onSuccess: () => { draft.clear(); onChanged(); }
  });
  const confirmMutation = useMutation({
    mutationFn: async (merge: boolean) => {
      await saveMutation.mutateAsync();
      return api.confirmResumeOption(option.id, merge);
    },
    onSuccess: onChanged
  });
  const deleteMutation = useMutation({
    mutationFn: () => api.deleteResumeOption(option.id),
    onSuccess: () => {
      onDeleted();
      onChanged();
    }
  });

  const deleteOption = () => {
    if (window.confirm(`Delete ${option.title}? This cannot be undone.`)) {
      deleteMutation.mutate();
    }
  };

  return (
    <Panel><fieldset disabled={saveMutation.isPending || confirmMutation.isPending || deleteMutation.isPending} className="min-w-0">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <AssetHeading
          title={option.title}
          badge={<Badge tone={option.status === "ready" ? "good" : "warn"}>{option.status}</Badge>}
          meta={`${option.source_filename ? `${option.source_filename} - ` : ""}Updated ${formatDate(option.updated_at)}`}
        />
        <div className="flex flex-wrap gap-2">
          {option.source_filename ? (
            <a href={api.resumeOptionDownloadUrl(option.id)} className="inline-flex h-8 items-center gap-2 rounded-md border border-border bg-secondary px-3 text-xs font-medium text-secondary-foreground hover:border-primary/35 hover:bg-accent">
              <Download className="h-4 w-4" />
              PDF
            </a>
          ) : null}
          <Button variant="secondary" size="sm" onClick={() => confirmMutation.mutate(false)} disabled={confirmMutation.isPending || saveMutation.isPending || (!draft.dirty && option.status === "ready")}>
            <CheckCircle2 className="h-4 w-4" />
            Save & mark ready
          </Button>
          <Button variant="secondary" size="sm" onClick={() => confirmMutation.mutate(true)} disabled={confirmMutation.isPending || saveMutation.isPending}>
            <UserRound className="h-4 w-4" />
            Save, mark ready & merge
          </Button>
          <Button variant="ghost" size="sm" onClick={deleteOption} disabled={deleteMutation.isPending}>
            <Trash2 className="h-4 w-4" />
            Delete
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
        <Field label="Skills">
          <Textarea value={form.skills} onChange={(event) => setForm({ ...form, skills: event.target.value })} />
        </Field>
        <AdvancedDetails>
          <div className="grid gap-4 lg:grid-cols-2">
            <Field label="Skill groups">
              <Textarea value={form.skill_groups} onChange={(event) => setForm({ ...form, skill_groups: event.target.value })} />
            </Field>
            <Field label="Certifications">
              <Textarea value={form.certifications} onChange={(event) => setForm({ ...form, certifications: event.target.value })} />
            </Field>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <RecordEditor title="Experience" value={form.experience_json} onChange={value => setForm({ ...form, experience_json: value })} />
            <RecordEditor title="Projects" value={form.projects_json} onChange={value => setForm({ ...form, projects_json: value })} />
            <RecordEditor title="Education" value={form.education_json} onChange={value => setForm({ ...form, education_json: value })} />
          </div>
          <Field label="Parsed resume text">
            <Textarea className="min-h-56" value={form.parsed_text} onChange={(event) => setForm({ ...form, parsed_text: event.target.value })} />
          </Field>
        </AdvancedDetails>
        {confirmMutation.error || deleteMutation.error ? <p role="alert" className="text-sm text-destructive">{((confirmMutation.error || deleteMutation.error) as Error).message}</p> : null}
        <DraftNotice dirty={draft.dirty} storageError={draft.storageError} saved={saveMutation.isSuccess} />
        {saveMutation.error ? <p className="text-sm text-destructive">{(saveMutation.error as Error).message}</p> : null}
        <Button className="justify-self-start" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || confirmMutation.isPending}>
          <Save className="h-4 w-4" />
          {saveMutation.isPending ? "Saving..." : "Save resume variant"}
        </Button>
      </div>
    </fieldset></Panel>
  );
}

function CoverLetterTemplatesTab({ templates, onChanged }: { templates: CoverLetterTemplate[]; onChanged: () => void }) {
  const [expandedTemplateId, setExpandedTemplateId] = React.useState<string | null>(null);
  const pendingTemplateId = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (!expandedTemplateId) return;
    if (pendingTemplateId.current) {
      if (templates.some((template) => template.id === pendingTemplateId.current)) {
        setExpandedTemplateId(pendingTemplateId.current);
        pendingTemplateId.current = null;
      }
      return;
    }
    if (!templates.some((template) => template.id === expandedTemplateId)) {
      setExpandedTemplateId(null);
    }
  }, [expandedTemplateId, templates]);

  const createMutation = useMutation({
    mutationFn: () => api.createCoverLetterTemplate({ title: "New Cover Letter Template", target_roles: [], target_keywords: [], body: "" }),
    onSuccess: (template) => {
      pendingTemplateId.current = template.id;
      setExpandedTemplateId(template.id);
      onChanged();
    }
  });
  return (
    <div className="grid gap-4">
      <Panel>
        <div className="flex items-center justify-between gap-3">
          <SectionHeader icon={Mail} title="Cover Letters" />
          <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
            <Mail className="h-4 w-4" />
            New template
          </Button>
        </div>
      </Panel>
      {createMutation.error ? <p role="alert" className="text-destructive">{createMutation.error.message}</p> : null}
      {templates.length ? (
        templates.map((template) =>
          template.id === expandedTemplateId ? (
            <CoverLetterTemplateEditor
              key={template.id}
              template={template}
              onChanged={onChanged}
              onDeleted={() => setExpandedTemplateId(null)}
            />
          ) : (
            <CoverLetterTemplateCard
              key={template.id}
              template={template}
              onEdit={() => setExpandedTemplateId(template.id)}
              onChanged={onChanged}
            />
          )
        )
      ) : (
        <Panel className="text-sm text-muted-foreground">No cover letter templates yet.</Panel>
      )}
    </div>
  );
}

function CoverLetterTemplateCard({
  template,
  onEdit,
  onChanged
}: {
  template: CoverLetterTemplate;
  onEdit: () => void;
  onChanged: () => void;
}) {
  const deleteMutation = useMutation({ mutationFn: () => api.deleteCoverLetterTemplate(template.id), onSuccess: onChanged });

  const deleteTemplate = () => {
    if (window.confirm(`Delete ${template.title}? This cannot be undone.`)) {
      deleteMutation.mutate();
    }
  };

  return (
    <Panel className="p-4">
      {deleteMutation.error ? <p role="alert" className="text-destructive">{deleteMutation.error.message}</p> : null}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <AssetHeading title={template.title} meta={`Updated ${formatDate(template.updated_at)}`} />
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={onEdit}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          <Button variant="ghost" size="sm" onClick={deleteTemplate} disabled={deleteMutation.isPending}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>
      <div className="mt-3 grid gap-2">
        <PreviewTags label="Roles" items={template.target_roles} />
        <PreviewTags label="Keywords" items={template.target_keywords} />
      </div>
    </Panel>
  );
}

function CoverLetterTemplateEditor({
  template,
  onChanged,
  onDeleted
}: {
  template: CoverLetterTemplate;
  onChanged: () => void;
  onDeleted: () => void;
}) {
  const draft = useDraft(`template-${template.id}`, {
    title: template.title,
    target_roles: listToCsv(template.target_roles),
    target_keywords: listToCsv(template.target_keywords),
    body: template.body,
    notes: template.notes ?? ""
  });
  const { value: form, setValue: setForm } = draft;
  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateCoverLetterTemplate(template.id, {
        title: form.title,
        target_roles: csvToList(form.target_roles),
        target_keywords: csvToList(form.target_keywords),
        body: form.body,
        notes: form.notes || null
      }),
    onSuccess: () => { draft.clear(); onChanged(); }
  });
  const deleteMutation = useMutation({
    mutationFn: () => api.deleteCoverLetterTemplate(template.id),
    onSuccess: () => {
      onDeleted();
      onChanged();
    }
  });

  const deleteTemplate = () => {
    if (window.confirm(`Delete ${template.title}? This cannot be undone.`)) {
      deleteMutation.mutate();
    }
  };

  return (
    <Panel><fieldset disabled={saveMutation.isPending || deleteMutation.isPending} className="min-w-0">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <AssetHeading title={template.title} meta={`Updated ${formatDate(template.updated_at)}`} />
        <Button variant="ghost" size="sm" onClick={deleteTemplate} disabled={deleteMutation.isPending}>
          <Trash2 className="h-4 w-4" />
          Delete
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
        <AdvancedDetails>
          <Field label="Body">
            <Textarea className="min-h-56" value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} />
          </Field>
          <Field label="Notes">
            <Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          </Field>
        </AdvancedDetails>
        {deleteMutation.error ? <p role="alert" className="text-destructive">{deleteMutation.error.message}</p> : null}
        <DraftNotice dirty={draft.dirty} storageError={draft.storageError} saved={saveMutation.isSuccess} />
        {saveMutation.error ? <p className="text-sm text-destructive">{(saveMutation.error as Error).message}</p> : null}
        <Button className="justify-self-start" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Save className="h-4 w-4" />
          {saveMutation.isPending ? "Saving..." : "Save template"}
        </Button>
      </div>
    </fieldset></Panel>
  );
}

function CoverageAuditTab() {
  const [result, setResult] = React.useState<CoverageGapResponse | null>(null);
  const mutation = useMutation({ mutationFn: api.generateCoverageGaps, onSuccess: setResult });
  return (
    <Panel>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <SectionHeader icon={FileSearch} title="Coverage Audit" />
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          <Search className="h-4 w-4" />
          {mutation.isPending ? "Checking..." : "Generate audit"}
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

function AssetHeading({
  title,
  meta,
  badge
}: {
  title: string;
  meta: string;
  badge?: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {badge}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{meta}</p>
    </div>
  );
}

function AdvancedDetails({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const Icon = open ? ChevronDown : ChevronRight;
  return (
    <div className="grid gap-4 border-t border-border pt-4">
      <Button className="justify-self-start px-0" variant="ghost" size="sm" onClick={() => setOpen((value) => !value)}>
        <Icon className="h-4 w-4" />
        Advanced details
      </Button>
      {open ? <div className="grid gap-4">{children}</div> : null}
    </div>
  );
}

function PreviewTags({ label, items, max = 6 }: { label: string; items: string[]; max?: number }) {
  const unique = uniqueStrings(items);
  if (!unique.length) return null;
  const visible = unique.slice(0, max);
  const remaining = unique.length - visible.length;
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="font-medium text-muted-foreground">{label}</span>
      {visible.map((item) => (
        <span key={item} className="rounded-md border border-border bg-muted px-2 py-1 text-muted-foreground">
          {item}
        </span>
      ))}
      {remaining > 0 ? <span className="text-muted-foreground">+{remaining}</span> : null}
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

function uniqueStrings(items: string[]) {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const item of items) {
    const text = item.trim();
    const key = text.toLocaleLowerCase();
    if (!text || seen.has(key)) continue;
    output.push(text);
    seen.add(key);
  }
  return output;
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

function parseJsonList(value: string, _fallback: Record<string, unknown>[]) {
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed) || parsed.some(item => !item || typeof item !== "object" || Array.isArray(item))) throw new Error();
    return parsed as Record<string, unknown>[];
  } catch { throw new Error("Experience, projects, or education contains invalid data. Correct the highlighted draft before saving."); }
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

function DraftNotice({ dirty, storageError, saved }: { dirty: boolean; storageError: boolean; saved: boolean }) {
  return <p role="status" className="text-sm text-muted-foreground">{dirty ? storageError ? "Unsaved changes. Draft recovery is unavailable in this browser; save before leaving." : "Unsaved changes. Your draft is kept in this browser tab, including after a refresh." : saved ? "Saved successfully." : ""}</p>;
}
