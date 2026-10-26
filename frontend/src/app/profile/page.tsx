"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, FileText, Mail, Search, UserRound } from "lucide-react";
import { BaseProfileTab, ResumeVariantsTab, CoverLetterTemplatesTab, CoverageAuditTab } from "@/components/assets/asset-views";
import { TailoringSourceManager } from "@/components/tailoring/source-manager";
import { RetainedView } from "@/components/layout/retained-view";
import { Button } from "@/components/ui/button";
import { LocalTab, LocalTabs } from "@/components/ui/local-tabs";
import { MoreMenu } from "@/components/ui/more-menu";
import { PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { CoverLetterTemplate, ResumeOption, ResumeProfile } from "@/lib/types";
import { cn } from "@/lib/utils";
import { localViewHref, selectLocalView } from "@/lib/workspace-navigation";

type TabKey = "base" | "resumes" | "templates" | "sources" | "coverage";

const tabs: Array<{ key: TabKey; label: string; icon: React.ElementType }> = [
  { key: "resumes", label: "Resumes", icon: FileText },
  { key: "base", label: "Base profile", icon: UserRound },
  { key: "templates", label: "Cover Letters", icon: Mail },
  { key: "sources", label: "Tailoring sources", icon: Search }
];

export default function ProfilePage() { return <React.Suspense fallback={<Panel>Loading assets...</Panel>}><ProfileContent /></React.Suspense>; }

function ProfileContent() {
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const activeTab = selectLocalView(params, ["base", "resumes", "templates", "sources", "coverage"] as const, params.get("focus")?.startsWith("Tailoring") ? "sources" : "base");
  const setActiveTab = (tab: TabKey, focus?: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("tab", tab);
    if (focus) next.set("focus", focus); else next.delete("focus");
    window.history.pushState(null, "", `/profile?${next}`);
  };
  const { data: profile, isLoading, error } = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const { data: resumeOptions = [], isLoading: resumesLoading, error: resumesError } = useQuery({ queryKey: ["resume-options"], queryFn: api.resumeOptions });
  const { data: templates = [], isLoading: templatesLoading, error: templatesError } = useQuery({ queryKey: ["cover-letter-templates"], queryFn: api.coverLetterTemplates });

  React.useEffect(() => {
    const target = params.get("focus");
    if (!target || isLoading || resumesLoading || templatesLoading) return;
    const frame = requestAnimationFrame(() => {
      const section = document.getElementById("asset-content");
      const field = Array.from(section?.querySelectorAll("label") ?? []).find(label => !label.closest("[hidden]") && label.textContent?.startsWith(target));
      const element = field ?? section;
      element?.scrollIntoView({ block: "start", behavior: "smooth" });
      (field instanceof HTMLLabelElement ? document.getElementById(field.htmlFor) : section)?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [params, isLoading, resumesLoading, templatesLoading]);
  const invalidateProfileAssets = () => {
    queryClient.invalidateQueries({ queryKey: ["profile"] });
    queryClient.invalidateQueries({ queryKey: ["resume-options"] });
    queryClient.invalidateQueries({ queryKey: ["cover-letter-templates"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  return (
    <div className="grid gap-8">
      <PageHeader
        title="Application Assets"
        description="Reusable documents, your profile, and approved tailoring inputs."
      />
      {error ? <Panel className="border-destructive/25 bg-destructive/10 text-sm text-destructive">{(error as Error).message}<Button variant="secondary" onClick={invalidateProfileAssets}>Retry loading profile</Button></Panel> : null}
      {isLoading ? <Panel>Loading application assets...</Panel> : null}
      {resumesError || templatesError ? <Panel><div role="alert">Could not load assets: {((resumesError || templatesError) as Error).message}</div><Button variant="secondary" onClick={invalidateProfileAssets}>Retry loading assets</Button></Panel> : null}
      <LocalTabs label="Application asset views">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <LocalTab
              key={tab.key}
              active={active}
              onClick={() => setActiveTab(tab.key)}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </LocalTab>
          );
        })}
        <MoreMenu items={[{ label: "Coverage audit", href: localViewHref("/profile", params, "coverage") }]} />
      </LocalTabs>
      <div className="grid gap-3">
        {!isLoading && !resumesLoading && !templatesLoading && !error && !resumesError && !templatesError ? <ReadinessStrip profile={profile ?? null} resumeOptions={resumeOptions} templates={templates} onSelect={setActiveTab} /> : null}
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">Tailored drafts and approved exports live in each job.<Link className="font-medium text-primary underline" href="/jobs">Open Jobs</Link></p>
      </div>
      <section id="asset-content" tabIndex={-1} className="scroll-mt-36">
        <RetainedView label="Reusable resumes" active={activeTab === "resumes"}>{!resumesLoading && !resumesError ? <div className="grid gap-8"><ResumeVariantsTab resumeOptions={resumeOptions} onChanged={invalidateProfileAssets} /><SourceLink onOpen={() => setActiveTab("sources")} /></div> : null}</RetainedView>
        <RetainedView label="Base profile" active={activeTab === "base"}>{!isLoading && !error ? <div className="grid gap-8"><BaseProfileTab profile={profile ?? null} onSaved={invalidateProfileAssets} /><SourceLink onOpen={() => setActiveTab("sources")} /></div> : null}</RetainedView>
        <RetainedView label="Reusable cover letters" active={activeTab === "templates"}>{!templatesLoading && !templatesError ? <CoverLetterTemplatesTab templates={templates} onChanged={invalidateProfileAssets} /> : null}</RetainedView>
        <RetainedView label="Tailoring source workspace" active={activeTab === "sources"}>{!isLoading && !error ? profile ? <TailoringSourceManager key={profile.id} profileId={profile.id} /> : <Panel><p className="text-sm">Save a base profile before importing tailoring sources.</p><Link className="mt-3 inline-block text-sm font-medium text-primary underline" href="/profile?tab=base">Open base profile</Link></Panel> : null}</RetainedView>
        <RetainedView label="Coverage audit" active={activeTab === "coverage"}><CoverageAuditTab /></RetainedView>
      </section>
    </div>
  );
}

function SourceLink({ onOpen }: { onOpen: () => void }) {
  return <div className="grid gap-2 border-t border-border pt-6 text-sm">
    <h2 className="font-semibold">Tailoring inputs</h2>
    <p className="text-muted-foreground">Tailoring uses the activated source bundle. Profile edits do not change its approved facts, preferences or layout references.</p>
    <Button variant="ghost" className="w-fit px-0 text-primary underline" onClick={onOpen}>Manage approved tailoring sources</Button>
  </div>;
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
  onSelect: (tab: TabKey, focus?: string) => void;
}) {
  const checks = [
    { tab: "base" as TabKey, label: "Base profile", focus: "Summary", ready: Boolean(profile?.resume_text.trim() || profile?.summary?.trim()) },
    { tab: "base" as TabKey, label: "Skills", focus: "Skills", ready: Boolean(profile?.skills.some(skill => skill.trim())) },
    { tab: "resumes" as TabKey, label: "Ready resume", focus: "Resume Variants", ready: resumeOptions.some((option) => option.status === "ready" && Boolean(option.parsed_text.trim() || option.summary?.trim() || option.experience.length)) },
    { tab: "templates" as TabKey, label: "Cover template", focus: "Cover Letters", ready: templates.some(template => Boolean(template.body.trim())) }
  ];
  const ready = checks.every((item) => item.ready);
  const StatusIcon = ready ? CheckCircle2 : AlertCircle;

  return (
    <Panel className="p-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-2">
          <StatusIcon className={cn("h-4 w-4", ready ? "text-success-foreground" : "text-warning-foreground")} />
          <span className="text-sm font-semibold">{ready ? "Ready for job review" : "Needs assets"}</span>{!ready ? <p className="text-xs text-muted-foreground">Add saved content for: {checks.filter(item => !item.ready).map(item => item.label).join(", ")}. Select a check to open its section.</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {checks.map((item) => (
            <button type="button" onClick={() => onSelect(item.tab, item.focus)} title={item.ready ? `${item.label} has saved content` : `Add content to ${item.label.toLowerCase()}`}
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
