import type {
  AIReadiness,
  AdvancedAnalysisResponse,
  AssetRecommendation,
  CoverLetterTemplate,
  CoverageGapResponse,
  DashboardSummary,
  InterviewFeedback,
  InterviewInsights,
  InterviewPracticeFeedback,
  InterviewPracticeSet,
  InterviewPracticeSetPayload,
  InterviewQuestionResponse,
  InterviewSession,
  Job,
  JobCategory,
  JobCreatePayload,
  JobDetail,
  JobExtractPreview,
  JobIntelligenceResponse,
  JobListItem,
  JobStatusEventPayload,
  JobStatus,
  ResumeProfile,
  ResumeOption,
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

async function requestForm<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData
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

  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<DashboardSummary>("/api/dashboard/summary"),
  jobs: (params?: {
    includeArchived?: boolean;
    search?: string;
    status?: JobStatus | "";
    category?: JobCategory | "";
    healthFilter?: "stale" | "missing_data" | "";
  }) => {
    const query = new URLSearchParams();
    if (params?.includeArchived) query.set("include_archived", "true");
    if (params?.search) query.set("search", params.search);
    if (params?.status) query.set("status_filter", params.status);
    if (params?.category) query.set("category", params.category);
    if (params?.healthFilter) query.set("health_filter", params.healthFilter);
    const suffix = query.toString() ? `?${query}` : "";
    return request<JobListItem[]>(`/api/jobs${suffix}`);
  },
  job: (id: string) => request<JobDetail>(`/api/jobs/${id}`),
  extractJobPreview: (payload: { source_url?: string | null; source_content?: string | null }) =>
    request<JobExtractPreview>("/api/jobs/extract-preview", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createJob: (payload: JobCreatePayload) =>
    request<JobDetail>("/api/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateJob: (
    id: string,
    payload: Partial<JobCreatePayload> & {
      status?: JobStatus;
      fit_score?: number | null;
      selected_resume_option_id?: string | null;
      selected_cover_letter_template_id?: string | null;
    }
  ) =>
    request<Job>(`/api/jobs/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  createStatusEvent: (jobId: string, payload: JobStatusEventPayload) =>
    request<JobDetail>(`/api/jobs/${jobId}/status-events`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateStatusEvent: (jobId: string, eventId: string, payload: Partial<JobStatusEventPayload>) =>
    request<JobDetail>(`/api/jobs/${jobId}/status-events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteStatusEvent: (jobId: string, eventId: string) =>
    request<JobDetail>(`/api/jobs/${jobId}/status-events/${eventId}`, { method: "DELETE" }),
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
  resumeOptions: () => request<ResumeOption[]>("/api/profile/resume-options"),
  createResumeOption: (payload: Partial<ResumeOption> & { title: string }) =>
    request<ResumeOption>("/api/profile/resume-options", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  importResumeOption: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestForm<ResumeOption>("/api/profile/resume-options/import", formData);
  },
  updateResumeOption: (id: string, payload: Partial<ResumeOption>) =>
    request<ResumeOption>(`/api/profile/resume-options/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  confirmResumeOption: (id: string, mergeIntoProfile: boolean) =>
    request<ResumeOption>(`/api/profile/resume-options/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ merge_into_profile: mergeIntoProfile })
    }),
  deleteResumeOption: (id: string) => request<void>(`/api/profile/resume-options/${id}`, { method: "DELETE" }),
  resumeOptionDownloadUrl: (id: string) => `${API_BASE_URL}/api/profile/resume-options/${id}/download`,
  coverLetterTemplates: () => request<CoverLetterTemplate[]>("/api/profile/cover-letter-templates"),
  createCoverLetterTemplate: (payload: Partial<CoverLetterTemplate> & { title: string }) =>
    request<CoverLetterTemplate>("/api/profile/cover-letter-templates", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateCoverLetterTemplate: (id: string, payload: Partial<CoverLetterTemplate>) =>
    request<CoverLetterTemplate>(`/api/profile/cover-letter-templates/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteCoverLetterTemplate: (id: string) =>
    request<void>(`/api/profile/cover-letter-templates/${id}`, { method: "DELETE" }),
  generateCoverageGaps: () => request<CoverageGapResponse>("/api/profile/coverage-gaps", { method: "POST" }),
  skillGaps: () => request<SkillGap[]>("/api/skill-gaps"),
  updateSkillGap: (id: string, payload: Partial<SkillGap>) =>
    request<SkillGap>(`/api/skill-gaps/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  interviewSessions: () => request<InterviewSession[]>("/api/interview/sessions"),
  interviewSession: (sessionId: string) => request<InterviewSession>(`/api/interview/sessions/${sessionId}`),
  resumeSession: (sessionId: string) => request<InterviewPracticeSet>(`/api/interview/sessions/${sessionId}/resume`),
  interviewInsights: () => request<InterviewInsights>("/api/interview/insights"),
  createPracticeSet: (payload: InterviewPracticeSetPayload) =>
    request<InterviewPracticeSet>("/api/interview/practice-sets", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  evaluatePracticeAnswer: (payload: { session_id: string; question_id: string; answer: string }) =>
    request<InterviewPracticeFeedback>("/api/interview/answers/evaluate", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  analyzeJob: (jobId: string) =>
    request<JobDetail["analysis"]>(`/api/ai/analyze-job/${jobId}`, { method: "POST" }),
  suggestResume: (jobId: string) =>
    request<ResumeSuggestion>(`/api/ai/suggest-resume/${jobId}`, { method: "POST" }),
  aiReadiness: (jobId: string) => request<AIReadiness>(`/api/ai/readiness/${jobId}`),
  runJobIntelligence: (jobId: string) =>
    request<JobIntelligenceResponse>(`/api/ai/run-job-intelligence/${jobId}`, { method: "POST" }),
  rankAssets: (jobId: string) =>
    request<AssetRecommendation>(`/api/ai/rank-assets/${jobId}`, { method: "POST" }),
  advancedAnalysis: (jobId: string) =>
    request<AdvancedAnalysisResponse>(`/api/ai/advanced-analysis/${jobId}`),
  runAdvancedAnalysis: (jobId: string, refreshCompany = false) =>
    request<AdvancedAnalysisResponse>(
      `/api/ai/run-advanced-analysis/${jobId}${refreshCompany ? "?refresh_company=true" : ""}`,
      { method: "POST" }
    ),
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
