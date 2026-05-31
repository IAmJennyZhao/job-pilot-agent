export const jobStatuses = [
  "Saved",
  "Applied",
  "Recruiter Screen",
  "Tech Screen",
  "Final Interview",
  "Offer",
  "Rejected",
  "Withdrawn",
  "Archived"
] as const;

export const jobCategories = [
  "AI/ML Engineer",
  "Backend Engineer",
  "Frontend Engineer",
  "Full Stack Engineer",
  "Data Engineer",
  "DevOps/Infrastructure",
  "Product/Platform Engineer",
  "Other"
] as const;

export const remoteTypes = ["Remote", "Hybrid", "On-site", "Unknown"] as const;
export const jobLinkKinds = ["source", "company_portal", "application_portal", "recruiter", "company_info", "custom"] as const;

export type JobStatus = (typeof jobStatuses)[number];
export type JobCategory = (typeof jobCategories)[number];
export type RemoteType = (typeof remoteTypes)[number];
export type JobLinkKind = (typeof jobLinkKinds)[number];

export type JobLink = {
  id: string;
  job_id: string;
  kind: JobLinkKind;
  label: string;
  url: string;
  created_at: string;
};

export type JobLinkInput = {
  kind: JobLinkKind;
  label: string;
  url: string;
};

export type JobStatusEvent = {
  id: string;
  job_id: string;
  from_status: JobStatus | null;
  to_status: JobStatus;
  note: string | null;
  changed_at: string;
};

export type JobStatusEventPayload = {
  to_status: JobStatus;
  changed_at?: string | null;
  note?: string | null;
};

export type Job = {
  id: string;
  company: string;
  role_title: string;
  category: JobCategory;
  location: string | null;
  remote_type: RemoteType | string | null;
  summary: string | null;
  responsibilities: string[];
  required_skills: string[];
  pay_min: number | null;
  pay_max: number | null;
  pay_currency: string | null;
  pay_period: string | null;
  pay_raw: string | null;
  pay_annual_min: number | null;
  pay_annual_max: number | null;
  pay_conversion_note: string | null;
  benefits: string[];
  status: JobStatus;
  notes: string | null;
  fit_score: number | null;
  extraction_confidence: number | null;
  extraction_warnings: string[];
  links: JobLink[];
  source_url: string | null;
  created_at: string;
  updated_at: string;
};

export type JobCreatePayload = {
  company: string;
  role_title: string;
  category: JobCategory;
  location?: string | null;
  remote_type?: RemoteType | null;
  summary?: string | null;
  responsibilities: string[];
  required_skills: string[];
  pay_min?: number | null;
  pay_max?: number | null;
  pay_currency?: string | null;
  pay_period?: string | null;
  pay_raw?: string | null;
  benefits?: string[];
  source_content: string;
  links: JobLinkInput[];
  status?: JobStatus;
  status_note?: string | null;
  notes?: string | null;
  extraction_confidence?: number | null;
  extraction_warnings?: string[];
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

export type CompanyResearch = {
  id: string;
  company_name: string;
  normalized_company_name: string;
  sentiment: string;
  summary: string;
  themes: string[];
  highlight_phrases: string[];
  source_links: Array<{ title: string; url: string }>;
  confidence: number | null;
  coverage_note: string | null;
  created_at: string;
  updated_at: string;
};

export type AdvancedJobAnalysis = {
  id: string;
  job_id: string;
  company_research_id: string | null;
  status: "complete" | "partial";
  job_insights: {
    summary?: string;
    role_focus?: string[];
    responsibilities?: string[];
    must_have_skills?: string[];
    nice_to_have_skills?: string[];
    seniority_signal?: string | null;
    concerns?: string[];
  } | null;
  company_sentiment: {
    sentiment?: string;
    summary?: string;
    themes?: string[];
    highlight_phrases?: string[];
    source_links?: Array<{ title: string; url: string }>;
    confidence?: number | null;
    coverage_note?: string | null;
  } | null;
  top_company_fit: string[];
  resume_keywords: string[];
  risks_gaps: string[];
  highlight_phrases: {
    responsibilities?: string[];
    fit?: string[];
    gaps?: string[];
  };
  expected_questions: Array<{ question: string; type: string; why_it_matters: string }>;
  source_links: Array<{ title: string; url: string }>;
  errors: string[];
  created_at: string;
  updated_at: string;
};

export type AdvancedAnalysisResponse = {
  status: "complete" | "partial";
  analysis: AdvancedJobAnalysis | null;
  company_research: CompanyResearch | null;
  errors: string[];
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
  source_content: string;
  status_events: JobStatusEvent[];
  analysis: JobAnalysis | null;
  latest_advanced_analysis: AdvancedJobAnalysis | null;
  latest_resume_suggestion: ResumeSuggestion | null;
};

export type JobDuplicateCandidate = {
  id: string;
  company: string;
  role_title: string;
  status: JobStatus;
  matched_on: string[];
};

export type JobExtractPreview = {
  company: string;
  role_title: string;
  category: JobCategory;
  location: string | null;
  remote_type: RemoteType;
  summary: string;
  responsibilities: string[];
  required_skills: string[];
  pay_min: number | null;
  pay_max: number | null;
  pay_currency: string | null;
  pay_period: string;
  pay_raw: string | null;
  benefits: string[];
  links: JobLinkInput[];
  confidence: number;
  warnings: string[];
  source_url: string | null;
  source_content: string;
  duplicate_candidates: JobDuplicateCandidate[];
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
  has_tavily_api_key: boolean;
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
