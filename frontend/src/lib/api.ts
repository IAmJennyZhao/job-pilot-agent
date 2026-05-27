import type {
  DashboardSummary,
  InterviewFeedback,
  InterviewQuestionResponse,
  InterviewSession,
  Job,
  JobDetail,
  JobStatus,
  ResumeProfile,
  ResumeSuggestion,
  SkillGap,
  StudyPlan
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : message;
    } catch {
      // The status code is still useful if the backend returned plain text.
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<DashboardSummary>("/api/dashboard/summary"),
  jobs: () => request<Job[]>("/api/jobs"),
  job: (id: string) => request<JobDetail>(`/api/jobs/${id}`),
  createJob: (payload: {
    company: string;
    role_title: string;
    job_url?: string | null;
    job_description: string;
    notes?: string | null;
  }) =>
    request<Job>("/api/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateJob: (id: string, payload: Partial<Job> & { status?: JobStatus }) =>
    request<Job>(`/api/jobs/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  archiveJob: (id: string) => request<Job>(`/api/jobs/${id}`, { method: "DELETE" }),
  profile: () => request<ResumeProfile | null>("/api/profile"),
  saveProfile: (payload: Partial<ResumeProfile>) =>
    request<ResumeProfile>("/api/profile", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateProfile: (id: string, payload: Partial<ResumeProfile>) =>
    request<ResumeProfile>(`/api/profile/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  skillGaps: () => request<SkillGap[]>("/api/skill-gaps"),
  updateSkillGap: (id: string, payload: Partial<SkillGap>) =>
    request<SkillGap>(`/api/skill-gaps/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  interviewSessions: () => request<InterviewSession[]>("/api/interview/sessions"),
  analyzeJob: (jobId: string) =>
    request<JobDetail["analysis"]>(`/api/ai/analyze-job/${jobId}`, { method: "POST" }),
  suggestResume: (jobId: string) =>
    request<ResumeSuggestion>(`/api/ai/suggest-resume/${jobId}`, { method: "POST" }),
  generateInterviewQuestions: (
    jobId: string,
    payload: { question_type: string; count: number; resume_profile_id?: string | null }
  ) =>
    request<InterviewQuestionResponse>(`/api/ai/generate-interview-questions/${jobId}`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  evaluateInterviewAnswer: (payload: {
    job_id: string;
    question: string;
    answer: string;
    session_id?: string | null;
  }) =>
    request<InterviewFeedback>("/api/ai/evaluate-interview-answer", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  generateStudyPlan: (payload: {
    resume_profile_id?: string | null;
    timeframe: "1 week" | "2 weeks" | "1 month";
    target_roles: string[];
  }) =>
    request<StudyPlan>("/api/ai/generate-study-plan", {
      method: "POST",
      body: JSON.stringify(payload)
    })
};

