"use client";

import { useQuery } from "@tanstack/react-query";
import { Archive, ArrowRight, BriefcaseBusiness, ClipboardList, RefreshCw } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { jobStatuses } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function DashboardPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard
  });

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Dashboard"
        description="A compact view of application activity, resume tailoring work, interview practice, and current skill gaps."
        action={
          <Button variant="secondary" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        }
      />

      {error ? <Panel className="border-rose-200 bg-rose-50 text-sm text-rose-700">{(error as Error).message}</Panel> : null}
      {isLoading ? <Panel>Loading dashboard...</Panel> : null}

      {data ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Metric title="Active Jobs" value={data.total_jobs} icon={<BriefcaseBusiness className="h-4 w-4" />} />
            <Metric title="Archived" value={data.archived_jobs} icon={<Archive className="h-4 w-4" />} />
            <Metric title="Need Tailoring" value={data.needs_resume_tailoring} icon={<ArrowRight className="h-4 w-4" />} />
            <Metric title="Interviewing" value={data.interviewing} icon={<ClipboardList className="h-4 w-4" />} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <Panel>
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-base font-semibold">Status Pipeline</h2>
                <Link href="/jobs" className="text-sm font-medium text-primary">
                  Manage jobs
                </Link>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {jobStatuses.map((status) => (
                  <div key={status} className="rounded-md border border-border bg-muted/40 p-3">
                    <div className="text-sm font-medium">{status}</div>
                    <div className="mt-2 text-2xl font-semibold">{data.by_status[status] ?? 0}</div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel>
              <h2 className="text-base font-semibold">Next Action</h2>
              <p className="mt-3 text-sm text-muted-foreground">{data.next_recommended_action}</p>
              <div className="mt-5 flex gap-2">
                <Link href="/jobs">
                  <Button size="sm">Add job</Button>
                </Link>
                <Link href="/interview">
                  <Button size="sm" variant="secondary">
                    Practice
                  </Button>
                </Link>
              </div>
            </Panel>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Panel>
              <h2 className="text-base font-semibold">Top Skill Gaps</h2>
              <div className="mt-4 grid gap-3">
                {data.top_skill_gaps.length ? (
                  data.top_skill_gaps.map((gap) => (
                    <div key={gap.id} className="flex items-center justify-between gap-3 border-b border-border pb-3 last:border-0 last:pb-0">
                      <div>
                        <div className="font-medium">{gap.skill_name}</div>
                        <div className="text-xs text-muted-foreground">{gap.suggested_action}</div>
                      </div>
                      <Badge tone={gap.priority === "high" ? "bad" : gap.priority === "medium" ? "warn" : "neutral"}>
                        {gap.priority}
                      </Badge>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">Analyze jobs or resume matches to populate gaps.</p>
                )}
              </div>
            </Panel>

            <Panel>
              <h2 className="text-base font-semibold">Recent Interview Practice</h2>
              <div className="mt-4 grid gap-3">
                {data.recent_interviews.length ? (
                  data.recent_interviews.map((session) => (
                    <div key={session.id} className="border-b border-border pb-3 last:border-0 last:pb-0">
                      <div className="font-medium">{session.title ?? "Interview session"}</div>
                      <div className="text-xs text-muted-foreground">
                        {session.mode.replace("_", " ")} - {formatDate(session.updated_at)}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">Generate questions to start an interview history.</p>
                )}
              </div>
            </Panel>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Metric({ title, value, icon }: { title: string; value: number; icon: React.ReactNode }) {
  return (
    <Panel>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-muted-foreground">{title}</div>
        <div className="grid h-8 w-8 place-items-center rounded-md bg-accent text-accent-foreground">{icon}</div>
      </div>
      <div className="mt-4 text-3xl font-semibold">{value}</div>
    </Panel>
  );
}
