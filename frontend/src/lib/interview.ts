import type { InterviewFeedback, InterviewMessage, JobCategory, WeakPointTag } from "@/lib/types";

export function sessionTarget(
  session: { job_id: string | null; target_category: JobCategory | null; target_role: string | null },
  jobsById: Map<string, { company: string; role_title: string }>
) {
  if (session.job_id) {
    const job = jobsById.get(session.job_id);
    if (job) return `${job.company} - ${job.role_title}`;
  }
  return session.target_role || session.target_category || "Interview session";
}

export type SessionEntry = {
  questionId: string;
  question: string;
  questionType: string | null;
  whyItMatters: string | null;
  weakPointTags: string[];
  askedAt: string;
  answer: string | null;
  answeredAt: string | null;
  feedback: InterviewFeedback | null;
};

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

export function groupSessionEntries(messages: InterviewMessage[]): SessionEntry[] {
  const order: string[] = [];
  const entries = new Map<string, SessionEntry>();

  const ensureEntry = (questionId: string) => {
    let entry = entries.get(questionId);
    if (!entry) {
      entry = {
        questionId,
        question: "",
        questionType: null,
        whyItMatters: null,
        weakPointTags: [],
        askedAt: "",
        answer: null,
        answeredAt: null,
        feedback: null
      };
      entries.set(questionId, entry);
      order.push(questionId);
    }
    return entry;
  };

  for (const message of messages) {
    if (!message.question_id) continue;
    const entry = ensureEntry(message.question_id);
    const feedback = message.feedback;

    if (message.role === "ai" && message.score == null) {
      entry.question = message.content;
      entry.questionType = message.question_type;
      entry.askedAt = message.created_at;
      entry.whyItMatters = typeof feedback?.why_it_matters === "string" ? feedback.why_it_matters : null;
      entry.weakPointTags = asStringArray(feedback?.weak_point_tags);
    } else if (message.role === "user") {
      entry.answer = message.content;
      entry.answeredAt = message.created_at;
    } else if (message.role === "ai" && message.score != null) {
      if (typeof feedback?.submitted_answer === "string") {
        entry.answer = feedback.submitted_answer;
        entry.answeredAt = message.created_at;
      }
      entry.feedback = {
        score: message.score,
        what_went_well: asStringArray(feedback?.what_went_well),
        what_was_missing: asStringArray(feedback?.what_was_missing),
        suggested_better_answer: typeof feedback?.suggested_better_answer === "string" ? feedback.suggested_better_answer : "",
        coaching_notes: asStringArray(feedback?.coaching_notes),
        evidence_to_add: asStringArray(feedback?.evidence_to_add),
        weak_point_tags: asStringArray(feedback?.weak_point_tags) as WeakPointTag[],
        missing_skill_names: asStringArray(feedback?.missing_skill_names),
        follow_up_question: typeof feedback?.follow_up_question === "string" ? feedback.follow_up_question : "",
        session_id: message.session_id,
        follow_up_question_id: typeof feedback?.follow_up_question_id === "string" ? feedback.follow_up_question_id : null
      };
    }
  }

  return order.map((id) => entries.get(id)!);
}
