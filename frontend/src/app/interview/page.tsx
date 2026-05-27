"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, MessageSquareText, Play } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { InterviewFeedback, InterviewQuestionResponse } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function InterviewPage() {
  const queryClient = useQueryClient();
  const { data: jobs = [] } = useQuery({ queryKey: ["jobs"], queryFn: api.jobs });
  const { data: sessions = [] } = useQuery({ queryKey: ["interview-sessions"], queryFn: api.interviewSessions });
  const [jobId, setJobId] = React.useState("");
  const [questionType, setQuestionType] = React.useState("mixed");
  const [count, setCount] = React.useState(6);
  const [generated, setGenerated] = React.useState<InterviewQuestionResponse | null>(null);
  const [question, setQuestion] = React.useState("");
  const [answer, setAnswer] = React.useState("");
  const [feedback, setFeedback] = React.useState<InterviewFeedback | null>(null);

  React.useEffect(() => {
    if (!jobId && jobs[0]) setJobId(jobs[0].id);
  }, [jobId, jobs]);

  const questionMutation = useMutation({
    mutationFn: () => api.generateInterviewQuestions(jobId, { question_type: questionType, count }),
    onSuccess: (data) => {
      setGenerated(data);
      setQuestion(data.questions[0]?.question ?? "");
      queryClient.invalidateQueries({ queryKey: ["interview-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  const feedbackMutation = useMutation({
    mutationFn: () =>
      api.evaluateInterviewAnswer({
        job_id: jobId,
        question,
        answer,
        session_id: generated?.session_id ?? null
      }),
    onSuccess: (data) => {
      setFeedback(data);
      queryClient.invalidateQueries({ queryKey: ["interview-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["skill-gaps"] });
    }
  });

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Interview Practice"
        description="Generate job-specific questions, answer one, and store scored feedback for later review."
      />

      <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
        <Panel>
          <div className="mb-4 flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">Question Generator</h2>
          </div>
          <div className="grid gap-4">
            <Field label="Saved job">
              <Select value={jobId} onChange={(event) => setJobId(event.target.value)}>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.company} · {job.role_title}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Question type">
              <Select value={questionType} onChange={(event) => setQuestionType(event.target.value)}>
                <option value="mixed">Mixed</option>
                <option value="technical">Technical</option>
                <option value="behavioral">Behavioral</option>
                <option value="company">Company</option>
                <option value="resume">Resume</option>
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
            {questionMutation.error ? <p className="text-sm text-destructive">{(questionMutation.error as Error).message}</p> : null}
            <Button onClick={() => questionMutation.mutate()} disabled={!jobId || questionMutation.isPending}>
              <Play className="h-4 w-4" />
              {questionMutation.isPending ? "Generating..." : "Generate questions"}
            </Button>
          </div>
        </Panel>

        <Panel>
          <div className="mb-4 flex items-center gap-2">
            <MessageSquareText className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">Answer Practice</h2>
          </div>
          {generated ? (
            <div className="grid gap-4">
              <div className="grid gap-3">
                {generated.questions.map((item) => (
                  <button
                    key={item.question}
                    className="rounded-md border border-border bg-white p-3 text-left text-sm transition hover:bg-muted"
                    onClick={() => setQuestion(item.question)}
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <Badge>{item.type}</Badge>
                      <span className="text-xs text-muted-foreground">{item.why_it_matters}</span>
                    </div>
                    {item.question}
                  </button>
                ))}
              </div>
              <Field label="Selected question">
                <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
              </Field>
              <Field label="Your answer">
                <Textarea value={answer} onChange={(event) => setAnswer(event.target.value)} className="min-h-40" />
              </Field>
              {feedbackMutation.error ? <p className="text-sm text-destructive">{(feedbackMutation.error as Error).message}</p> : null}
              <Button onClick={() => feedbackMutation.mutate()} disabled={!jobId || !question || !answer || feedbackMutation.isPending}>
                {feedbackMutation.isPending ? "Evaluating..." : "Evaluate answer"}
              </Button>
              {feedback ? <FeedbackPanel feedback={feedback} /> : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Generate questions to open the answer workspace.</p>
          )}
        </Panel>
      </div>

      <Panel>
        <h2 className="text-base font-semibold">Session History</h2>
        <div className="mt-4 grid gap-3">
          {sessions.length ? (
            sessions.map((session) => (
              <div key={session.id} className="rounded-md border border-border bg-muted/40 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium">{session.title ?? "Interview session"}</div>
                  <Badge>{session.mode.replace("_", " ")}</Badge>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {formatDate(session.updated_at)} · {session.messages.length} messages
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No interview sessions yet.</p>
          )}
        </div>
      </Panel>
    </div>
  );
}

function FeedbackPanel({ feedback }: { feedback: InterviewFeedback }) {
  return (
    <div className="rounded-md border border-border bg-muted/40 p-4 text-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="font-semibold">Feedback</h3>
        <Badge tone={feedback.score >= 75 ? "good" : feedback.score >= 50 ? "warn" : "bad"}>Score {feedback.score}</Badge>
      </div>
      <List title="What went well" items={feedback.what_went_well} />
      <List title="What was missing" items={feedback.what_was_missing} />
      <div className="mt-3">
        <h4 className="font-medium">Stronger answer</h4>
        <p className="mt-1 leading-6 text-muted-foreground">{feedback.suggested_better_answer}</p>
      </div>
      <div className="mt-3">
        <h4 className="font-medium">Follow-up</h4>
        <p className="mt-1 text-muted-foreground">{feedback.follow_up_question}</p>
      </div>
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-3">
      <h4 className="font-medium">{title}</h4>
      <ul className="mt-1 list-inside list-disc text-muted-foreground">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

