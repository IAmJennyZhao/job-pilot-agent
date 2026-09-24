export const jobStatuses = [
  "Saved",
  "Applied",
  "Recruiter Screen",
  "Tech Screen",
  "Final Interview",
  "Offer",
  "Rejected",
  "Withdrawn",
  "Ghosted",
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

export type JobAction = {
  job_id: string;
  title: string;
  due_date: string;
  completed_at: string | null;
  company: string;
  role_title: string;
  status: JobStatus;
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
  selected_resume_option_id: string | null;
  selected_cover_letter_template_id: string | null;
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

export type AssetRanking = {
  asset_id: string;
  title: string;
  score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  reasons: string[];
};

export type AssetRecommendation = {
  id: string;
  job_id: string;
  source: "keyword" | "ai";
  resume_rankings: AssetRanking[];
  cover_letter_rankings: AssetRanking[];
  errors: string[];
  created_at: string;
};

export type JobDetail = Job & {
  source_content: string;
  status_events: JobStatusEvent[];
  analysis: JobAnalysis | null;
  latest_advanced_analysis: AdvancedJobAnalysis | null;
  latest_resume_suggestion: ResumeSuggestion | null;
  latest_asset_recommendation: AssetRecommendation | null;
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
  skill_groups: Array<{ category: string; skills: string[] }>;
  projects: Record<string, unknown>[];
  experience: Record<string, unknown>[];
  education: Record<string, unknown>[];
  certifications: string[];
  created_at: string;
  updated_at: string;
};

export type ResumeOptionStatus = "draft" | "ready";

export type ResumeOption = {
  id: string;
  resume_profile_id: string;
  title: string;
  candidate_name: string | null;
  status: ResumeOptionStatus;
  source_filename: string | null;
  content_type: string | null;
  file_size: number | null;
  parsed_text: string;
  summary: string | null;
  target_roles: string[];
  target_keywords: string[];
  skills: string[];
  skill_groups: Array<{ category: string; skills: string[] }>;
  projects: Record<string, unknown>[];
  experience: Record<string, unknown>[];
  education: Record<string, unknown>[];
  certifications: string[];
  created_at: string;
  updated_at: string;
};

export type CoverLetterTemplate = {
  id: string;
  resume_profile_id: string;
  title: string;
  target_roles: string[];
  target_keywords: string[];
  body: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CoverageGap = {
  asset_type: "resume" | "cover_letter";
  title: string;
  rationale: string;
  affected_job_ids: string[];
  target_keywords: string[];
};

export type CoverageGapResponse = {
  generated_at: string;
  jobs_considered: number;
  gaps: CoverageGap[];
};

export type SkillGapSource = "job_analysis" | "resume_match" | "interview_feedback";

export type SkillGap = {
  active_job_count: number;
  id: string;
  resume_profile_id: string;
  skill_name: string;
  sources: SkillGapSource[];
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
  question_id: string | null;
  role: "ai" | "user";
  content: string;
  question_type: string | null;
  score: number | null;
  feedback: Record<string, unknown> | null;
  created_at: string;
};

export type InterviewSession = {
  id: string;
  job_id: string | null;
  resume_profile_id: string | null;
  mode: "question_list" | "live_practice";
  title: string | null;
  target_category: JobCategory | null;
  target_role: string | null;
  stage: InterviewStage;
  question_type: string;
  created_at: string;
  updated_at: string;
  messages: InterviewMessage[];
};

export type DashboardSummary = {
  total_jobs: number;
  archived_jobs: number;
  ghosted_jobs: number;
  by_status: Record<string, number>;
  needs_resume_tailoring: number;
  interviewing: number;
  top_skill_gaps: DashboardSkillGap[];
  recent_interviews: InterviewSession[];
  next_recommended_action: string;
  sankey: DashboardSankey;
  health: DashboardHealth;
  search_health: DashboardSearchHealth;
  coverage_risk: DashboardCoverageRisk;
};

export type DashboardJobInsight = {
  id: string;
  company: string;
  role_title: string;
  status: JobStatus;
  last_movement_at: string;
  issue_label: string;
  recommended_action: string;
};

export type DashboardSankeyNode = {
  recorded_count: number;
  id: string;
  label: string;
  count: number;
  kind: "stage" | "terminal";
};

export type DashboardSankeyLink = {
  source: string;
  target: string;
  value: number;
};

export type DashboardSankey = {
  nodes: DashboardSankeyNode[];
  links: DashboardSankeyLink[];
};

export type DashboardHealth = {
  active_jobs: number;
  stale_jobs: number;
  missing_fit: number;
  missing_pay: number;
  low_confidence: number;
  missing_data: number;
  ghosted_jobs: number;
  archived_jobs: number;
};

export type DashboardSearchHealth = {
  stale_jobs: DashboardJobInsight[];
  missing_data: DashboardJobInsight[];
  needs_analysis: DashboardJobInsight[];
};

export type DashboardRiskSignal = {
  label: string;
  count: number;
  job_ids: string[];
};

export type DashboardCoverageRisk = {
  missing_pay: DashboardJobInsight[];
  missing_fit: DashboardJobInsight[];
  low_confidence: DashboardJobInsight[];
  recurring_risks: DashboardRiskSignal[];
};

export type DashboardSkillGap = {
  skill_name: string;
  count: number;
  source: "resume_match" | "analysis";
  affected_jobs: DashboardJobInsight[];
  suggested_action: string;
};

export type InterviewFeedback = {
  score: number;
  what_went_well: string[];
  what_was_missing: string[];
  suggested_better_answer: string;
  coaching_notes: string[];
  evidence_to_add: string[];
  weak_point_tags: WeakPointTag[];
  missing_skill_names: string[];
  follow_up_question: string;
  session_id: string | null;
  follow_up_question_id: string | null;
};

export type InterviewStage = "mixed" | "recruiter_screen" | "tech_screen" | "final_interview";

export type InterviewQuestionType =
  | "technical"
  | "behavioral"
  | "company"
  | "resume"
  | "role_specific"
  | "system_design"
  | "mixed";

export type WeakPointTag =
  | "technical_depth"
  | "answer_structure"
  | "specific_evidence"
  | "role_alignment"
  | "concision"
  | "communication_clarity"
  | "missing_skill"
  | "company_context"
  | "resume_positioning";

export type InterviewPracticeQuestion = {
  id: string;
  job_id: string | null;
  resume_profile_id: string | null;
  target_category: JobCategory | null;
  target_role: string | null;
  stage: InterviewStage;
  question_type: string;
  content: string;
  why_it_matters: string | null;
  strong_answer_should_include: string[];
  source: "advanced_analysis" | "generated" | "follow_up" | "manual";
  prompt_metadata: Record<string, unknown>;
  weak_point_tags: string[];
  asked_count: number;
  last_asked_at: string | null;
  created_at: string;
  updated_at: string;
};

export type InterviewPracticeSetPayload = {
  job_id?: string | null;
  target_category?: JobCategory | null;
  target_role?: string | null;
  stage: InterviewStage;
  question_type: InterviewQuestionType;
  count: number;
  resume_profile_id?: string | null;
};

export type InterviewPracticeSet = {
  session_id: string;
  questions: InterviewPracticeQuestion[];
  reused_count: number;
  generated_count: number;
  job_id: string | null;
  target_category: JobCategory | null;
  target_role: string | null;
  stage: InterviewStage;
  question_type: string;
};

export type InterviewPracticeFeedback = InterviewFeedback & {
  question_id: string;
  follow_up: InterviewPracticeQuestion | null;
};

export type InterviewScoreEntry = {
  message_id: string;
  session_id: string;
  question_id: string | null;
  question: string;
  answer: string | null;
  score: number;
  feedback: Record<string, unknown> | null;
  created_at: string;
  weak_point_tags: string[];
};

export type InterviewTrendPoint = {
  created_at: string;
  score: number;
};

export type InterviewInsights = {
  average_score: number | null;
  recent_scores: InterviewScoreEntry[];
  weak_points: Array<{ tag: string; count: number; latest_note: string | null; examples: InterviewScoreEntry[] }>;
  coaching_themes: string[];
  trends: {
    overall: InterviewTrendPoint[];
    knowledge: InterviewTrendPoint[];
    interview_skills: InterviewTrendPoint[];
  };
};

export type StudyPlanMode = "weekly_plan" | "project_ideas" | "both";

export type StudyPlanTimeframe = "1 week" | "2 weeks" | "1 month";

export type StudyPlan = {
  completed_tasks?: string[];
  top_gaps: string[];
  priority_order: string[];
  study_plan: Array<{ period: string; focus: string; tasks: string[] }>;
  project_ideas: string[];
};

export type SavedStudyPlan = {
  id: string;
  resume_profile_id: string;
  title: string;
  timeframe: string;
  time_budget_hours: number | null;
  time_budget_unit: "day" | "week";
  mode: StudyPlanMode;
  focus_skills: string[];
  plan: StudyPlan;
  created_at: string;
  updated_at: string;
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
  asset_recommendation: AssetRecommendation | null;
  errors: string[];
};
