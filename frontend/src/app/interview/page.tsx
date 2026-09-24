"use client";

import { useConfirm } from "@/components/ui/confirm-provider";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Brain, ChevronDown, ClipboardList, ExternalLink, MessageSquareText, Play, RotateCcw, Sparkles, Target, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { FeedbackDetails, weakPointLabels } from "@/components/interview/feedback-details";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { useDraft } from "@/lib/use-draft";
import { api } from "@/lib/api";
import { sessionTarget } from "@/lib/interview";
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
      <PageHeader title="Interview Practice" description="Focused answer reps for saved jobs and role targets." />
      <Panel>Loading interview workspace...</Panel>
    </div>
  );
}

function InterviewPageContent() {
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedJobId = searchParams.get("jobId") ?? "";
  const requestedTargetCategory = searchParams.get("targetCategory") as JobCategory | null;
  const requestedTargetRole = searchParams.get("targetRole");
  const requestedStage = searchParams.get("stage") as InterviewStage | null;
  const requestedQuestionType = searchParams.get("questionType") as InterviewQuestionType | null;
  const resumeSessionId = searchParams.get("resumeSessionId");

  const jobsQuery = useQuery({ queryKey: ["jobs", "interview-all"], queryFn: () => api.jobs({ includeArchived: true }) });
  const jobs = jobsQuery.data ?? [];
  const sessionsQuery = useQuery({ queryKey: ["interview-sessions"], queryFn: api.interviewSessions });
  const sessions = sessionsQuery.data ?? [];
  const insightsQuery = useQuery({ queryKey: ["interview-insights"], queryFn: api.interviewInsights });
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
  const answer = practiceDraft.value.answers[answerKey] ?? "";
  const setAnswer = (value: string) => practiceDraft.setValue(current => ({ ...current, answers: { ...current.answers, [answerKey]: value } }));
  const [feedback, setFeedback] = React.useState<InterviewPracticeFeedback | null>(null);
  const [showInsightsHistory, setShowInsightsHistory] = React.useState(false);

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
    if (!resumeData || !practiceDraft.ready) return;
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
        answer
      });
    },
    onSuccess: (data) => {
      setFeedback(data);
      setAnswer("");
      if (data.follow_up) {
        const followUp = data.follow_up;
        setQueue((current) => {
          if (current.some((question) => question.id === followUp.id)) return current;
          return [...current, followUp];
        });
        setActiveQuestionId(followUp.id);
      }
      queryClient.invalidateQueries({ queryKey: ["interview-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["interview-insights"] });
      queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const canStart = targetMode === "job" ? Boolean(jobs.some(job => job.id === jobId) && !jobsQuery.isLoading && !jobsQuery.error) : Boolean(targetCategory || targetRole.trim());
  const resetPracticeSet = () => {
    setPracticeSet(null);
    setQueue([]);
    setActiveQuestionId("");
    setFeedback(null);
  };

  return (
    <div className="grid gap-6">
      <PageHeader title="Interview Practice" description="Focused answer reps for saved jobs and role targets." />
      {[jobsQuery, sessionsQuery, insightsQuery, ...(resumeSessionId ? [resumeQuery] : [])].map((query, index) => query.error ? <Panel key={index}><p role="alert">Could not load {["job choices", "session history", "interview insights", "the requested session"][index]}: {(query.error as Error).message}</p><Button variant="secondary" onClick={() => query.refetch()}>Retry</Button></Panel> : query.isLoading ? <Panel key={index}>Loading {["job choices", "session history", "interview insights", "the requested session"][index]}...</Panel> : null)}
      {resumeSessionId && resumeQuery.error ? <Link href="/interview" className="text-sm font-medium underline">Return to saved practice draft</Link> : null}
      {practiceDraft.dirty ? <p role="status" className="text-sm text-muted-foreground">{practiceDraft.storageError ? "Draft recovery is unavailable. Keep this page open until you submit your answer." : "Each question keeps its own draft. This practice set and your drafts recover after a refresh on this browser, including after closing the tab."}</p> : null}
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
            <QuestionQueue questions={queue} activeQuestionId={activeQuestion.id} onSelect={id => { if (!evaluateAnswer.isPending) { setActiveQuestionId(id); setFeedback(null); } }} />
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
          </div>
        </Panel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.92fr)_minmax(360px,1.08fr)]">
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
                <div className="grid gap-4">
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

              <Field label="Stage">
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
              {createPracticeSet.error ? <p className="text-sm text-destructive">{(createPracticeSet.error as Error).message}</p> : null}
              <Button onClick={() => createPracticeSet.mutate()} disabled={!practiceDraft.ready || !canStart || createPracticeSet.isPending || Boolean(resumeSessionId && resumeQuery.isLoading)}>
                <Play className="h-4 w-4" />
                {createPracticeSet.isPending ? "Starting..." : "Start practice"}
              </Button>
            </fieldset>
          </Panel>
          {!sessionsQuery.isLoading && !insightsQuery.isLoading && !sessionsQuery.error && !insightsQuery.error ? <CommandCenterPanel
            insights={insights}
            sessions={sessions}
            jobsById={jobsById}
          /> : null}
        </div>
      )}

      {isActive ? (
        <div>
          <button
            type="button"
            aria-expanded={showInsightsHistory} aria-controls="practice-insights" onClick={() => setShowInsightsHistory((value) => !value)}
            className="flex items-center gap-2 text-sm font-medium text-muted-foreground transition hover:text-foreground"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform", showInsightsHistory && "rotate-180")} />
            {showInsightsHistory ? "Hide insights & history" : "Show insights & history"}
          </button>
          {showInsightsHistory ? (
            <div id="practice-insights" className="mt-4 grid gap-4 xl:grid-cols-[1fr_420px]">
              {!insightsQuery.isLoading && !insightsQuery.error ? <InsightsPanel insights={insights} /> : null}
              {!sessionsQuery.isLoading && !sessionsQuery.error ? <SessionHistoryPanel sessions={sessions} jobsById={jobsById} /> : null}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
          {!insightsQuery.isLoading && !insightsQuery.error ? <InsightsPanel insights={insights} /> : null}
          {!sessionsQuery.isLoading && !sessionsQuery.error ? <SessionHistoryPanel sessions={sessions} jobsById={jobsById} /> : null}
        </div>
      )}
    </div>
  );
}

function scoreTone(score: number): "good" | "warn" | "bad" {
  return score >= 75 ? "good" : score >= 50 ? "warn" : "bad";
}

function labelForWeakPoint(tag: string) {
  return weakPointLabels[tag] ?? tag.replace("_", " ");
}

function hasUnansweredPrompts(session: InterviewSession) {
  const asked = new Set(
    session.messages
      .filter((message) => message.role === "ai" && message.score == null && message.question_id)
      .map((message) => message.question_id as string)
  );
  const answered = new Set(
    session.messages
      .filter((message) => message.role === "user" && message.question_id)
      .map((message) => message.question_id as string)
  );
  return [...asked].some((questionId) => !answered.has(questionId));
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
        <h2 className="text-base font-semibold">Command Center</h2>
      </div>

      <div className="grid gap-4">
        <div className="grid gap-3 md:grid-cols-3">
          <TrendMetric title="Overall" points={insights?.trends?.overall ?? []} />
          <TrendMetric title="Knowledge" points={insights?.trends?.knowledge ?? []} />
          <TrendMetric title="Interview skills" points={insights?.trends?.interview_skills ?? []} />
        </div>

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
                  <Button size="sm" variant="secondary">Resume session</Button>
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
    <div className="rounded-md border border-border bg-muted/25 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">{title}</span>
        <span className="text-sm font-semibold">{latest ?? "--"}</span>
      </div>
      <TrendSparkline points={points} />
      <div className="mt-1 text-[11px] text-muted-foreground">
        {delta == null ? `${points.length} scored` : `${delta >= 0 ? "+" : ""}${delta} since first`}
      </div>
    </div>
  );
}

function TrendSparkline({ points }: { points: InterviewTrendPoint[] }) {
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
    <svg viewBox={`0 0 ${width} ${height}`} className="mt-2 h-11 w-full" role="img" aria-label="Score trend">
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
      <Badge>{practiceSet.stage.replace("_", " ")}</Badge>
      <Badge>{practiceSet.question_type.replace("_", " ")}</Badge>
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
        <h2 className="text-base font-semibold">Interview Insights</h2>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium">Weak points</h3>
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
          <h3 className="text-sm font-medium">Recent scores</h3>
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
  return (
    <Panel>
      <div className="mb-4 flex items-center gap-2">
        <ClipboardList className="h-4 w-4 text-primary" />
        <h2 className="text-base font-semibold">Session History</h2>
      </div>
      <div className="grid gap-3">
        {sessions.length ? (
          sessions.map((session) => (
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
    </Panel>
  );
}
