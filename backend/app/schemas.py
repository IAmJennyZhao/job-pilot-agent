from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models import (
    InterviewMode,
    JobCategory,
    JobLinkKind,
    JobStatus,
    MessageRole,
    Priority,
    SkillGapSource,
    UserLevel,
)


class CareerPilotModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobLinkBase(BaseModel):
    kind: JobLinkKind = JobLinkKind.custom
    label: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)


class JobLinkCreate(JobLinkBase):
    pass


class JobLinkRead(CareerPilotModel):
    id: str
    job_id: str
    kind: JobLinkKind
    label: str
    url: str
    created_at: datetime


class JobStatusEventRead(CareerPilotModel):
    id: str
    job_id: str
    from_status: JobStatus | None
    to_status: JobStatus
    note: str | None
    changed_at: datetime


class JobStatusEventCreate(BaseModel):
    to_status: JobStatus
    changed_at: datetime | None = None
    note: str | None = None


class JobStatusEventUpdate(BaseModel):
    to_status: JobStatus | None = None
    changed_at: datetime | None = None
    note: str | None = None


class JobDuplicateCandidate(BaseModel):
    id: str
    company: str
    role_title: str
    status: JobStatus
    matched_on: list[str] = Field(default_factory=list)


class JobExtractPreviewRequest(BaseModel):
    source_url: HttpUrl | str | None = None
    source_content: str | None = None

    @model_validator(mode="after")
    def has_source_material(self) -> "JobExtractPreviewRequest":
        if not self.source_url and not (self.source_content and self.source_content.strip()):
            raise ValueError("Provide a job URL, pasted job content, or both.")
        return self


class JobExtractionOutput(AIModel):
    company: str
    role_title: str
    category: JobCategory = JobCategory.other
    location: str | None = None
    remote_type: Literal["Remote", "Hybrid", "On-site", "Unknown"] = "Unknown"
    summary: str
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    pay_min: int | None = Field(default=None, ge=0)
    pay_max: int | None = Field(default=None, ge=0)
    pay_currency: str | None = Field(default=None, max_length=16)
    pay_period: Literal["hour", "day", "week", "month", "year", "contract", "unknown"] = "unknown"
    pay_raw: str | None = None
    benefits: list[str] = Field(default_factory=list)
    links: list[JobLinkBase] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)


class JobExtractPreview(JobExtractionOutput):
    source_url: str | None = None
    source_content: str
    duplicate_candidates: list[JobDuplicateCandidate] = Field(default_factory=list)


class JobCreate(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    role_title: str = Field(min_length=1, max_length=255)
    category: JobCategory = JobCategory.other
    location: str | None = Field(default=None, max_length=255)
    remote_type: Literal["Remote", "Hybrid", "On-site", "Unknown"] | None = "Unknown"
    summary: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    pay_min: int | None = Field(default=None, ge=0)
    pay_max: int | None = Field(default=None, ge=0)
    pay_currency: str | None = Field(default=None, max_length=16)
    pay_period: Literal["hour", "day", "week", "month", "year", "contract", "unknown"] | None = "unknown"
    pay_raw: str | None = None
    benefits: list[str] = Field(default_factory=list)
    source_content: str = ""
    links: list[JobLinkCreate] = Field(default_factory=list)
    status: JobStatus = JobStatus.saved
    status_note: str | None = None
    notes: str | None = None
    extraction_confidence: int | None = Field(default=None, ge=0, le=100)
    extraction_warnings: list[str] = Field(default_factory=list)


class JobUpdate(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=255)
    role_title: str | None = Field(default=None, min_length=1, max_length=255)
    category: JobCategory | None = None
    location: str | None = Field(default=None, max_length=255)
    remote_type: Literal["Remote", "Hybrid", "On-site", "Unknown"] | None = None
    summary: str | None = None
    responsibilities: list[str] | None = None
    required_skills: list[str] | None = None
    pay_min: int | None = Field(default=None, ge=0)
    pay_max: int | None = Field(default=None, ge=0)
    pay_currency: str | None = Field(default=None, max_length=16)
    pay_period: Literal["hour", "day", "week", "month", "year", "contract", "unknown"] | None = None
    pay_raw: str | None = None
    benefits: list[str] | None = None
    source_content: str | None = None
    links: list[JobLinkCreate] | None = None
    status: JobStatus | None = None
    status_note: str | None = None
    notes: str | None = None
    fit_score: int | None = Field(default=None, ge=0, le=100)
    extraction_confidence: int | None = Field(default=None, ge=0, le=100)
    extraction_warnings: list[str] | None = None


class JobRead(CareerPilotModel):
    id: str
    company: str
    role_title: str
    category: JobCategory
    location: str | None
    remote_type: str | None
    summary: str | None
    responsibilities: list[str]
    required_skills: list[str]
    pay_min: int | None
    pay_max: int | None
    pay_currency: str | None
    pay_period: str | None
    pay_raw: str | None
    pay_annual_min: int | None
    pay_annual_max: int | None
    pay_conversion_note: str | None
    benefits: list[str]
    status: JobStatus
    notes: str | None
    fit_score: int | None
    extraction_confidence: int | None
    extraction_warnings: list[str]
    links: list[JobLinkRead] = Field(default_factory=list)
    source_url: str | None = None
    created_at: datetime
    updated_at: datetime


class JobListItem(JobRead):
    top_gaps: list[str] = Field(default_factory=list)
    top_gaps_source: Literal["resume_match", "analysis"] | None = None


class JobAnalysisRead(CareerPilotModel):
    id: str
    job_id: str
    summary: str
    responsibilities: list[str]
    required_skills: list[str]
    preferred_skills: list[str]
    technologies: list[str]
    resume_keywords: list[str]
    interview_topics: list[str]
    created_at: datetime
    updated_at: datetime


class SourceLink(AIModel):
    title: str
    url: str


class JobInsightsOutput(AIModel):
    summary: str
    role_focus: list[str]
    responsibilities: list[str]
    must_have_skills: list[str]
    nice_to_have_skills: list[str]
    seniority_signal: str | None = None
    concerns: list[str] = Field(default_factory=list)


class CompanyResearchOutput(AIModel):
    sentiment: Literal["positive", "mixed", "negative", "neutral", "unknown"] = "unknown"
    summary: str
    themes: list[str] = Field(default_factory=list)
    source_links: list[SourceLink] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100)
    coverage_note: str


class ResumeFitOutput(AIModel):
    top_company_fit: list[str]
    resume_keywords: list[str]
    risks_gaps: list[str]


class AdvancedInterviewQuestion(AIModel):
    question: str
    type: Literal["technical", "behavioral", "company", "resume", "role_specific", "system_design", "mixed"]
    why_it_matters: str


class AdvancedInterviewPrepOutput(AIModel):
    expected_questions: list[AdvancedInterviewQuestion]


class CompanyResearchRead(CareerPilotModel):
    id: str
    company_name: str
    normalized_company_name: str
    sentiment: str
    summary: str
    themes: list[str]
    source_links: list[dict[str, Any]]
    confidence: int | None
    coverage_note: str | None
    created_at: datetime
    updated_at: datetime


class AdvancedJobAnalysisRead(CareerPilotModel):
    id: str
    job_id: str
    company_research_id: str | None
    status: Literal["complete", "partial"]
    job_insights: dict[str, Any] | None
    company_sentiment: dict[str, Any] | None
    top_company_fit: list[str]
    resume_keywords: list[str]
    risks_gaps: list[str]
    expected_questions: list[dict[str, Any]]
    source_links: list[dict[str, Any]]
    errors: list[str]
    created_at: datetime
    updated_at: datetime


class AdvancedAnalysisResponse(BaseModel):
    status: Literal["complete", "partial"]
    analysis: AdvancedJobAnalysisRead | None = None
    company_research: CompanyResearchRead | None = None
    errors: list[str] = Field(default_factory=list)


class BulletSuggestion(AIModel):
    original: str
    suggested: str
    reason: str


class ResumeSuggestionRead(CareerPilotModel):
    id: str
    job_id: str
    resume_profile_id: str
    matched_skills: list[str]
    missing_skills: list[str]
    weak_skills: list[str]
    keyword_suggestions: list[str]
    bullet_suggestions: list[dict[str, Any]]
    fit_score: int
    created_at: datetime


class JobDetail(JobRead):
    source_content: str
    status_events: list[JobStatusEventRead] = Field(default_factory=list)
    analysis: JobAnalysisRead | None = None
    latest_advanced_analysis: AdvancedJobAnalysisRead | None = None
    latest_resume_suggestion: ResumeSuggestionRead | None = None


class ResumeProfileCreate(BaseModel):
    name: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    resume_text: str = ""
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ResumeProfileUpdate(BaseModel):
    name: str | None = None
    target_roles: list[str] | None = None
    resume_text: str | None = None
    summary: str | None = None
    skills: list[str] | None = None
    projects: list[dict[str, Any]] | None = None
    experience: list[dict[str, Any]] | None = None
    education: list[dict[str, Any]] | None = None
    certifications: list[str] | None = None


class ResumeProfileRead(CareerPilotModel):
    id: str
    name: str | None
    is_active: bool
    target_roles: list[str]
    resume_text: str
    summary: str | None
    skills: list[str]
    projects: list[dict[str, Any]]
    experience: list[dict[str, Any]]
    education: list[dict[str, Any]]
    certifications: list[str]
    created_at: datetime
    updated_at: datetime


class SkillGapUpdate(BaseModel):
    count: int | None = Field(default=None, ge=0)
    priority: Priority | None = None
    user_level: UserLevel | None = None
    suggested_action: str | None = None


class SkillGapRead(CareerPilotModel):
    id: str
    resume_profile_id: str
    skill_name: str
    source: SkillGapSource
    count: int
    priority: Priority
    user_level: UserLevel
    suggested_action: str | None
    created_at: datetime
    updated_at: datetime


class InterviewMessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)
    question_type: str | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    feedback: dict[str, Any] | None = None


class InterviewSessionCreate(BaseModel):
    job_id: str
    resume_profile_id: str | None = None
    mode: InterviewMode = InterviewMode.question_list
    title: str | None = None


class InterviewMessageRead(CareerPilotModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    question_type: str | None
    score: int | None
    feedback: dict[str, Any] | None
    created_at: datetime


class InterviewSessionRead(CareerPilotModel):
    id: str
    job_id: str
    resume_profile_id: str | None
    mode: InterviewMode
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[InterviewMessageRead] = Field(default_factory=list)


class InterviewQuestion(AIModel):
    question: str
    type: Literal["technical", "behavioral", "company", "resume", "role_specific", "system_design", "mixed"]
    why_it_matters: str
    strong_answer_should_include: list[str]


class InterviewQuestionsOutput(AIModel):
    questions: list[InterviewQuestion]


class InterviewQuestionResponse(InterviewQuestionsOutput):
    session_id: str | None = None


class GenerateInterviewQuestionsRequest(BaseModel):
    resume_profile_id: str | None = None
    question_type: Literal["technical", "behavioral", "company", "resume", "mixed"] = "mixed"
    count: int = Field(default=10, ge=1, le=20)


class EvaluateInterviewAnswerRequest(BaseModel):
    job_id: str
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    session_id: str | None = None


class InterviewAnswerFeedbackOutput(AIModel):
    score: int = Field(ge=0, le=100)
    what_went_well: list[str]
    what_was_missing: list[str]
    suggested_better_answer: str
    follow_up_question: str


class InterviewAnswerFeedback(InterviewAnswerFeedbackOutput):
    session_id: str | None = None


class StudyPlanRequest(BaseModel):
    resume_profile_id: str | None = None
    timeframe: Literal["1 week", "2 weeks", "1 month"] = "2 weeks"
    target_roles: list[str] = Field(default_factory=list)


class StudyPlanItem(AIModel):
    day: str
    focus: str
    tasks: list[str]


class StudyPlanResponse(AIModel):
    top_gaps: list[str]
    priority_order: list[str]
    study_plan: list[StudyPlanItem]
    project_ideas: list[str]


class JobAnalysisOutput(AIModel):
    summary: str
    responsibilities: list[str]
    required_skills: list[str]
    preferred_skills: list[str]
    technologies: list[str]
    resume_keywords: list[str]
    interview_topics: list[str]


class ResumeSuggestionOutput(AIModel):
    matched_skills: list[str]
    missing_skills: list[str]
    weak_skills: list[str]
    keyword_suggestions: list[str]
    bullet_suggestions: list[BulletSuggestion]
    fit_score: int = Field(ge=0, le=100)


class AIReadiness(BaseModel):
    ready: bool
    has_openai_api_key: bool
    has_openai_model: bool
    has_tavily_api_key: bool
    model: str | None
    job_id: str
    profile_id: str | None
    has_profile: bool
    has_resume_text: bool
    has_skills: bool
    missing_requirements: list[str] = Field(default_factory=list)


class JobIntelligenceResponse(BaseModel):
    status: Literal["complete", "partial"]
    analysis: JobAnalysisRead | None = None
    resume_suggestion: ResumeSuggestionRead | None = None
    errors: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    total_jobs: int
    archived_jobs: int
    by_status: dict[str, int]
    needs_resume_tailoring: int
    interviewing: int
    top_skill_gaps: list[SkillGapRead]
    recent_interviews: list[InterviewSessionRead]
    next_recommended_action: str
