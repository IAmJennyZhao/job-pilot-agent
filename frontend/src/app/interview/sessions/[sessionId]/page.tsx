"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { FeedbackDetails, weakPointLabels } from "@/components/interview/feedback-details";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { groupSessionEntries, sessionTarget } from "@/lib/interview";
import { formatDate } from "@/lib/utils";

export default function InterviewSessionDetailPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;

  const { data: session, isLoading } = useQuery({
    queryKey: ["interview-session", sessionId],
    queryFn: () => api.interviewSession(sessionId),
    enabled: Boolean(sessionId)
  });
  const { data: jobs = [] } = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs() });

  const jobsById = React.useMemo(() => new Map(jobs.map((job) => [job.id, job])), [jobs]);
  const entries = React.useMemo(() => (session ? groupSessionEntries(session.messages) : []), [session]);
  const hasUnanswered = entries.some((entry) => !entry.answer);
  const answeredCount = entries.filter((entry) => entry.answer).length;

  const startAnotherHref = React.useMemo(() => {
    if (!session) return "/interview";
    const params = new URLSearchParams();
    if (session.job_id) {
      params.set("jobId", session.job_id);
    } else {
      if (session.target_category) params.set("targetCategory", session.target_category);
      if (session.target_role) params.set("targetRole", session.target_role);
    }
    params.set("stage", session.stage);
    params.set("questionType", session.question_type);
    return `/interview?${params.toString()}`;
  }, [session]);

  return (
    <div className="grid gap-6">
      <PageHeader
        title={session ? session.title ?? sessionTarget(session, jobsById) : "Interview session"}
        description={
          session
            ? `${session.stage.replace("_", " ")} - ${session.question_type.replace("_", " ")} - ${answeredCount} of ${entries.length} answered - Updated ${formatDate(session.updated_at)}`
            : "Loading session..."
        }
        action={
          <Link href="/interview">
            <Button variant="secondary">
              <ArrowLeft className="h-4 w-4" />
              Back to Interview Practice
            </Button>
          </Link>
        }
      />

      {isLoading ? <Panel>Loading session...</Panel> : null}

      {session ? (
        <>
          <div className="flex flex-wrap gap-2">
            {hasUnanswered ? (
              <Link href={`/interview?resumeSessionId=${session.id}`}>
                <Button>Resume practice</Button>
              </Link>
            ) : null}
            <Link href={startAnotherHref}>
              <Button variant="secondary">Start another session</Button>
            </Link>
          </div>

          <div className="grid gap-4">
            {entries.length ? (
              entries.map((entry, index) => (
                <Panel key={entry.questionId}>
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-muted-foreground">Q{index + 1}</span>
                    {entry.questionType ? <Badge>{entry.questionType.replace("_", " ")}</Badge> : null}
                    {entry.weakPointTags.map((tag) => (
                      <Badge key={tag} tone="warn">
                        {weakPointLabels[tag] ?? tag.replace("_", " ")}
                      </Badge>
                    ))}
                    {!entry.answer ? <Badge tone="bad">Not answered</Badge> : null}
                  </div>
                  <p className="text-base font-medium leading-7">{entry.question}</p>
                  {entry.whyItMatters ? <p className="mt-1 text-xs text-muted-foreground">{entry.whyItMatters}</p> : null}
                  {entry.answer ? (
                    <div className="mt-4 grid gap-4">
                      <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
                        <h4 className="font-medium">Your answer</h4>
                        <p className="mt-1 leading-6 text-muted-foreground">{entry.answer}</p>
                      </div>
                      {entry.feedback ? (
                        <div className="rounded-md border border-border bg-muted/40 p-4 text-sm">
                          <FeedbackDetails feedback={entry.feedback} />
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </Panel>
              ))
            ) : (
              <Panel>
                <p className="text-sm text-muted-foreground">No questions recorded for this session yet.</p>
              </Panel>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
