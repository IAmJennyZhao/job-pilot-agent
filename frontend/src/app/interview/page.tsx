"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ClipboardList, MessageSquareText, Play, RotateCcw, Sparkles, Target } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { FeedbackDetails, weakPointLabels } from "@/components/interview/feedback-details";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { sessionTarget } from "@/lib/interview";
import {
  jobCategories,
  type InterviewInsights,
  type InterviewPracticeFeedback,
  type InterviewPracticeQuestion,
  type InterviewPracticeSet,
  type InterviewQuestionType,
  type InterviewSession,
  type InterviewStage,
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
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedJobId = searchParams.get("jobId") ?? "";
  const requestedTargetCategory = searchParams.get("targetCategory") as JobCategory | null;
  const requestedTargetRole = searchParams.get("targetRole");
  const requestedStage = searchParams.get("stage") as InterviewStage | null;
  const requestedQuestionType = searchParams.get("questionType") as InterviewQuestionType | null;
  const resumeSessionId = searchParams.get("resumeSessionId");

  const { data: jobs = [] } = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs() });
  const { data: sessions = [] } = useQuery({ queryKey: ["interview-sessions"], queryFn: api.interviewSessions });
  const { data: insights } = useQuery({ queryKey: ["interview-insights"], queryFn: api.interviewInsights });
  const { data: resumeData } = useQuery({
    queryKey: ["interview-resume", resumeSessionId],
    queryFn: () => api.resumeSession(resumeSessionId as string),
    enabled: Boolean(resumeSessionId)
  });

  const [targetMode, setTargetMode] = React.useState<"job" | "role">(requestedJobId ? "job" : "role");
  const [jobId, setJobId] = React.useState(requestedJobId);
  const [targetCategory, setTargetCategory] = React.useState<JobCategory>("AI/ML Engineer");
  const [targetRole, setTargetRole] = React.useState("");
  const [stage, setStage] = React.useState<InterviewStage>("mixed");
  const [questionType, setQuestionType] = React.useState<InterviewQuestionType>("mixed");
  const [count, setCount] = React.useState(6);
  const [practiceSet, setPracticeSet] = React.useState<InterviewPracticeSet | null>(null);
  const [queue, setQueue] = React.useState<InterviewPracticeQuestion[]>([]);
  const [activeQuestionId, setActiveQuestionId] = React.useState("");
  const [answer, setAnswer] = React.useState("");
  const [feedback, setFeedback] = React.useState<InterviewPracticeFeedback | null>(null);
  const [showInsightsHistory, setShowInsightsHistory] = React.useState(false);

  const jobsById = React.useMemo(() => new Map(jobs.map((job) => [job.id, job])), [jobs]);
  const activeQuestion = queue.find((question) => question.id === activeQuestionId) ?? queue[0] ?? null;
  const isActive = Boolean(practiceSet && activeQuestion);

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
    if (!resumeData) return;
    setPracticeSet(resumeData);
    setQueue(resumeData.questions);
    setActiveQuestionId(resumeData.questions[0]?.id ?? "");
    setAnswer("");
    setFeedback(null);
    router.replace("/interview");
  }, [resumeData, router]);

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
      setPracticeSet(data);
      setQueue(data.questions);
      setActiveQuestionId(data.questions[0]?.id ?? "");
      setAnswer("");
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

  const canStart = targetMode === "job" ? Boolean(jobId) : Boolean(targetCategory || targetRole.trim());

  const resetPracticeSet = () => {
    setPracticeSet(null);
    setQueue([]);
    setActiveQuestionId("");
    setAnswer("");
    setFeedback(null);
  };

  return (
    <div className="grid gap-6">
      <PageHeader title="Interview Practice" description="Focused answer reps for saved jobs and role targets." />

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
            <Button variant="secondary" onClick={resetPracticeSet}>
              <Target className="h-4 w-4" />
              New practice set
            </Button>
          </div>
          <div className="grid gap-4">
            <PracticeSetStats practiceSet={practiceSet} />
            <QuestionQueue questions={queue} activeQuestionId={activeQuestion.id} onSelect={setActiveQuestionId} />
            <div className="rounded-md border border-border bg-muted/30 p-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Badge>{activeQuestion.question_type.replace("_", " ")}</Badge>
                <Badge>{activeQuestion.source.replace("_", " ")}</Badge>
                {activeQuestion.why_it_matters ? <span className="text-xs text-muted-foreground">{activeQuestion.why_it_matters}</span> : null}
              </div>
              <p className="text-base font-medium leading-7">{activeQuestion.content}</p>
            </div>
            <Field label="Your answer">
              <Textarea value={answer} onChange={(event) => setAnswer(event.target.value)} className="min-h-44" />
            </Field>
            {evaluateAnswer.error ? <p className="text-sm text-destructive">{(evaluateAnswer.error as Error).message}</p> : null}
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => evaluateAnswer.mutate()} disabled={!answer.trim() || evaluateAnswer.isPending}>
                <Sparkles className="h-4 w-4" />
                {evaluateAnswer.isPending ? "Evaluating..." : "Evaluate answer"}
              </Button>
              <Button variant="secondary" onClick={() => setAnswer("")} disabled={!answer.trim()}>
                <RotateCcw className="h-4 w-4" />
                Clear
              </Button>
            </div>
            {feedback ? <FeedbackPanel feedback={feedback} /> : null}
          </div>
        </Panel>
      ) : (
        <div className="mx-auto w-full max-w-xl">
          <Panel>
            <div className="mb-4 flex items-center gap-2">
              <Target className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold">Practice Target</h2>
            </div>
            <div className="grid gap-4">
              <div className="grid grid-cols-2 gap-2 rounded-md border border-border bg-muted p-1">
                <button
                  className={cn("rounded px-3 py-2 text-sm font-medium", targetMode === "job" ? "bg-card-strong text-primary shadow-sm" : "text-muted-foreground")}
                  onClick={() => setTargetMode("job")}
                  type="button"
                >
                  Saved job
                </button>
                <button
                  className={cn("rounded px-3 py-2 text-sm font-medium", targetMode === "role" ? "bg-card-strong text-primary shadow-sm" : "text-muted-foreground")}
                  onClick={() => setTargetMode("role")}
                  type="button"
                >
                  General role
                </button>
              </div>

              {targetMode === "job" ? (
                <Field label="Saved job">
                  <Select value={jobId} onChange={(event) => setJobId(event.target.value)}>
                    {jobs.map((job) => (
                      <option key={job.id} value={job.id}>
                        {job.company} - {job.role_title}
                      </option>
                    ))}
                  </Select>
                </Field>
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
              <Button onClick={() => createPracticeSet.mutate()} disabled={!canStart || createPracticeSet.isPending}>
                <Play className="h-4 w-4" />
                {createPracticeSet.isPending ? "Starting..." : "Start practice"}
              </Button>
            </div>
          </Panel>
        </div>
      )}

      {isActive ? (
        <div>
          <button
            type="button"
            onClick={() => setShowInsightsHistory((value) => !value)}
            className="flex items-center gap-2 text-sm font-medium text-muted-foreground transition hover:text-foreground"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform", showInsightsHistory && "rotate-180")} />
            {showInsightsHistory ? "Hide insights & history" : "Show insights & history"}
          </button>
          {showInsightsHistory ? (
            <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_420px]">
              <InsightsPanel insights={insights} />
              <SessionHistoryPanel sessions={sessions} jobsById={jobsById} />
            </div>
          ) : null}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
          <InsightsPanel insights={insights} />
          <SessionHistoryPanel sessions={sessions} jobsById={jobsById} />
        </div>
      )}
    </div>
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

function InsightsPanel({ insights }: { insights?: InterviewInsights }) {
  return (
    <Panel>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <h2 className="text-base font-semibold">Interview Insights</h2>
        </div>
        <Badge>{insights?.average_score == null ? "No score" : `Avg ${insights.average_score}`}</Badge>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium">Weak points</h3>
          <div className="mt-2 grid gap-2">
            {insights?.weak_points.length ? (
              insights.weak_points.slice(0, 6).map((item) => (
                <div key={item.tag} className="rounded-md border border-border bg-muted/40 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{weakPointLabels[item.tag] ?? item.tag.replace("_", " ")}</span>
                    <Badge tone="warn">{item.count}</Badge>
                  </div>
                  {item.latest_note ? <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.latest_note}</p> : null}
                </div>
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
                <div key={`${item.session_id}-${item.created_at}`} className="rounded-md border border-border bg-muted/40 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="line-clamp-1 font-medium">{item.question}</span>
                    <Badge tone={item.score >= 75 ? "good" : item.score >= 50 ? "warn" : "bad"}>{item.score}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{formatDate(item.created_at)}</div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No evaluated answers yet.</p>
            )}
          </div>
        </div>
      </div>
    </Panel>
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
