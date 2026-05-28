export const jobStatuses = [
  "Saved",
  "Resume Tailored",
  "Applied",
  "Recruiter Screen",
  "Tech Screen",
  "Final Interview",
  "Offer",
  "Rejected",
  "Archived"
] as const;

export type JobStatus = (typeof jobStatuses)[number];

export type Job = {
  id: string;
  company: string;
  role_title: string;
  job_url: string | null;
  job_description: string;
  status: JobStatus;
  notes: string | null;
  fit_score: number | null;
  created_at: string;
  updated_at: string;
};

export type JobListItem = Job & {
  top_gaps: string[];
  top_gaps_source: "resume_match" | "analysis" | null;
};

export type JobAnalysis = {
  id: string;
  job_id: string;
  summary: string;
  responsibilities: string[];
  required_skills: string[];
  preferred_skills: string[];
  technologies: string[];
  resume_keywords: string[];
  interview_topics: string[];
  created_at: string;
  updated_at: string;
};

export type ResumeSuggestion = {
  id: string;
  job_id: string;
  resume_profile_id: string;
  matched_skills: string[];
  missing_skills: string[];
  weak_skills: string[];
  keyword_suggestions: string[];
  bullet_suggestions: Array<{ original: string; suggested: string; reason: string }>;
  fit_score: number;
  created_at: string;
};

export type JobDetail = Job & {
  analysis: JobAnalysis | null;
  latest_resume_suggestion: ResumeSuggestion | null;
};

export type ResumeProfile = {
  id: string;
  name: string | null;
  is_active: boolean;
  target_roles: string[];
  resume_text: string;
  summary: string | null;
  skills: string[];
  projects: Record<string, unknown>[];
  experience: Record<string, unknown>[];
  education: Record<string, unknown>[];
  certifications: string[];
  created_at: string;
  updated_at: string;
};

export type SkillGap = {
  id: string;
  resume_profile_id: string;
  skill_name: string;
  source: "job_analysis" | "resume_match" | "interview_feedback";
  count: number;
  priority: "low" | "medium" | "high";
  user_level: "low" | "medium" | "high" | "unknown";
  suggested_action: string | null;
  created_at: string;
  updated_at: string;
};

export type InterviewMessage = {
  id: string;
  session_id: string;
  role: "ai" | "user";
  content: string;
  question_type: string | null;
  score: number | null;
  feedback: Record<string, unknown> | null;
  created_at: string;
};

export type InterviewSession = {
  id: string;
  job_id: string;
  resume_profile_id: string | null;
  mode: "question_list" | "live_practice";
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: InterviewMessage[];
};

export type DashboardSummary = {
  total_jobs: number;
  archived_jobs: number;
  by_status: Record<string, number>;
  needs_resume_tailoring: number;
  interviewing: number;
  top_skill_gaps: SkillGap[];
  recent_interviews: InterviewSession[];
  next_recommended_action: string;
};

export type InterviewQuestion = {
  question: string;
  type: string;
  why_it_matters: string;
  strong_answer_should_include: string[];
};

export type InterviewQuestionResponse = {
  session_id: string | null;
  questions: InterviewQuestion[];
};

export type InterviewFeedback = {
  score: number;
  what_went_well: string[];
  what_was_missing: string[];
  suggested_better_answer: string;
  follow_up_question: string;
  session_id: string | null;
};

export type StudyPlan = {
  top_gaps: string[];
  priority_order: string[];
  study_plan: Array<{ day: string; focus: string; tasks: string[] }>;
  project_ideas: string[];
};

export type AIReadiness = {
  ready: boolean;
  has_openai_api_key: boolean;
  has_openai_model: boolean;
  model: string | null;
  job_id: string;
  profile_id: string | null;
  has_profile: boolean;
  has_resume_text: boolean;
  has_skills: boolean;
  missing_requirements: string[];
};

export type JobIntelligenceResponse = {
  status: "complete" | "partial";
  analysis: JobAnalysis | null;
  resume_suggestion: ResumeSuggestion | null;
  errors: string[];
};
