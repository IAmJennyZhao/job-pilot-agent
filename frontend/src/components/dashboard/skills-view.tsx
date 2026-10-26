"use client";

import { useConfirm } from "@/components/ui/confirm-provider";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ChevronRight, Pencil, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { Dialog } from "@/components/ui/dialog";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { SavedStudyPlan, SkillGap, StudyPlan, StudyPlanMode, StudyPlanTimeframe } from "@/lib/types";

const priorityTone = { low: "neutral", medium: "warn", high: "bad" } as const;

const modeLabels: Record<StudyPlanMode, string> = {
  both: "plan + projects",
  weekly_plan: "weekly plan",
  project_ideas: "project ideas"
};

type PlanRequestMeta = {
  timeframe: StudyPlanTimeframe;
  focus_skills: string[];
  time_budget_hours: number | null;
  time_budget_unit: "day" | "week";
  mode: StudyPlanMode;
};

export default function SkillsPage() {
  const queryClient = useQueryClient();
  const { data: gaps = [], isLoading, error } = useQuery({ queryKey: ["skill-gaps"], queryFn: api.skillGaps });
  const { data: profile, isLoading: profileLoading, error: profileError } = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const { data: savedPlans = [], isLoading: plansLoading, error: plansError } = useQuery({ queryKey: ["study-plans"], queryFn: api.savedStudyPlans });

  const [timeframe, setTimeframe] = React.useState<StudyPlanTimeframe>("2 weeks");
  const [hours, setHours] = React.useState("");
  const [hoursUnit, setHoursUnit] = React.useState<"day" | "week">("week");
  const [mode, setMode] = React.useState<StudyPlanMode>("both");
  const [selectedSkills, setSelectedSkills] = React.useState<Set<string>>(new Set());
  const [studyPlan, setStudyPlan] = React.useState<StudyPlan | null>(null);
  const [planMeta, setPlanMeta] = React.useState<PlanRequestMeta | null>(null);
  const [planTitle, setPlanTitle] = React.useState("");
  const [showKnown, setShowKnown] = React.useState(false);

  const activeGaps = gaps.filter((gap) => gap.user_level !== "high");
  const knownGaps = gaps.filter((gap) => gap.user_level === "high");
  const focusSkills = activeGaps.filter((gap) => selectedSkills.has(gap.skill_name)).map((gap) => gap.skill_name);

  const toggleSkill = (skillName: string) =>
    setSelectedSkills((current) => {
      const next = new Set(current);
      if (next.has(skillName)) {
        next.delete(skillName);
      } else {
        next.add(skillName);
      }
      return next;
    });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Pick<SkillGap, "user_level" | "suggested_action">> }) =>
      api.updateSkillGap(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const planMutation = useMutation({
    mutationFn: async () => {
      const meta: PlanRequestMeta = {
        timeframe,
        focus_skills: focusSkills,
        time_budget_hours: Number.parseInt(hours, 10) > 0 ? Number.parseInt(hours, 10) : null,
        time_budget_unit: hoursUnit,
        mode
      };
      const plan = await api.generateStudyPlan({
        resume_profile_id: profile?.id ?? null,
        target_roles: profile?.target_roles ?? [],
        ...meta
      });
      return { plan, meta };
    },
    onSuccess: ({ plan, meta }) => {
      setStudyPlan(plan);
      setPlanMeta(meta);
      const covered = meta.focus_skills.length ? meta.focus_skills : plan.top_gaps;
      setPlanTitle(`${meta.timeframe} - ${covered.slice(0, 3).join(", ")}` || "Study plan");
      saveMutation.reset();
    }
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!studyPlan || !planMeta) {
        throw new Error("Generate a plan first.");
      }
      return api.saveStudyPlan({
        resume_profile_id: profile?.id ?? null,
        title: planTitle.trim(),
        plan: studyPlan,
        ...planMeta
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["study-plans"] })
  });

  const setLevel = (id: string, level: SkillGap["user_level"]) =>
    updateMutation.mutate({ id, payload: { user_level: level } });

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Skill Gaps"
        description="Prioritized by unique active jobs affected, using the latest resume match or job requirements. Generate a study plan from the current gap list. Set your level to high to mark a skill as known - it moves out of the gap list and study plans."
        action={
          <Button variant="secondary" onClick={() => queryClient.invalidateQueries({ queryKey: ["skill-gaps"] })}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        }
      />

      {updateMutation.error ? <p role="alert" className="text-destructive">Could not update skill level: {updateMutation.error.message}</p> : null}
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="grid content-start gap-4">
          <Panel className="overflow-hidden">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Gap Table</h2>
              <Badge>{activeGaps.length} tracked</Badge>
            </div>
            {error ? <p className="text-sm text-destructive">{(error as Error).message}<Button variant="secondary" onClick={() => queryClient.invalidateQueries({ queryKey: ["skill-gaps"] })}>Retry loading skills</Button></p> : null}
            {isLoading ? <p className="text-sm text-muted-foreground">Loading gaps...</p> : null}
            <div className="overflow-x-auto">
              <GapTable
                gaps={activeGaps}
                onLevelChange={setLevel} busy={updateMutation.isPending}
                selectable
                selectedSkills={selectedSkills}
                onToggleSkill={toggleSkill}
              />
              {!activeGaps.length && !isLoading && !error ? (
                <p className="py-8 text-sm text-muted-foreground">
                  {knownGaps.length
                    ? "No active gaps - everything tracked is marked as known."
                    : "No gaps yet. Run job analysis or resume suggestions first."}
                </p>
              ) : null}
            </div>
            {knownGaps.length ? (
              <div className="mt-4 border-t border-border pt-4">
                <button
                  type="button"
                  aria-expanded={showKnown} aria-controls="known-skills" onClick={() => setShowKnown((value) => !value)}
                  className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                >
                  <ChevronRight className={cn("h-4 w-4 transition-transform", showKnown && "rotate-90")} />
                  Known skills ({knownGaps.length})
                </button>
                {showKnown ? (
                  <div id="known-skills" className="mt-3 overflow-x-auto">
                    <GapTable gaps={knownGaps} onLevelChange={setLevel} busy={updateMutation.isPending} muted />
                  </div>
                ) : null}
              </div>
            ) : null}
          </Panel>

          {plansLoading ? <Panel>Loading saved plans...</Panel> : plansError ? <Panel><p role="alert">Could not load saved plans: {(plansError as Error).message}</p><Button onClick={() => queryClient.invalidateQueries({ queryKey: ["study-plans"] })}>Retry</Button></Panel> : <SavedPlansPanel plans={savedPlans} />}
        </div>

        <Panel className="self-start">
          <div className="mb-4 flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" />
            <h2 id="study-plan" className="scroll-mt-28 text-base font-semibold">Study Plan</h2>
          </div>
          <div className="grid gap-4">
            <div className="grid gap-1.5 text-sm font-medium">
              Skills to cover
              <div className="flex flex-wrap items-center gap-1.5">
                {focusSkills.length ? (
                  <>
                    {focusSkills.map((skill) => (
                      <Badge key={skill}>{skill}</Badge>
                    ))}
                    <button
                      type="button"
                      onClick={() => setSelectedSkills(new Set())}
                      className="text-xs font-medium text-muted-foreground underline-offset-2 hover:underline"
                    >
                      clear
                    </button>
                  </>
                ) : (
                  <p className="text-sm font-normal text-muted-foreground">
                    None selected - the plan will use your top gaps. Tick skills in the gap table to focus it.
                  </p>
                )}
              </div>
            </div>
            <label className="grid gap-1.5 text-sm font-medium">
              Timeframe
              <Select value={timeframe} onChange={(event) => setTimeframe(event.target.value as StudyPlanTimeframe)}>
                <option value="1 week">1 week</option>
                <option value="2 weeks">2 weeks</option>
                <option value="1 month">1 month</option>
              </Select>
            </label>
            <div className="grid gap-1.5 text-sm font-medium">
              Available time
              <div className="grid grid-cols-[1fr_1fr] gap-2">
                <Input
                  type="number"
                  min={1}
                  aria-label="Available hours" placeholder="Hours (optional)"
                  value={hours}
                  onChange={(event) => setHours(event.target.value)}
                />
                <Select aria-label="Time budget unit" value={hoursUnit} onChange={(event) => setHoursUnit(event.target.value as "day" | "week")}>
                  <option value="day">per day</option>
                  <option value="week">per week</option>
                </Select>
              </div>
            </div>
            <label className="grid gap-1.5 text-sm font-medium">
              Output
              <Select value={mode} onChange={(event) => setMode(event.target.value as StudyPlanMode)}>
                <option value="both">Weekly plan + project ideas</option>
                <option value="weekly_plan">Weekly plan only</option>
                <option value="project_ideas">Project ideas only</option>
              </Select>
            </label>
            {planMutation.error ? <p className="text-sm text-destructive">{(planMutation.error as Error).message}</p> : null}
            {profileLoading ? <p role="status">Loading profile...</p> : profileError ? <p role="alert">Could not load your profile: {(profileError as Error).message}<Button variant="secondary" onClick={() => queryClient.invalidateQueries({ queryKey: ["profile"] })}>Retry loading profile</Button></p> : !profile ? <p className="text-sm">Create a <Link href="/profile" className="underline">base profile in Application Assets</Link> before generating a plan.</p> : null}
            <Button onClick={() => planMutation.mutate()} disabled={planMutation.isPending || !profile}>
              {planMutation.isPending ? "Generating..." : "Generate study plan"}
            </Button>
            {studyPlan ? (
              <div className="grid gap-4 text-sm">
                <StudyPlanView plan={studyPlan} />
                <div className="grid gap-2 border-t border-border pt-4">
                  <label className="grid gap-1.5 text-sm font-medium">
                    Plan name
                    <Input value={planTitle} onChange={(event) => setPlanTitle(event.target.value)} />
                  </label>
                  {saveMutation.error ? (
                    <p className="text-sm text-destructive">{(saveMutation.error as Error).message}</p>
                  ) : null}
                  <Button
                    variant="secondary"
                    onClick={() => saveMutation.mutate()}
                    disabled={saveMutation.isPending || saveMutation.isSuccess || !planTitle.trim()}
                  >
                    {saveMutation.isSuccess ? "Saved" : saveMutation.isPending ? "Saving..." : "Save plan"}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function SavedPlansPanel({ plans }: { plans: SavedStudyPlan[] }) {
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = React.useState<string | null>(null);
  const [renamingId, setRenamingId] = React.useState<string | null>(null);
  const [renameValue, setRenameValue] = React.useState("");

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => api.renameStudyPlan(id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["study-plans"] })
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteStudyPlan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["study-plans"] })
  });

  const submitRename = (id: string) => {
    const title = renameValue.trim();
    if (title) {
      renameMutation.mutate({ id, title }, { onSuccess: () => setRenamingId(null) });
    }
  };

  return (
    <Panel>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Saved Study Plans</h2>
        <Badge>{plans.length} saved</Badge>
      </div>
      {renameMutation.error || deleteMutation.error ? <p role="alert" className="mb-3 text-destructive">{((renameMutation.error || deleteMutation.error) as Error).message}</p> : null}
      {plans.length ? (
        <div className="grid gap-3">
          {plans.map((plan) => {
            const expanded = expandedId === plan.id;
            return (
              <div key={plan.id} className="rounded-md border border-border">
                <div className="flex flex-wrap items-center gap-2 p-3">
                  {renamingId === plan.id ? (
                    <div className="flex min-w-0 flex-1 items-center gap-1.5">
                      <ChevronRight className={cn("h-4 w-4 shrink-0 transition-transform", expanded && "rotate-90")} />
                      <Input
                        autoFocus
                        aria-label="Plan name"
                        value={renameValue}
                        onChange={(event) => setRenameValue(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") submitRename(plan.id);
                          if (event.key === "Escape") setRenamingId(null);
                        }}
                      /><Button size="sm" disabled={renameMutation.isPending || !renameValue.trim()} onClick={() => submitRename(plan.id)}>Save</Button><Button variant="ghost" size="sm" onClick={() => setRenamingId(null)}>Cancel</Button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      aria-expanded={expanded} aria-controls={`plan-${plan.id}`} onClick={() => setExpandedId(expanded ? null : plan.id)}
                      className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-sm font-medium"
                    >
                      <ChevronRight className={cn("h-4 w-4 shrink-0 transition-transform", expanded && "rotate-90")} />
                      <span className="truncate">{plan.title}</span>
                    </button>
                  )}
                  <Badge>{plan.timeframe}</Badge>
                  <Badge>{modeLabels[plan.mode]}</Badge>
                  {plan.time_budget_hours ? <Badge>{plan.time_budget_hours}h/{plan.time_budget_unit}</Badge> : null}
                  <span className="text-xs text-muted-foreground">
                    {new Date(plan.created_at).toLocaleDateString()}
                  </span>
                  <button
                    type="button"
                    aria-label="Rename plan"
                    onClick={() => {
                      setRenamingId(plan.id);
                      setRenameValue(plan.title);
                    }}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label="Delete plan"
                    disabled={deleteMutation.isPending} onClick={async () => { if (await confirm(`Delete study plan "${plan.title}"? This cannot be undone.`)) deleteMutation.mutate(plan.id); }}
                    className="text-muted-foreground transition-colors hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                {expanded ? (
                  <div id={`plan-${plan.id}`} className="grid gap-4 border-t border-border p-3 text-sm">
                    {plan.focus_skills.length ? (
                      <div>
                        <h3 className="font-medium">Focused on</h3>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {plan.focus_skills.map((skill) => (
                            <Badge key={skill}>{skill}</Badge>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    <SavedPlanProgress saved={plan} />
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No saved plans yet. Generate a study plan and save it to keep it here.</p>
      )}
    </Panel>
  );
}

function StudyPlanView({ plan, onToggle, busy = false }: { plan: StudyPlan; onToggle?: (id: string) => void; busy?: boolean }) {
  return (
    <div className="grid gap-4 text-sm">
      {plan.top_gaps.length ? <List title="Top gaps" items={plan.top_gaps} /> : null}
      {plan.priority_order.length ? <List title="Priority order" items={plan.priority_order} /> : null}
      {plan.study_plan.length ? (
        <div>
          <h3 className="font-medium">Plan</h3>
          <div className="mt-2 grid gap-3">
            {plan.study_plan.map((item, periodIndex) => (
              <div key={`${item.period}-${item.focus}`} className="rounded-md border border-border bg-muted/40 p-3">
                <div className="font-medium">{item.period}: {item.focus}</div>
                <ul className="mt-2 list-inside list-disc text-muted-foreground">
                  {item.tasks.map((task, taskIndex) => { const id = `task:${periodIndex}:${taskIndex}`; return <li key={id} className="mb-2 list-none">{onToggle ? <label className="flex items-start gap-2"><input className="mt-1" type="checkbox" checked={plan.completed_tasks?.includes(id) ?? false} disabled={busy} onChange={() => onToggle(id)} /><span className={plan.completed_tasks?.includes(id) ? "line-through" : ""}>{task}</span></label> : task}</li>; })}
                </ul>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {plan.project_ideas.length ? <div><h3 className="font-medium">Optional project ideas</h3><p className="text-xs text-muted-foreground">Projects are tracked separately from study tasks.</p><ul className="mt-2 grid gap-2">{plan.project_ideas.map((project, index) => <li key={index}>{onToggle ? <label className="flex items-start gap-2"><input className="mt-1" type="checkbox" checked={plan.completed_tasks?.includes(`project:${index}`) ?? false} disabled={busy} onChange={() => onToggle(`project:${index}`)} /><span>{project}</span></label> : project}</li>)}</ul></div> : null}
    </div>
  );
}

function GapTable({
  gaps,
  onLevelChange,
  muted = false,
  selectable = false,
  selectedSkills,
  onToggleSkill,
  busy = false
}: {
  gaps: SkillGap[];
  onLevelChange: (id: string, level: SkillGap["user_level"]) => void;
  muted?: boolean;
  selectable?: boolean;
  selectedSkills?: Set<string>;
  onToggleSkill?: (skillName: string) => void;
  busy?: boolean;
}) {
  if (!gaps.length) {
    return null;
  }
  return (
    <table className={cn("w-full min-w-[860px] text-left text-sm", muted && "opacity-70")}>
      <thead className="border-b border-border text-xs uppercase text-muted-foreground">
        <tr>
          {selectable ? <th className="w-8 py-2 pr-2" aria-label="Select for study plan" /> : null}
          <th className="py-2 pr-4">Skill</th>
          <th className="py-2 pr-4">Sources</th>
          <th className="py-2 pr-4">Active jobs</th>
          <th className="py-2 pr-4">Priority</th>
          <th className="py-2 pr-4">Level</th>
          <th className="py-2 pr-4">Suggested Action</th>
        </tr>
      </thead>
      <tbody>
        {gaps.map((gap) => (
          <tr key={gap.id} className="border-b border-border last:border-0">
            {selectable ? (
              <td className="py-3 pr-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-primary"
                  aria-label={`Include ${gap.skill_name} in study plan`}
                  checked={selectedSkills?.has(gap.skill_name) ?? false}
                  onChange={() => onToggleSkill?.(gap.skill_name)}
                />
              </td>
            ) : null}
            <td className="py-3 pr-4 font-medium"><SkillEvidence gap={gap} /></td>
            <td className="py-3 pr-4">
              <div className="flex flex-wrap gap-1.5">
                {gap.sources.map((source) => (
                  <Badge key={source}>{source.replaceAll("_", " ")}</Badge>
                ))}
              </div>
            </td>
            <td className="py-3 pr-4">{gap.active_job_count}<span className="block text-xs text-muted-foreground">{gap.count} historical mentions</span></td>
            <td className="py-3 pr-4">
              <Badge tone={priorityTone[gap.priority]}>{gap.priority}</Badge>
            </td>
            <td className="py-3 pr-4">
              <Select
                disabled={busy}
                aria-label={`Your level in ${gap.skill_name}`}
                value={gap.user_level}
                onChange={(event) => onLevelChange(gap.id, event.target.value as SkillGap["user_level"])}
              >
                <option value="unknown">unknown</option>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </Select>
            </td>
            <td className="py-3 pr-4 text-muted-foreground">{gap.suggested_action}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="font-medium">{title}</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item) => (
          <Badge key={item}>{item}</Badge>
        ))}
      </div>
    </div>
  );
}

function SavedPlanProgress({ saved }: { saved: SavedStudyPlan }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (completed: string[]) => api.updateStudyProgress(saved.id, completed),
    onSuccess: updated => queryClient.setQueryData<SavedStudyPlan[]>(["study-plans"], old => old?.map(plan => plan.id === updated.id ? updated : plan))
  });
  const completed = saved.plan.completed_tasks ?? [];
  const total = saved.plan.study_plan.reduce((count, period) => count + period.tasks.length, 0);
  const completedTasks = completed.filter(id => id.startsWith("task:")).length;
  const completedProjects = completed.filter(id => id.startsWith("project:")).length;
  return <div className="grid gap-3"><p role="status" className="text-sm">{completedTasks} of {total} study tasks completed · {completedProjects} of {saved.plan.project_ideas.length} optional projects completed{mutation.isPending ? " · Saving..." : ""}</p><progress className="h-2 w-full accent-primary" aria-label="Study plan progress" value={completedTasks} max={Math.max(1, total)} />{mutation.error ? <p role="alert" className="text-destructive">Progress was not saved: {mutation.error.message}. Try again.</p> : null}<StudyPlanView plan={saved.plan} busy={mutation.isPending} onToggle={id => mutation.mutate(completed.includes(id) ? completed.filter(value => value !== id) : [...completed, id])} /></div>;
}

function SkillEvidence({ gap }: { gap: SkillGap }) {
  const [open, setOpen] = React.useState(false);
  const query = useQuery({ queryKey: ["skill-evidence", gap.id], queryFn: () => api.skillEvidence(gap.id), enabled: open });
  return <><button className="text-left text-primary underline" onClick={() => setOpen(true)} aria-label={`View evidence for ${gap.skill_name}`}>{gap.skill_name}</button>{open ? <Dialog title={`Evidence for ${gap.skill_name}`} onClose={() => setOpen(false)}><p className="mb-3 text-sm text-muted-foreground">{gap.active_job_count} unique active jobs affected. {gap.count} recorded mentions, including repeat analyses. These are the matching sources still available; mentions are not a count of unique jobs.</p>{query.isLoading ? <p role="status">Loading evidence...</p> : query.error ? <div role="alert">{query.error.message}<Button variant="secondary" onClick={() => query.refetch()}>Retry loading evidence</Button></div> : query.data?.length ? <ul className="grid gap-3">{query.data.map(item => <li key={`${item.href}-${item.source}`}><Link className="underline" href={item.href}>{item.label}</Link><div className="text-xs text-muted-foreground">{item.source}</div></li>)}</ul> : <p>No matching source records remain. This skill may come from an older analysis.</p>}</Dialog> : null}</>;
}
