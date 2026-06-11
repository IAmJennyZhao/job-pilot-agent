"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ChevronRight, RefreshCw } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { SkillGap, StudyPlan } from "@/lib/types";

const priorityTone = { low: "neutral", medium: "warn", high: "bad" } as const;

export default function SkillsPage() {
  const queryClient = useQueryClient();
  const { data: gaps = [], isLoading, error } = useQuery({ queryKey: ["skill-gaps"], queryFn: api.skillGaps });
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const [timeframe, setTimeframe] = React.useState<"1 week" | "2 weeks" | "1 month">("2 weeks");
  const [studyPlan, setStudyPlan] = React.useState<StudyPlan | null>(null);
  const [showKnown, setShowKnown] = React.useState(false);

  const activeGaps = gaps.filter((gap) => gap.user_level !== "high");
  const knownGaps = gaps.filter((gap) => gap.user_level === "high");

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Pick<SkillGap, "user_level" | "suggested_action">> }) =>
      api.updateSkillGap(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const planMutation = useMutation({
    mutationFn: () =>
      api.generateStudyPlan({
        resume_profile_id: profile?.id ?? null,
        timeframe,
        target_roles: profile?.target_roles ?? []
      }),
    onSuccess: setStudyPlan
  });

  const setLevel = (id: string, level: SkillGap["user_level"]) =>
    updateMutation.mutate({ id, payload: { user_level: level } });

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Skill Gaps"
        description="Review recurring missing skills and generate a study plan from the current gap list. Set your level to high to mark a skill as known - it moves out of the gap list and study plans."
        action={
          <Button variant="secondary" onClick={() => queryClient.invalidateQueries({ queryKey: ["skill-gaps"] })}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <Panel className="overflow-hidden">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold">Gap Table</h2>
            <Badge>{activeGaps.length} tracked</Badge>
          </div>
          {error ? <p className="text-sm text-destructive">{(error as Error).message}</p> : null}
          {isLoading ? <p className="text-sm text-muted-foreground">Loading gaps...</p> : null}
          <div className="overflow-x-auto">
            <GapTable gaps={activeGaps} onLevelChange={setLevel} />
            {!activeGaps.length && !isLoading ? (
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
                onClick={() => setShowKnown((value) => !value)}
                className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                <ChevronRight className={cn("h-4 w-4 transition-transform", showKnown && "rotate-90")} />
                Known skills ({knownGaps.length})
              </button>
              {showKnown ? (
                <div className="mt-3 overflow-x-auto">
                  <GapTable gaps={knownGaps} onLevelChange={setLevel} muted />
                </div>
              ) : null}
            </div>
          ) : null}
        </Panel>

        <Panel>
          <div className="mb-4 flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">Study Plan</h2>
          </div>
          <div className="grid gap-4">
            <label className="grid gap-1.5 text-sm font-medium">
              Timeframe
              <Select value={timeframe} onChange={(event) => setTimeframe(event.target.value as "1 week" | "2 weeks" | "1 month")}>
                <option value="1 week">1 week</option>
                <option value="2 weeks">2 weeks</option>
                <option value="1 month">1 month</option>
              </Select>
            </label>
            {planMutation.error ? <p className="text-sm text-destructive">{(planMutation.error as Error).message}</p> : null}
            <Button onClick={() => planMutation.mutate()} disabled={planMutation.isPending || !profile}>
              {planMutation.isPending ? "Generating..." : "Generate study plan"}
            </Button>
            {studyPlan ? (
              <div className="grid gap-4 text-sm">
                <List title="Top gaps" items={studyPlan.top_gaps} />
                <List title="Priority order" items={studyPlan.priority_order} />
                <div>
                  <h3 className="font-medium">Plan</h3>
                  <div className="mt-2 grid gap-3">
                    {studyPlan.study_plan.map((item) => (
                      <div key={`${item.day}-${item.focus}`} className="rounded-md border border-border bg-muted/40 p-3">
                        <div className="font-medium">{item.day}: {item.focus}</div>
                        <ul className="mt-2 list-inside list-disc text-muted-foreground">
                          {item.tasks.map((task) => (
                            <li key={task}>{task}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
                <List title="Project ideas" items={studyPlan.project_ideas} />
              </div>
            ) : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function GapTable({
  gaps,
  onLevelChange,
  muted = false
}: {
  gaps: SkillGap[];
  onLevelChange: (id: string, level: SkillGap["user_level"]) => void;
  muted?: boolean;
}) {
  if (!gaps.length) {
    return null;
  }
  return (
    <table className={cn("w-full min-w-[860px] text-left text-sm", muted && "opacity-70")}>
      <thead className="border-b border-border text-xs uppercase text-muted-foreground">
        <tr>
          <th className="py-2 pr-4">Skill</th>
          <th className="py-2 pr-4">Sources</th>
          <th className="py-2 pr-4">Count</th>
          <th className="py-2 pr-4">Priority</th>
          <th className="py-2 pr-4">Level</th>
          <th className="py-2 pr-4">Suggested Action</th>
        </tr>
      </thead>
      <tbody>
        {gaps.map((gap) => (
          <tr key={gap.id} className="border-b border-border last:border-0">
            <td className="py-3 pr-4 font-medium">{gap.skill_name}</td>
            <td className="py-3 pr-4">
              <div className="flex flex-wrap gap-1.5">
                {gap.sources.map((source) => (
                  <Badge key={source}>{source.replaceAll("_", " ")}</Badge>
                ))}
              </div>
            </td>
            <td className="py-3 pr-4">{gap.count}</td>
            <td className="py-3 pr-4">
              <Badge tone={priorityTone[gap.priority]}>{gap.priority}</Badge>
            </td>
            <td className="py-3 pr-4">
              <Select
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
