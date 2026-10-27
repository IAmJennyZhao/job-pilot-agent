"use client";

import { useConfirm } from "@/components/ui/confirm-provider";
import { PracticeTimer, usePracticeTimer } from "@/components/interview/practice-timer";
import { AttemptHistory } from "@/components/interview/attempt-history";
import { RetainedView } from "@/components/layout/retained-view";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Brain, ClipboardList, ExternalLink, MessageSquareText, Play, RotateCcw, Sparkles, Target, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { FeedbackDetails, weakPointLabels } from "@/components/interview/feedback-details";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { LocalTab, LocalTabs } from "@/components/ui/local-tabs";
import { MoreMenu } from "@/components/ui/more-menu";
import { useDraft } from "@/lib/use-draft";
import { api } from "@/lib/api";
import { hasUnansweredPrompts, sessionTarget } from "@/lib/interview";
import {
  jobCategories,
  type InterviewFeedback,
  type InterviewInsights,
  type InterviewPracticeFeedback,
  type InterviewPracticeQuestion,
  type InterviewPracticeSet,
  type InterviewQuestionType,
  type InterviewScoreEntry,
  type InterviewSession,
  type InterviewStage,
  type InterviewTrendPoint,
  type WeakPointTag,
  type JobCategory
} from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";
import { localViewHref, pushLocalView, selectLocalView } from "@/lib/workspace-navigation";

const stages: Array<{ value: InterviewStage; label: string }> = [
  { value: "mixed", label: "Mixed" },
  { value: "recruiter_screen", label: "Recruiter screen" },
  { value: "tech_screen", label: "Tech screen" },
  { value: "final_interview", label: "Final interview" }
];

const questionTypes: Array<{ value: InterviewQuestionType; label: string }> = [
  { value: "mixed", label: "Mixed" },
  { value: "technical", label: "Technical" },
  { value: "behavioral", label: "Behavioral" },
  { value: "company", label: "Company" },
  { value: "resume", label: "Resume" },
  { value: "role_specific", label: "Role specific" },
  { value: "system_design", label: "System design" }
];

export default function InterviewPage() {
  return (
    <React.Suspense fallback={<InterviewPageFallback />}>
      <InterviewPageContent />
    </React.Suspense>
  );
}

function InterviewPageFallback() {
  return (
    <div className="grid gap-6">
      <PageHeader title="Interview" />
      <Panel>Loading interview workspace...</Panel>
    </div>
  );
}

function InterviewPageContent() {
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeView = selectLocalView(searchParams, ["practice", "history"] as const, "practice");
  const requestedJobId = searchParams.get("jobId") ?? "";
  const requestedTargetCategory = searchParams.get("targetCategory") as JobCategory | null;
  const requestedTargetRole = searchParams.get("targetRole");
  const requestedStage = searchParams.get("stage") as InterviewStage | null;
  const requestedQuestionType = searchParams.get("questionType") as InterviewQuestionType | null;
  const resumeSessionId = searchParams.get("resumeSessionId");

  const jobsQuery = useQuery({ queryKey: ["jobs", "interview-all"], queryFn: () => api.jobs({ includeArchived: true }) });
  const jobs = jobsQuery.data ?? [];
  const sessionsQuery = useQuery({ queryKey: ["interview-sessions"], queryFn: api.interviewSessions, enabled: activeView === "history" });
  const sessions = sessionsQuery.data ?? [];
  const insightsQuery = useQuery({ queryKey: ["interview-insights"], queryFn: api.interviewInsights, enabled: activeView === "history" });
  const insights = insightsQuery.data;
  const resumeQuery = useQuery({
    queryKey: ["interview-resume", resumeSessionId],
    queryFn: () => api.resumeSession(resumeSessionId as string),
    enabled: Boolean(resumeSessionId)
  });

  const resumeData = resumeQuery.data;
  const [targetMode, setTargetMode] = React.useState<"job" | "role">(requestedJobId ? "job" : "role");
  const [jobSearch, setJobSearch] = React.useState("");
  const [jobId, setJobId] = React.useState(requestedJobId);
  const [targetCategory, setTargetCategory] = React.useState<JobCategory>("AI/ML Engineer");
  const [targetRole, setTargetRole] = React.useState("");
  const [stage, setStage] = React.useState<InterviewStage>("mixed");
  const [questionType, setQuestionType] = React.useState<InterviewQuestionType>("mixed");
  const [count, setCount] = React.useState(6);
  const practiceDraft = useDraft<{ practiceSet: InterviewPracticeSet | null; queue: InterviewPracticeQuestion[]; activeQuestionId: string; answers: Record<string, string> }>("interview-practice", { practiceSet: null, queue: [], activeQuestionId: "", answers: {} });
  const { practiceSet, queue, activeQuestionId } = practiceDraft.value;
  const setPracticeSet = (value: InterviewPracticeSet | null) => practiceDraft.setValue(current => ({ ...current, practiceSet: value }));
  const setQueue: React.Dispatch<React.SetStateAction<InterviewPracticeQuestion[]>> = value => practiceDraft.setValue(current => ({ ...current, queue: typeof value === "function" ? value(current.queue) : value }));
  const setActiveQuestionId = (value: string) => practiceDraft.setValue(current => ({ ...current, activeQuestionId: value }));
  const answerKey = `${practiceSet?.session_id ?? ""}:${activeQuestionId}`;
  const timer = usePracticeTimer(answerKey);
  const answer = practiceDraft.value.answers[answerKey] ?? "";
  const setAnswer = (value: string) => practiceDraft.setValue(current => ({ ...current, answers: { ...current.answers, [answerKey]: value } }));
  const [feedback, setFeedback] = React.useState<InterviewPracticeFeedback | null>(null);
  React.useEffect(() => {
    const revealShortcut = () => {
      const anchor = window.location.hash;
      if (["#command-center", "#interview-insights", "#current-attempts"].includes(anchor) && activeView !== "history") {
        window.history.replaceState(null, "", localViewHref("/interview", searchParams, "history", anchor));
        return;
      }
      requestAnimationFrame(() => {
        const target = document.getElementById(anchor.slice(1));
        const disclosure = target?.closest("details");
        if (disclosure) disclosure.open = true;
        target?.scrollIntoView({ block: "start" });
      });
    };
    revealShortcut();
    window.addEventListener("hashchange", revealShortcut);
    return () => window.removeEventListener("hashchange", revealShortcut);
  }, [activeView, searchParams, sessionsQuery.isLoading, insightsQuery.isLoading]);

  const jobsById = React.useMemo(() => new Map(jobs.map((job) => [job.id, job])), [jobs]);
  const activeQuestion = queue.find((question) => question.id === activeQuestionId) ?? queue[0] ?? null;
  const isActive = Boolean(practiceSet && activeQuestion && !resumeSessionId && !searchParams.has("new") && !requestedTargetCategory && !requestedTargetRole && (!requestedJobId || practiceSet.job_id === requestedJobId));

  React.useEffect(() => {
    if (requestedJobId) {
      setTargetMode("job");
      setJobId(requestedJobId);
    }
  }, [requestedJobId]);

  React.useEffect(() => {
    if (targetMode === "job" && !jobId && jobs[0]) {
      setJobId(jobs[0].id);
    }
  }, [jobId, jobs, targetMode]);

  React.useEffect(() => {
    if (!requestedJobId && (requestedTargetCategory || requestedTargetRole)) {
      setTargetMode("role");
      if (requestedTargetCategory) setTargetCategory(requestedTargetCategory);
      if (requestedTargetRole) setTargetRole(requestedTargetRole);
    }
    if (requestedStage) setStage(requestedStage);
    if (requestedQuestionType) setQuestionType(requestedQuestionType);
  }, [requestedJobId, requestedTargetCategory, requestedTargetRole, requestedStage, requestedQuestionType]);

  React.useEffect(() => {
    if (!resumeData?.questions.length || !practiceDraft.ready) return;
    setPracticeSet(resumeData);
    setQueue(resumeData.questions);
    setActiveQuestionId(resumeData.questions[0]?.id ?? "");
    setFeedback(null);
    router.replace("/interview");
  }, [resumeData, router, practiceDraft.ready]);

  const createPracticeSet = useMutation({
    mutationFn: () =>
      api.createPracticeSet({
        job_id: targetMode === "job" ? jobId : null,
        target_category: targetMode === "role" ? targetCategory : null,
        target_role: targetMode === "role" ? targetRole || null : null,
        stage,
        question_type: questionType,
        count
      }),
    onSuccess: (data) => {
      router.replace("/interview");
      setPracticeSet(data);
      setQueue(data.questions);
      setActiveQuestionId(data.questions[0]?.id ?? "");
      setFeedback(null);
      queryClient.invalidateQueries({ queryKey: ["interview-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["interview-insights"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const evaluateAnswer = useMutation({
    mutationFn: () => {
      if (!practiceSet || !activeQuestion) throw new Error("Start a practice set first.");
      return api.evaluatePracticeAnswer({
        session_id: practiceSet.session_id,
        question_id: activeQuestion.id,
        answer,
        elapsed_seconds: timer.stop() || null,
        time_limit_seconds: timer.limit
      });
    },
    onSuccess: (data) => {
      setFeedback(data);
      timer.reset();
      if (data.follow_up) {
        const followUp = data.follow_up;
        setQueue((current) => {
          if (current.some((question) => question.id === followUp.id)) return current;
          return [...current, followUp];
        });
      }
      queryClient.invalidateQueries({ queryKey: ["interview-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["interview-attempts"] });
      queryClient.invalidateQueries({ queryKey: ["interview-insights"] });
      queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const canStart = targetMode === "job" ? Boolean(jobs.some(job => job.id === jobId) && !jobsQuery.isLoading && !jobsQuery.error) : Boolean(targetCategory || targetRole.trim());
  const resetPracticeSet = () => {
    timer.stop();
    setPracticeSet(null);
    setQueue([]);
    setActiveQuestionId("");
    setFeedback(null);
  };

  return (
    <div className="grid gap-6">
      <PageHeader title="Interview" />
      <LocalTabs label="Interview views">
        <LocalTab active={activeView === "practice"} onClick={() => pushLocalView("/interview", searchParams, "practice")}>Practice</LocalTab>
        <LocalTab active={activeView === "history"} onClick={() => pushLocalView("/interview", searchParams, "history")}>History</LocalTab>
        <MoreMenu items={[
          { label: "Command Center", href: localViewHref("/interview", searchParams, "history", "#command-center") },
          { label: "Interview insights", href: localViewHref("/interview", searchParams, "history", "#interview-insights") },
          ...(isActive ? [{ label: "Practice timer", href: localViewHref("/interview", searchParams, "practice", "#practice-timer") }] : [])
        ]} />
      </LocalTabs>
      <RetainedView active={activeView === "practice"}>
      <div className="grid gap-6">
      {jobsQuery.error && targetMode === "job" ? <Panel><p role="alert">Could not load job choices: {jobsQuery.error.message}</p><Button variant="secondary" onClick={() => jobsQuery.refetch()}>Retry job choices</Button></Panel> : null}
      {resumeSessionId && resumeQuery.isLoading ? <Panel>Loading the requested session...</Panel> : null}
      {resumeSessionId && resumeQuery.error ? <Panel><p role="alert">Could not load the requested session: {resumeQuery.error.message}</p><Button variant="secondary" onClick={() => resumeQuery.refetch()}>Retry session</Button></Panel> : null}
      {resumeSessionId && resumeData && !resumeData.questions.length ? <Panel><p role="status">No unanswered questions remain in this session. Your saved practice draft is still available.</p><div className="mt-3 flex flex-wrap gap-3"><Link className="underline" href={`/interview/sessions/${resumeSessionId}`}>Review this session</Link><Link className="underline" href="/interview?tab=practice">Return to saved practice draft</Link></div></Panel> : null}
      {resumeSessionId && resumeQuery.error ? <Link href="/interview" className="text-sm font-medium underline">Return to saved practice draft</Link> : null}
      {practiceDraft.dirty ? <p role="status" className="text-sm text-muted-foreground">{practiceDraft.storageError ? "Draft recovery is unavailable. Keep this page open until you submit your answer." : "Draft saved on this browser."}</p> : null}
      {isActive && practiceSet && activeQuestion ? (
        <Panel>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <MessageSquareText className="h-4 w-4 text-primary" />
              <div>
                <h2 className="text-base font-semibold">{sessionTarget(practiceSet, jobsById)}</h2>
                <p className="text-xs text-muted-foreground">
                  {practiceSet.stage.replace("_", " ")} - {practiceSet.question_type.replace("_", " ")}
                </p>
              </div>
            </div>
            <Button variant="secondary" onClick={resetPracticeSet} disabled={evaluateAnswer.isPending}>
              <Target className="h-4 w-4" />
              New practice set
            </Button>
          </div>
          <div className="grid gap-4">
            <PracticeSetStats practiceSet={practiceSet} />
            <details className="rounded-md border border-border p-3"><summary className="cursor-pointer text-sm font-medium">Questions: {queue.findIndex(question => question.id === activeQuestion.id) + 1} of {queue.length}</summary><div className="mt-3"><QuestionQueue questions={queue} activeQuestionId={activeQuestion.id} onSelect={id => { if (!evaluateAnswer.isPending) { timer.stop(); setActiveQuestionId(id); setFeedback(null); } }} /></div></details>
            <div className="rounded-md border border-border bg-muted/30 p-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Badge>{activeQuestion.question_type.replace("_", " ")}</Badge>
                <Badge>{activeQuestion.source.replace("_", " ")}</Badge>
                {activeQuestion.why_it_matters ? <span className="text-xs text-muted-foreground">{activeQuestion.why_it_matters}</span> : null}
              </div>
              <p className="text-base font-medium leading-7">{activeQuestion.content}</p>
            </div>
            <Field label="Your answer">
              <Textarea disabled={evaluateAnswer.isPending} value={answer} onChange={(event) => setAnswer(event.target.value)} className="min-h-44" />
            </Field>
            <div id="practice-timer" className="scroll-mt-28"><PracticeTimer timer={timer} disabled={evaluateAnswer.isPending} /></div>
            {evaluateAnswer.error ? <p className="text-sm text-destructive">{(evaluateAnswer.error as Error).message}</p> : null}
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => evaluateAnswer.mutate()} disabled={!answer.trim() || evaluateAnswer.isPending}>
                <Sparkles className="h-4 w-4" />
                {evaluateAnswer.isPending ? "Evaluating..." : "Evaluate answer"}
              </Button>
              <Button variant="secondary" onClick={async () => { if (await confirm("Clear this answer draft?")) setAnswer(""); }} disabled={!answer.trim() || evaluateAnswer.isPending}>
                <RotateCcw className="h-4 w-4" />
                Clear
              </Button>
            </div>
            {feedback ? <FeedbackPanel feedback={feedback} /> : null}
            <Button className="justify-self-start" variant="secondary" onClick={() => window.history.pushState(null, "", localViewHref("/interview", searchParams, "history", "#current-attempts"))}>Review attempts in History</Button>
          </div>
        </Panel>
      ) : (
        <div className="grid gap-4">
          <Panel>
            <div className="mb-4 flex items-center gap-2">
              <Target className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold">Practice Target</h2>
            </div>
            <fieldset disabled={createPracticeSet.isPending} className="grid min-w-0 gap-4">
              <div className="grid grid-cols-2 gap-2 rounded-md border border-border bg-muted p-1">
                <button
                  className={cn("rounded px-3 py-2 text-sm font-medium", targetMode === "job" ? "bg-card-strong text-primary shadow-sm" : "text-muted-foreground")}
                  aria-pressed={targetMode === "job"} onClick={() => setTargetMode("job")}
                  type="button"
                >
                  Saved job
                </button>
                <button
                  className={cn("rounded px-3 py-2 text-sm font-medium", targetMode === "role" ? "bg-card-strong text-primary shadow-sm" : "text-muted-foreground")}
                  aria-pressed={targetMode === "role"} onClick={() => setTargetMode("role")}
                  type="button"
                >
                  General role
                </button>
              </div>

              {targetMode === "job" ? (
                <div className="grid gap-3"><Field label="Find a saved job"><Input value={jobSearch} onChange={event => setJobSearch(event.target.value)} placeholder="Company or role" /></Field><Field label="Saved job">
                  <Select aria-label="Saved job" value={jobId} onChange={(event) => setJobId(event.target.value)}>
                    {!jobs.length ? <option value="">No saved jobs - add one in Jobs or practice a general role</option> : null}
                    {[{ label: "Active opportunities", closed: false }, { label: "Closed and archived", closed: true }].map(group => <optgroup key={group.label} label={group.label}>{jobs.filter(job => ["Archived", "Rejected", "Withdrawn", "Ghosted"].includes(job.status) === group.closed && (job.id === jobId || `${job.company} ${job.role_title}`.toLowerCase().includes(jobSearch.toLowerCase()))).map(job => <option key={job.id} value={job.id}>{job.company} — {job.role_title} ({job.status})</option>)}</optgroup>)}
                  </Select>
                </Field><p className="text-xs text-muted-foreground">The selected job stays visible while searching.</p></div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Category">
                    <Select value={targetCategory} onChange={(event) => setTargetCategory(event.target.value as JobCategory)}>
                      {jobCategories.map((category) => (
                        <option key={category} value={category}>
                          {category}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Role or focus">
                    <Input value={targetRole} onChange={(event) => setTargetRole(event.target.value)} placeholder="AI Platform Engineer" />
                  </Field>
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-3"><Field label="Stage">
                <Select value={stage} onChange={(event) => setStage(event.target.value as InterviewStage)}>
                  {stages.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Question type">
                <Select value={questionType} onChange={(event) => setQuestionType(event.target.value as InterviewQuestionType)}>
                  {questionTypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Count">
                <Select value={count} onChange={(event) => setCount(Number(event.target.value))}>
                  {[3, 5, 6, 10].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </Field>
              </div>
              {createPracticeSet.error ? <p className="text-sm text-destructive">{(createPracticeSet.error as Error).message}</p> : null}
              <Button className="justify-self-start" onClick={() => createPracticeSet.mutate()} disabled={!practiceDraft.ready || !canStart || createPracticeSet.isPending || Boolean(resumeSessionId && resumeQuery.isLoading)}>
                <Play className="h-4 w-4" />
                {createPracticeSet.isPending ? "Starting..." : "Start practice"}
              </Button>
            </fieldset>
          </Panel>
        </div>
      )}
      </div>
      </RetainedView>
      <RetainedView active={activeView === "history"}>
        <div className="grid gap-6">
          {insightsQuery.isLoading ? <Panel>Loading interview insights...</Panel> : insightsQuery.error ? <Panel><p role="alert">Could not load interview insights: {insightsQuery.error.message}</p><Button variant="secondary" onClick={() => insightsQuery.refetch()}>Retry insights</Button></Panel> : <InsightsPanel insights={insights} />}
          {isActive && practiceSet && activeQuestion ? <details className="rounded-lg border border-border bg-card p-5 sm:p-6">
            <summary id="current-attempts" className="scroll-mt-28 cursor-pointer font-semibold">Current question: attempts & comparisons</summary>
            <p className="my-3 text-sm text-muted-foreground">{activeQuestion.content}</p>
            <AttemptHistory key={activeQuestion.id} questionId={activeQuestion.id} disabled={evaluateAnswer.isPending} onRevise={async value => {
              if (!answer.trim() || answer === value || await confirm("Replace this answer draft with the selected attempt?")) {
                setAnswer(value); timer.reset(); setFeedback(null); pushLocalView("/interview", searchParams, "practice");
              }
            }} />
          </details> : null}
          {sessionsQuery.isLoading ? <Panel>Loading session history...</Panel> : sessionsQuery.error ? <Panel><p role="alert">Could not load session history: {sessionsQuery.error.message}</p><Button variant="secondary" onClick={() => sessionsQuery.refetch()}>Retry sessions</Button></Panel> : <SessionHistoryPanel sessions={sessions} jobsById={jobsById} />}
          {jobsQuery.error ? <p role="alert" className="text-sm">Job titles could not load: {jobsQuery.error.message}. Sessions are still available.</p> : null}
          {!sessionsQuery.isLoading && !insightsQuery.isLoading && !sessionsQuery.error && !insightsQuery.error ? <details className="rounded-lg border border-border bg-card p-5 sm:p-6"><summary className="cursor-pointer font-semibold">Score trends & session cues</summary><div className="mt-4"><CommandCenterPanel insights={insights} sessions={sessions} jobsById={jobsById} /></div></details> : null}
        </div>
      </RetainedView>
    </div>
  );
}

function scoreTone(score: number): "good" | "warn" | "bad" {
  return score >= 75 ? "good" : score >= 50 ? "warn" : "bad";
}

function labelForWeakPoint(tag: string) {
  return weakPointLabels[tag] ?? tag.replace("_", " ");
}

function CommandCenterPanel({
  insights,
  sessions,
  jobsById
}: {
  insights?: InterviewInsights;
  sessions: InterviewSession[];
  jobsById: Map<string, { company: string; role_title: string }>;
}) {
  const latestScore = insights?.recent_scores[0] ?? null;
  const topWeakPoint = insights?.weak_points[0] ?? null;
  const resumableSession = sessions.find(hasUnansweredPrompts);
  const nextAction = !latestScore
    ? "Start a first scored practice round."
    : topWeakPoint
      ? `Work on ${labelForWeakPoint(topWeakPoint.tag).toLowerCase()} next.`
      : latestScore.score < 75
        ? "Review the latest feedback before starting another set."
        : "Keep the streak going with a fresh question set.";

  return (
    <Panel>
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-primary" />
        <h2 id="command-center" className="scroll-mt-28 text-base font-semibold">Score trends & session cues</h2>
      </div>

      <div className="grid gap-4">
        <div className="grid gap-3 md:grid-cols-3">
          <TrendMetric title="Overall score" points={insights?.trends?.overall ?? []} />
          <TrendMetric title="Overall score: Knowledge tags" points={insights?.trends?.knowledge ?? []} />
          <TrendMetric title="Overall score: Interview skills tags" points={insights?.trends?.interview_skills ?? []} />
        </div>
        <p className="text-xs text-muted-foreground">Knowledge and Interview skills filter overall answer scores by feedback tags. They are not independent subscores, and the same answer can appear in both series. These trends use up to the latest 50 scored answers.</p>
        <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">Which feedback tags are included?</summary><p className="mt-2">Knowledge: technical depth, missing skill and company context. Interview skills: answer structure, specific evidence, role alignment, concision, communication clarity and resume positioning.</p></details>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-md border border-border bg-card-strong/60 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <Brain className="h-4 w-4 text-primary" />
              Next action
            </div>
            <p className="text-sm leading-6 text-muted-foreground">{nextAction}</p>
            {topWeakPoint ? (
              <div className="mt-3">
                <Badge tone="warn">
                  {labelForWeakPoint(topWeakPoint.tag)} ({topWeakPoint.count})
                </Badge>
              </div>
            ) : null}
          </div>

          <div className="rounded-md border border-border bg-card-strong/60 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <ClipboardList className="h-4 w-4 text-primary" />
              Session cue
            </div>
            {resumableSession ? (
              <div className="grid gap-3">
                <p className="text-sm leading-6 text-muted-foreground">{sessionTarget(resumableSession, jobsById)}</p>
                <Link href={`/interview?resumeSessionId=${resumableSession.id}`}>
                  <Button size="sm" variant="secondary">Continue unanswered questions</Button>
                </Link>
              </div>
            ) : (
              <p className="text-sm leading-6 text-muted-foreground">No unfinished practice set is waiting.</p>
            )}
          </div>
        </div>
      </div>
    </Panel>
  );
}
function TrendMetric({ title, points }: { title: string; points: InterviewTrendPoint[] }) {
  const latest = points.at(-1)?.score ?? null;
  const first = points[0]?.score ?? null;
  const delta = latest != null && first != null && points.length > 1 ? latest - first : null;
  return (
    <section aria-label={title} className="rounded-md border border-border bg-muted/25 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">{title}</span>
        <span className="shrink-0 text-sm font-semibold">{latest == null ? "--" : `${latest}/100`}</span>
      </div>
      <TrendSparkline points={points} title={title} />
      <div className="mt-1 text-[11px] text-muted-foreground">
        {points.length} scored answers{delta == null ? "" : ` · ${delta >= 0 ? "+" : ""}${delta} points from first shown`}
      </div>
    </section>
  );
}

function TrendSparkline({ points, title }: { points: InterviewTrendPoint[]; title: string }) {
  const width = 160;
  const height = 44;
  const padding = 4;
  if (!points.length) {
    return <div className="mt-2 h-11 rounded bg-muted/60" />;
  }

  const values = points.map((point) => point.score);
  const min = Math.min(0, ...values);
  const max = Math.max(100, ...values);
  const range = Math.max(1, max - min);
  const coordinates = points.map((point, index) => {
    const x = points.length === 1 ? width / 2 : padding + (index / (points.length - 1)) * (width - padding * 2);
    const y = padding + ((max - point.score) / range) * (height - padding * 2);
    return { x, y };
  });
  const path = coordinates.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
  const last = coordinates.at(-1)!;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="mt-2 h-11 w-full" role="img" aria-label={`${title}: ${points.map(point => point.score).join(", ")} in chronological order`}>
      <path d={`M ${padding} ${height - padding} L ${width - padding} ${height - padding}`} stroke="hsl(var(--border))" strokeWidth="1" />
      {points.length > 1 ? <path d={path} fill="none" stroke="hsl(var(--chart-tech))" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /> : null}
      <circle cx={last.x} cy={last.y} r="3.5" fill="hsl(var(--chart-tech))" />
    </svg>
  );
}

function PracticeSetStats({ practiceSet }: { practiceSet: InterviewPracticeSet }) {
  return (
    <div className="flex flex-wrap gap-2 text-xs">
      <Badge>{practiceSet.reused_count} reused</Badge>
      <Badge>{practiceSet.generated_count} new</Badge>
    </div>
  );
}

function QuestionQueue({
  questions,
  activeQuestionId,
  onSelect
}: {
  questions: InterviewPracticeQuestion[];
  activeQuestionId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="grid gap-2">
      {questions.map((question, index) => (
        <button
          key={question.id}
          className={cn(
            "rounded-md border p-3 text-left text-sm transition",
            question.id === activeQuestionId ? "border-primary bg-primary/5" : "border-border bg-card-strong/75 hover:bg-muted"
          )}
          onClick={() => onSelect(question.id)}
          type="button"
        >
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground">Q{index + 1}</span>
            <Badge>{question.source.replace("_", " ")}</Badge>
            {question.weak_point_tags.map((tag) => (
              <Badge key={tag} tone="warn">
                {weakPointLabels[tag] ?? tag.replace("_", " ")}
              </Badge>
            ))}
          </div>
          <div className="line-clamp-2 leading-6">{question.content}</div>
        </button>
      ))}
    </div>
  );
}

function FeedbackPanel({ feedback }: { feedback: InterviewPracticeFeedback }) {
  return (
    <div className="rounded-md border border-border bg-muted/40 p-4 text-sm">
      <FeedbackDetails feedback={feedback} />
      {feedback.follow_up ? (
        <div className="mt-3 rounded-md border border-border bg-card-strong/75 p-3">
          <h4 className="font-medium">Queued follow-up</h4>
          <p className="mt-1 text-muted-foreground">{feedback.follow_up.content}</p>
        </div>
      ) : null}
    </div>
  );
}

type InsightSelection =
  | { kind: "weak_point"; weakPoint: InterviewInsights["weak_points"][number] }
  | { kind: "score"; score: InterviewScoreEntry };

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function scoreEntryFeedback(entry: InterviewScoreEntry): InterviewFeedback {
  const feedback = entry.feedback ?? {};
  return {
    score: entry.score,
    what_went_well: asStringArray(feedback.what_went_well),
    what_was_missing: asStringArray(feedback.what_was_missing),
    suggested_better_answer: typeof feedback.suggested_better_answer === "string" ? feedback.suggested_better_answer : "",
    coaching_notes: asStringArray(feedback.coaching_notes),
    evidence_to_add: asStringArray(feedback.evidence_to_add),
    weak_point_tags: asStringArray(feedback.weak_point_tags) as WeakPointTag[],
    missing_skill_names: asStringArray(feedback.missing_skill_names),
    follow_up_question: typeof feedback.follow_up_question === "string" ? feedback.follow_up_question : "",
    session_id: entry.session_id,
    follow_up_question_id: typeof feedback.follow_up_question_id === "string" ? feedback.follow_up_question_id : null
  };
}

function InsightsPanel({ insights }: { insights?: InterviewInsights }) {
  const [selection, setSelection] = React.useState<InsightSelection | null>(null);

  return (
    <Panel>
      <div className="mb-4 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-primary" />
        <h2 id="interview-insights" className="scroll-mt-28 text-base font-semibold">Interview Insights</h2>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">Review recurring weaknesses and recent attempts first. Patterns use the latest 50 scored answers; one answer can have multiple feedback tags. Scores are AI coaching estimates.</p>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium">Weaknesses to revisit</h3>
          <p className="mt-1 text-xs text-muted-foreground">Most frequent feedback tags first.</p>
          <div className="mt-2 grid gap-2">
            {insights?.weak_points.length ? (
              insights.weak_points.slice(0, 6).map((item) => (
                <button
                  key={item.tag}
                  type="button"
                  onClick={() => setSelection({ kind: "weak_point", weakPoint: item })}
                  className={cn(
                    "rounded-md border p-3 text-left text-sm transition hover:bg-muted",
                    selection?.kind === "weak_point" && selection.weakPoint.tag === item.tag
                      ? "border-primary bg-primary/5"
                      : "border-border bg-muted/40"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{labelForWeakPoint(item.tag)}</span>
                    <Badge tone="warn">{item.count}</Badge>
                  </div>
                  {item.latest_note ? <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.latest_note}</p> : null}
                </button>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No weak-point data yet.</p>
            )}
          </div>
        </div>
        <div>
          <h3 className="text-sm font-medium">Recent attempts</h3>
          <p className="mt-1 text-xs text-muted-foreground">Newest evaluated answers first. Select one for its answer and feedback.</p>
          <div className="mt-2 grid gap-2">
            {insights?.recent_scores.length ? (
              insights.recent_scores.slice(0, 5).map((item) => (
                <button
                  key={item.message_id}
                  type="button"
                  onClick={() => setSelection({ kind: "score", score: item })}
                  className={cn(
                    "rounded-md border p-3 text-left text-sm transition hover:bg-muted",
                    selection?.kind === "score" && selection.score.message_id === item.message_id
                      ? "border-primary bg-primary/5"
                      : "border-border bg-muted/40"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="line-clamp-1 font-medium">{item.question}</span>
                    <Badge tone={scoreTone(item.score)}>{item.score}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{formatDate(item.created_at)}</div>
                </button>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No evaluated answers yet.</p>
            )}
          </div>
        </div>
      </div>
      {selection ? <InsightDrawer selection={selection} onClose={() => setSelection(null)} /> : null}
    </Panel>
  );
}

function InsightDrawer({ selection, onClose }: { selection: InsightSelection; onClose: () => void }) {
  const entries = selection.kind === "weak_point" ? selection.weakPoint.examples : [selection.score];
  const title = selection.kind === "weak_point" ? labelForWeakPoint(selection.weakPoint.tag) : "Recent score";
  const detail = selection.kind === "weak_point" ? `${selection.weakPoint.count} tagged score${selection.weakPoint.count === 1 ? "" : "s"}` : formatDate(selection.score.created_at);

  return (
    <div className="mt-5 rounded-md border border-border bg-card-strong/65 p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
        </div>
        <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close insight details">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="grid gap-4">
        {entries.length ? (
          entries.map((entry) => <ScoreEntryDetails key={entry.message_id} entry={entry} />)
        ) : (
          <p className="text-sm text-muted-foreground">No scored examples are available for this weak point yet.</p>
        )}
      </div>
    </div>
  );
}

function ScoreEntryDetails({ entry }: { entry: InterviewScoreEntry }) {
  return (
    <div className="rounded-md border border-border bg-card p-4 text-sm">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone={scoreTone(entry.score)}>Score {entry.score}</Badge>
        <span className="text-xs text-muted-foreground">{formatDate(entry.created_at)}</span>
        {entry.weak_point_tags.map((tag) => (
          <Badge key={tag} tone="warn">
            {labelForWeakPoint(tag)}
          </Badge>
        ))}
      </div>
      <p className="font-medium leading-6">{entry.question}</p>
      {entry.answer ? (
        <div className="mt-3 rounded-md border border-border bg-muted/30 p-3">
          <h4 className="font-medium">Your answer</h4>
          <p className="mt-1 leading-6 text-muted-foreground">{entry.answer}</p>
        </div>
      ) : null}
      {entry.feedback ? (
        <div className="mt-3 rounded-md border border-border bg-muted/40 p-3">
          <FeedbackDetails feedback={scoreEntryFeedback(entry)} />
        </div>
      ) : null}
      <div className="mt-3">
        <Link href={`/interview/sessions/${entry.session_id}`}>
          <Button size="sm" variant="secondary">
            <ExternalLink className="h-4 w-4" />
            Open session
          </Button>
        </Link>
      </div>
    </div>
  );
}

function SessionHistoryPanel({
  sessions,
  jobsById
}: {
  sessions: InterviewSession[];
  jobsById: Map<string, { company: string; role_title: string }>;
}) {
  const [showAll, setShowAll] = React.useState(false);
  return (
    <Panel>
      <div className="mb-4 flex items-center gap-2">
        <ClipboardList className="h-4 w-4 text-primary" />
        <h2 className="text-base font-semibold">Session History</h2>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">Up to 50 sessions, most recently updated first. Open a session for its recorded answers, feedback and question comparisons.</p>
      <div className="grid gap-3">
        {sessions.length ? (
          (showAll ? sessions : sessions.slice(0, 5)).map((session) => (
            <Link
              key={session.id}
              href={`/interview/sessions/${session.id}`}
              className="block rounded-md border border-border bg-muted/40 p-3 transition hover:bg-muted"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0 font-medium">{session.title ?? sessionTarget(session, jobsById)}</div>
                <Badge>{session.mode.replace("_", " ")}</Badge>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {formatDate(session.updated_at)} - {session.messages.length} messages
              </div>
            </Link>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">No interview sessions yet.</p>
        )}
      </div>
      {sessions.length > 5 ? <Button className="mt-4" variant="secondary" onClick={() => setShowAll(value => !value)}>{showAll ? "Show recent five sessions" : `Show all ${sessions.length} sessions`}</Button> : null}
    </Panel>
  );
}
