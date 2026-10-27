"use client";

import { useConfirm } from "@/components/ui/confirm-provider";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Pencil, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { Dialog } from "@/components/ui/dialog";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { SavedStudyPlan, SkillGap, StudyPlan, StudyPlanMode, StudyPlanTimeframe } from "@/lib/types";
import { TopSkillGaps } from "./top-skill-gaps";

const priorityTone = { low: "neutral", medium: "warn", high: "bad" } as const;
const progressClassName = "h-2 w-full appearance-none overflow-hidden rounded-full border-0 bg-muted [&::-webkit-progress-bar]:bg-muted [&::-webkit-progress-value]:bg-primary [&::-moz-progress-bar]:bg-primary";

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

function focusLearningSection(id: string) {
  const target = document.getElementById(id);
  const disclosure = target?.closest("details");
  if (disclosure) disclosure.open = true;
  target?.focus({ preventScroll: true });
  target?.scrollIntoView({ block: "start" });
}

export default function SkillsPage() {
  const queryClient = useQueryClient();
  const { data: gaps = [], isLoading, error } = useQuery({ queryKey: ["skill-gaps"], queryFn: api.skillGaps });
  const { data: profile, isLoading: profileLoading, error: profileError } = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const { data: savedPlans = [], isLoading: plansLoading, error: plansError } = useQuery({ queryKey: ["study-plans"], queryFn: api.savedStudyPlans });

  const [timeframe, setTimeframe] = React.useState<StudyPlanTimeframe>("2 weeks");
  const [hours, setHours] = React.useState("");
  const [hoursUnit, setHoursUnit] = React.useState<"day" | "week">("week");
  const [mode, setMode] = React.useState<StudyPlanMode>("project_ideas");
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
      setPlanTitle(`${meta.mode === "project_ideas" ? "Projects" : meta.timeframe}${covered.length ? ` - ${covered.slice(0, 3).join(", ")}` : ""}`);
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
      <PageHeader title="Skills & learning"
        action={<Button variant="secondary" onClick={() => queryClient.invalidateQueries({ queryKey: ["skill-gaps"] })}><RefreshCw className="h-4 w-4" />Refresh skills</Button>} />

      <Panel>
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div><h2 id="project-ideas" className="scroll-mt-28 font-semibold">Create project ideas</h2><p className="mt-1 text-sm text-muted-foreground">Start with practical projects. Add a weekly plan when you want a schedule.</p></div>
          <button type="button" className="py-2 text-sm underline" onClick={() => focusLearningSection("saved-learning")}>Saved projects & plans</button>
        </div>
        <div className="grid gap-4">
          <div><h3 className="text-sm font-medium">Skills to cover</h3>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {focusSkills.length ? <>{focusSkills.map(skill => <Badge key={skill}>{skill}</Badge>)}<Button size="sm" variant="ghost" onClick={() => setSelectedSkills(new Set())}>Clear selected skills</Button></>
                : <p className="text-sm text-muted-foreground">Using your top gaps. Choose specific skills in Skill gaps & evidence below.</p>}
              <button type="button" onClick={() => focusLearningSection("skill-gaps")} className="py-2 text-sm underline">Choose skills</button>
            </div>
          </div>
          <details className="rounded-md border border-border p-3">
            <summary id="study-plan" className="scroll-mt-28 cursor-pointer text-sm font-medium">Weekly planning & generation options</summary>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <Field label="Output">
                <Select value={mode} onChange={event => setMode(event.target.value as StudyPlanMode)}>
                  <option value="project_ideas">Project ideas only</option><option value="both">Weekly plan + project ideas</option><option value="weekly_plan">Weekly plan only</option>
                </Select>
              </Field>
              <Field label="Timeframe">
                <Select value={timeframe} onChange={event => setTimeframe(event.target.value as StudyPlanTimeframe)}><option value="1 week">1 week</option><option value="2 weeks">2 weeks</option><option value="1 month">1 month</option></Select>
              </Field>
              <div className="grid gap-1.5 text-sm font-medium">Available time
                <div className="grid grid-cols-2 gap-2"><Input type="number" min={1} aria-label="Available hours" placeholder="Hours (optional)" value={hours} onChange={event => setHours(event.target.value)} />
                  <Select aria-label="Time budget unit" value={hoursUnit} onChange={event => setHoursUnit(event.target.value as "day" | "week")}><option value="day">per day</option><option value="week">per week</option></Select>
                </div>
              </div>
            </div>
          </details>
          <p className="text-xs text-muted-foreground">Next output: {modeLabels[mode]}{mode !== "project_ideas" ? ` over ${timeframe}` : ""}{hours ? ` with ${hours} hours per ${hoursUnit}` : ""}.</p>
          {planMutation.error ? <p role="alert" className="text-sm text-destructive">{planMutation.error.message}</p> : null}
          {profileLoading ? <p role="status">Loading profile...</p> : profileError ? <p role="alert">Could not load your profile: {profileError.message}<Button variant="secondary" onClick={() => queryClient.invalidateQueries({ queryKey: ["profile"] })}>Retry loading profile</Button></p> : !profile ? <p className="text-sm">Create a <Link href="/profile" className="underline">base profile in Application Assets</Link> before generating ideas.</p> : null}
          <Button className="justify-self-start" onClick={() => planMutation.mutate()} disabled={planMutation.isPending || !profile}>
            {planMutation.isPending ? "Generating..." : mode === "project_ideas" ? "Generate project ideas" : mode === "weekly_plan" ? "Generate weekly plan" : "Generate plan + projects"}
          </Button>
          {studyPlan ? <section aria-label="Generated learning output" className="grid gap-4 border-t border-border pt-4">
            <h3 className="font-semibold">{planMeta?.mode === "project_ideas" ? "Generated project ideas" : "Generated learning plan"}</h3>
            <p className="text-xs text-muted-foreground">{saveMutation.isSuccess ? "Saved to your projects & plans." : "Generated preview. Save it to keep it and track progress."}</p>
            <StudyPlanView plan={studyPlan} />
            <div className="flex flex-wrap items-end gap-3 border-t border-border pt-4">
              <label className="grid min-w-0 flex-1 gap-1.5 text-sm font-medium">Save name<Input value={planTitle} onChange={event => setPlanTitle(event.target.value)} /></label>
              <Button variant="secondary" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || saveMutation.isSuccess || !planTitle.trim()}>{saveMutation.isSuccess ? "Saved" : saveMutation.isPending ? "Saving..." : planMeta?.mode === "project_ideas" ? "Save project ideas" : "Save plan"}</Button>
            </div>
            {saveMutation.error ? <p role="alert" className="text-sm text-destructive">{saveMutation.error.message}</p> : null}
          </section> : null}
        </div>
      </Panel>

      {plansLoading ? <Panel>Loading saved projects & plans...</Panel> : plansError ? <Panel><p role="alert">Could not load saved projects & plans: {plansError.message}</p><Button onClick={() => queryClient.invalidateQueries({ queryKey: ["study-plans"] })}>Retry saved work</Button></Panel> : <SavedPlansPanel plans={savedPlans} />}

      <TopSkillGaps />

      <Panel>
        <details>
          <summary id="skill-gaps" className="scroll-mt-28 cursor-pointer font-semibold">Skill gaps & evidence ({activeGaps.length})</summary>
          <p className="my-3 text-sm text-muted-foreground">Ranked by unique active jobs affected, using the latest resume match or job requirements. Select skills to focus generation. Set a skill to high to mark it known and exclude it from gaps and generation.</p>
          {updateMutation.error ? <p role="alert" className="text-destructive">Could not update skill level: {updateMutation.error.message}</p> : null}
          {error ? <p role="alert" className="text-sm text-destructive">{error.message}<Button variant="secondary" onClick={() => queryClient.invalidateQueries({ queryKey: ["skill-gaps"] })}>Retry loading skills</Button></p> : null}
          {isLoading ? <p className="text-sm text-muted-foreground">Loading gaps...</p> : null}
          <div className="overflow-x-auto"><GapTable gaps={activeGaps} onLevelChange={setLevel} busy={updateMutation.isPending} selectable selectedSkills={selectedSkills} onToggleSkill={toggleSkill} />
            {!activeGaps.length && !isLoading && !error ? <p className="py-4 text-sm text-muted-foreground">{knownGaps.length ? "No active gaps - everything tracked is marked as known." : "No gaps yet. Run job analysis or resume suggestions first."}</p> : null}
          </div>
          {knownGaps.length ? <div className="mt-4 border-t border-border pt-4">
            <button type="button" aria-expanded={showKnown} aria-controls="known-skills" onClick={() => setShowKnown(value => !value)} className="flex items-center gap-1.5 py-2 text-sm font-medium text-muted-foreground"><ChevronRight className={cn("h-4 w-4 transition-transform", showKnown && "rotate-90")} />Known skills ({knownGaps.length})</button>
            {showKnown ? <div id="known-skills" className="mt-3 overflow-x-auto"><GapTable gaps={knownGaps} onLevelChange={setLevel} busy={updateMutation.isPending} muted /></div> : null}
          </div> : null}
        </details>
      </Panel>
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
        <h2 id="saved-learning" tabIndex={-1} className="scroll-mt-28 text-base font-semibold">Saved projects & plans</h2>
        <Badge>{plans.length} saved</Badge>
      </div>
      {renameMutation.error || deleteMutation.error ? <p role="alert" className="mb-3 text-destructive">{((renameMutation.error || deleteMutation.error) as Error).message}</p> : null}
      {plans.length ? (
        <div className="grid gap-3">
          {plans.map((plan) => {
            const expanded = expandedId === plan.id;
            return (
              <div key={plan.id} data-plan-id={plan.id} className="rounded-md border border-border">
                <div className="flex flex-wrap items-center gap-2 p-3">
                  {renamingId === plan.id ? (
                    <div className="flex min-w-0 flex-1 basis-full items-center gap-1.5 sm:basis-0">
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
                      className="flex min-w-0 flex-1 basis-full items-center gap-1.5 text-left text-sm font-medium sm:basis-0"
                    >
                      <ChevronRight className={cn("h-4 w-4 shrink-0 transition-transform", expanded && "rotate-90")} />
                      <span className="min-w-0 break-words">{plan.title}</span>
                    </button>
                  )}
                  <Badge>{modeLabels[plan.mode]}</Badge>
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
                    className="grid h-8 w-8 shrink-0 place-items-center text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label="Delete plan"
                    disabled={deleteMutation.isPending} onClick={async () => { if (await confirm(`Delete study plan "${plan.title}"? This cannot be undone.`)) deleteMutation.mutate(plan.id); }}
                    className="grid h-8 w-8 shrink-0 place-items-center text-muted-foreground transition-colors hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                <p hidden={expanded} className="px-3 pb-3 text-xs text-muted-foreground">{progressSummary(plan.plan)}</p>
                <div id={`plan-${plan.id}`} hidden={!expanded} className="border-t border-border p-3 text-sm">
                  <p className="mb-3 text-xs text-muted-foreground">{plan.timeframe}{plan.time_budget_hours ? ` - ${plan.time_budget_hours}h/${plan.time_budget_unit}` : ""}</p>
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
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No saved work yet. Generate project ideas and save them here to track progress. Existing weekly plans will also appear here.</p>
      )}
    </Panel>
  );
}

function learningProgress(plan: StudyPlan) {
  const completed = new Set(plan.completed_tasks ?? []);
  const projects = plan.project_ideas.length;
  const completedProjects = plan.project_ideas.filter((_, index) => completed.has(`project:${index}`)).length;
  let tasks = 0, completedTasks = 0;
  plan.study_plan.forEach((period, i) => period.tasks.forEach((_, j) => { tasks++; if (completed.has(`task:${i}:${j}`)) completedTasks++; }));
  return { projects, completedProjects, tasks, completedTasks };
}

function progressSummary(plan: StudyPlan) {
  const progress = learningProgress(plan);
  return [progress.projects ? `${progress.completedProjects} of ${progress.projects} projects completed` : "", progress.tasks ? `${progress.completedTasks} of ${progress.tasks} study tasks completed` : ""].filter(Boolean).join(" - ") || "No project ideas or study tasks";
}

function StudyPlanView({ plan, onToggle, busy = false }: { plan: StudyPlan; onToggle?: (id: string) => void; busy?: boolean }) {
  return <div className="grid gap-4 text-sm">
    {plan.project_ideas.length ? <div><h3 className="font-medium">Project ideas</h3><p className="mt-1 text-xs text-muted-foreground">Project progress is tracked separately from weekly study tasks.</p>
      <ul className="mt-3 grid gap-2">{plan.project_ideas.map((project, index) => {
        const id = `project:${index}`;
        return <li key={id} className="rounded-md border border-border p-3" data-completion-id={id}>{onToggle ? <label className="flex items-start gap-3"><input className="mt-1 h-4 w-4 shrink-0 accent-primary" type="checkbox" checked={plan.completed_tasks?.includes(id) ?? false} disabled={busy} onChange={() => onToggle(id)} /><span className={plan.completed_tasks?.includes(id) ? "line-through" : ""}>{project}</span></label> : project}</li>;
      })}</ul>
    </div> : null}
    {plan.study_plan.length ? <details className="rounded-md border border-border p-3">
      <summary className="cursor-pointer font-medium">Weekly plan & study tasks</summary>
      <div className="mt-3 grid gap-3">{plan.study_plan.map((item, periodIndex) => <div key={periodIndex} className="rounded-md border border-border bg-muted/40 p-3">
        <h3 className="font-medium">{item.period}: {item.focus}</h3>
        <ul className="mt-3 grid gap-2">{item.tasks.map((task, taskIndex) => {
          const id = `task:${periodIndex}:${taskIndex}`;
          return <li key={id} data-completion-id={id}>{onToggle ? <label className="flex items-start gap-3"><input className="mt-1 h-4 w-4 shrink-0 accent-primary" type="checkbox" checked={plan.completed_tasks?.includes(id) ?? false} disabled={busy} onChange={() => onToggle(id)} /><span className={plan.completed_tasks?.includes(id) ? "line-through" : ""}>{task}</span></label> : task}</li>;
        })}</ul>
      </div>)}</div>
    </details> : null}
    {plan.top_gaps.length || plan.priority_order.length ? <details className="rounded-md border border-border p-3"><summary className="cursor-pointer font-medium">Gap priorities</summary><div className="mt-3 grid gap-3">{plan.top_gaps.length ? <List title="Top gaps" items={plan.top_gaps} /> : null}{plan.priority_order.length ? <List title="Priority order" items={plan.priority_order} /> : null}</div></details> : null}
    {!plan.project_ideas.length && !plan.study_plan.length ? <p className="text-muted-foreground">This output has no project ideas or study tasks. Adjust the generation options and try again.</p> : null}
  </div>;
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
          {selectable ? <th className="w-8 py-2 pr-2" aria-label="Select skills for generation" /> : null}
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
                  aria-label={`Focus on ${gap.skill_name}`}
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
  const progress = learningProgress(saved.plan);
  return <div className="grid gap-3">
    <p role="status" className="text-sm">{progressSummary(saved.plan)}{mutation.isPending ? " - Saving..." : ""}</p>
    {progress.projects ? <progress className={progressClassName} aria-label="Project progress" value={progress.completedProjects} max={progress.projects} /> : null}
    {progress.tasks ? <details><summary className="cursor-pointer text-xs text-muted-foreground">Study task progress: {progress.completedTasks} of {progress.tasks}</summary><progress className={cn("mt-2", progressClassName)} aria-label="Study plan progress" value={progress.completedTasks} max={progress.tasks} /></details> : null}
    {mutation.error ? <p role="alert" className="text-destructive">Progress was not saved: {mutation.error.message}. Try again.</p> : null}
    <StudyPlanView plan={saved.plan} busy={mutation.isPending} onToggle={id => mutation.mutate(completed.includes(id) ? completed.filter(value => value !== id) : [...completed, id])} />
  </div>;
}

function SkillEvidence({ gap }: { gap: SkillGap }) {
  const [open, setOpen] = React.useState(false);
  const query = useQuery({ queryKey: ["skill-evidence", gap.id], queryFn: () => api.skillEvidence(gap.id), enabled: open });
  return <><button className="text-left text-primary underline" onClick={() => setOpen(true)} aria-label={`View evidence for ${gap.skill_name}`}>{gap.skill_name}</button>{open ? <Dialog title={`Evidence for ${gap.skill_name}`} onClose={() => setOpen(false)}><p className="mb-3 text-sm text-muted-foreground">{gap.active_job_count} unique active jobs affected. {gap.count} recorded mentions, including repeat analyses. These are the matching sources still available; mentions are not a count of unique jobs.</p>{query.isLoading ? <p role="status">Loading evidence...</p> : query.error ? <div role="alert">{query.error.message}<Button variant="secondary" onClick={() => query.refetch()}>Retry loading evidence</Button></div> : query.data?.length ? <ul className="grid gap-3">{query.data.map(item => <li key={`${item.href}-${item.source}`}><Link className="underline" href={item.href}>{item.label}</Link><div className="text-xs text-muted-foreground">{item.source}</div></li>)}</ul> : <p>No matching source records remain. This skill may come from an older analysis.</p>}</Dialog> : null}</>;
}
