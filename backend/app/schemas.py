from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, field_serializer, model_validator

from app.models import (
    InterviewMode,
    InterviewQuestionSource,
    InterviewStage,
    JobCategory,
    JobLinkKind,
    JobStatus,
    MessageRole,
    Priority,
    RecommendationSource,
    ResumeOptionStatus,
    SkillGapSource,
    UserLevel,
)


InterviewQuestionType = Literal[
    "technical",
    "behavioral",
    "company",
    "resume",
    "role_specific",
    "system_design",
    "mixed",
]
WeakPointTag = Literal[
    "technical_depth",
    "answer_structure",
    "specific_evidence",
    "role_alignment",
    "concision",
    "communication_clarity",
    "missing_skill",
    "company_context",
    "resume_positioning",
]


class CareerPilotModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", mode="wrap", when_used="json")
    def serialize_utc_dates(self, value, handler):
        # SQLite drops timezone metadata; stored application timestamps are UTC.
        if isinstance(value, datetime):
            value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return handler(value)


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
    selected_resume_option_id: str | None = None
    selected_cover_letter_template_id: str | None = None


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
    selected_resume_option_id: str | None
    selected_cover_letter_template_id: str | None
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
    responsibility_highlights: list[str] = Field(default_factory=list)
    must_have_skills: list[str]
    nice_to_have_skills: list[str]
    seniority_signal: str | None = None
    concerns: list[str] = Field(default_factory=list)


class CompanyResearchOutput(AIModel):
    sentiment: Literal["positive", "mixed", "negative", "neutral", "unknown"] = "unknown"
    summary: str
    themes: list[str] = Field(default_factory=list)
    highlight_phrases: list[str] = Field(default_factory=list)
    source_links: list[SourceLink] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100)
    coverage_note: str


class ResumeFitOutput(AIModel):
    top_company_fit: list[str]
    fit_highlights: list[str] = Field(default_factory=list)
    resume_keywords: list[str]
    risks_gaps: list[str]
    gap_highlights: list[str] = Field(default_factory=list)


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
    highlight_phrases: list[str] = Field(default_factory=list)
    source_links: list[dict[str, Any]]
    confidence: int | None
    coverage_note: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("highlight_phrases", mode="before")
    @classmethod
    def default_highlight_phrases(cls, value: Any) -> list[str]:
        return value or []


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
    highlight_phrases: dict[str, list[str]] = Field(default_factory=dict)
    expected_questions: list[dict[str, Any]]
    source_links: list[dict[str, Any]]
    errors: list[str]
    created_at: datetime
    updated_at: datetime

    @field_validator("highlight_phrases", mode="before")
    @classmethod
    def default_analysis_highlight_phrases(cls, value: Any) -> dict[str, list[str]]:
        return value or {}


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


class SkillGroup(AIModel):
    category: str
    skills: list[str] = Field(default_factory=list)


class ExperienceItem(AIModel):
    company: str | None = None
    role_title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)


class ProjectItem(AIModel):
    name: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    url: str | None = None


class EducationItem(AIModel):
    school: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    details: list[str] = Field(default_factory=list)


class ResumeParseOutput(AIModel):
    name: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    target_keywords: list[str] = Field(default_factory=list)
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    skill_groups: list[SkillGroup] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class JobDetail(JobRead):
    source_content: str
    status_events: list[JobStatusEventRead] = Field(default_factory=list)
    analysis: JobAnalysisRead | None = None
    latest_advanced_analysis: AdvancedJobAnalysisRead | None = None
    latest_resume_suggestion: ResumeSuggestionRead | None = None
    latest_asset_recommendation: AssetRecommendationRead | None = None


class ResumeProfileCreate(BaseModel):
    name: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    resume_text: str = ""
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    skill_groups: list[dict[str, Any]] = Field(default_factory=list)
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
    skill_groups: list[dict[str, Any]] | None = None
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
    skill_groups: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    experience: list[dict[str, Any]]
    education: list[dict[str, Any]]
    certifications: list[str]
    created_at: datetime
    updated_at: datetime


class ResumeOptionBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    candidate_name: str | None = None
    status: ResumeOptionStatus = ResumeOptionStatus.draft
    summary: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    target_keywords: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skill_groups: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ResumeOptionCreate(ResumeOptionBase):
    parsed_text: str = ""
    source_filename: str | None = None
    file_path: str | None = None
    content_type: str | None = None
    file_size: int | None = Field(default=None, ge=0)


class ResumeOptionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    candidate_name: str | None = None
    status: ResumeOptionStatus | None = None
    parsed_text: str | None = None
    summary: str | None = None
    target_roles: list[str] | None = None
    target_keywords: list[str] | None = None
    skills: list[str] | None = None
    skill_groups: list[dict[str, Any]] | None = None
    projects: list[dict[str, Any]] | None = None
    experience: list[dict[str, Any]] | None = None
    education: list[dict[str, Any]] | None = None
    certifications: list[str] | None = None


class ResumeOptionRead(CareerPilotModel):
    id: str
    resume_profile_id: str
    title: str
    candidate_name: str | None
    status: ResumeOptionStatus
    source_filename: str | None
    content_type: str | None
    file_size: int | None
    parsed_text: str
    summary: str | None
    target_roles: list[str]
    target_keywords: list[str]
    skills: list[str]
    skill_groups: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    experience: list[dict[str, Any]]
    education: list[dict[str, Any]]
    certifications: list[str]
    created_at: datetime
    updated_at: datetime


class ResumeOptionConfirmRequest(BaseModel):
    merge_into_profile: bool = False


class CoverLetterTemplateCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    target_roles: list[str] = Field(default_factory=list)
    target_keywords: list[str] = Field(default_factory=list)
    body: str = ""
    notes: str | None = None


class CoverLetterTemplateUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    target_roles: list[str] | None = None
    target_keywords: list[str] | None = None
    body: str | None = None
    notes: str | None = None


class CoverLetterTemplateRead(CareerPilotModel):
    id: str
    resume_profile_id: str
    title: str
    target_roles: list[str]
    target_keywords: list[str]
    body: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AssetRanking(AIModel):
    asset_id: str
    title: str
    score: int = Field(ge=0, le=100)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class AssetRecommendationRead(CareerPilotModel):
    id: str
    job_id: str
    source: RecommendationSource
    resume_rankings: list[dict[str, Any]]
    cover_letter_rankings: list[dict[str, Any]]
    errors: list[str]
    created_at: datetime


class AIAssetRankingOutput(AIModel):
    resume_rankings: list[AssetRanking] = Field(default_factory=list)
    cover_letter_rankings: list[AssetRanking] = Field(default_factory=list)


class CoverageGap(AIModel):
    asset_type: Literal["resume", "cover_letter"]
    title: str
    rationale: str
    affected_job_ids: list[str] = Field(default_factory=list)
    target_keywords: list[str] = Field(default_factory=list)


class CoverageGapResponse(BaseModel):
    generated_at: datetime
    jobs_considered: int
    gaps: list[CoverageGap] = Field(default_factory=list)


class SkillGapUpdate(BaseModel):
    user_level: UserLevel | None = None
    suggested_action: str | None = None


class SkillGapRead(CareerPilotModel):
    active_job_count: int = 0
    id: str
    resume_profile_id: str
    skill_name: str
    sources: list[SkillGapSource]
    count: int
    priority: Priority
    user_level: UserLevel
    suggested_action: str | None
    created_at: datetime
    updated_at: datetime


class InterviewMessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)
    question_id: str | None = None
    question_type: str | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    feedback: dict[str, Any] | None = None


class InterviewSessionCreate(BaseModel):
    job_id: str | None = None
    resume_profile_id: str | None = None
    mode: InterviewMode = InterviewMode.question_list
    title: str | None = None
    target_category: JobCategory | None = None
    target_role: str | None = Field(default=None, max_length=255)
    stage: InterviewStage = InterviewStage.mixed
    question_type: InterviewQuestionType = "mixed"

    @model_validator(mode="after")
    def has_target(self) -> "InterviewSessionCreate":
        if not self.job_id and not self.target_category and not (self.target_role and self.target_role.strip()):
            raise ValueError("Provide a job, category, or target role for the interview session.")
        return self


class InterviewMessageRead(CareerPilotModel):
    id: str
    session_id: str
    question_id: str | None
    role: MessageRole
    content: str
    question_type: str | None
    score: int | None
    feedback: dict[str, Any] | None
    created_at: datetime


class InterviewSessionRead(CareerPilotModel):
    id: str
    job_id: str | None
    resume_profile_id: str | None
    mode: InterviewMode
    title: str | None
    target_category: JobCategory | None
    target_role: str | None
    stage: InterviewStage
    question_type: str
    created_at: datetime
    updated_at: datetime
    messages: list[InterviewMessageRead] = Field(default_factory=list)


class InterviewQuestion(AIModel):
    question: str
    type: InterviewQuestionType
    why_it_matters: str
    strong_answer_should_include: list[str]


class InterviewQuestionsOutput(AIModel):
    questions: list[InterviewQuestion]


class InterviewAnswerFeedbackOutput(AIModel):
    score: int = Field(ge=0, le=100)
    what_went_well: list[str]
    what_was_missing: list[str]
    suggested_better_answer: str
    coaching_notes: list[str] = Field(default_factory=list)
    evidence_to_add: list[str] = Field(default_factory=list)
    weak_point_tags: list[WeakPointTag] = Field(default_factory=list)
    missing_skill_names: list[str] = Field(default_factory=list)
    follow_up_question: str


class InterviewAnswerFeedback(InterviewAnswerFeedbackOutput):
    session_id: str | None = None
    follow_up_question_id: str | None = None


class InterviewPracticeQuestionRead(CareerPilotModel):
    id: str
    job_id: str | None
    resume_profile_id: str | None
    target_category: JobCategory | None
    target_role: str | None
    stage: InterviewStage
    question_type: str
    content: str
    why_it_matters: str | None
    strong_answer_should_include: list[str]
    source: InterviewQuestionSource
    prompt_metadata: dict[str, Any]
    weak_point_tags: list[str]
    asked_count: int
    last_asked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InterviewPracticeSetCreate(BaseModel):
    job_id: str | None = None
    target_category: JobCategory | None = None
    target_role: str | None = Field(default=None, max_length=255)
    stage: InterviewStage = InterviewStage.mixed
    question_type: InterviewQuestionType = "mixed"
    count: int = Field(default=6, ge=1, le=20)
    resume_profile_id: str | None = None

    @model_validator(mode="after")
    def has_target(self) -> "InterviewPracticeSetCreate":
        if not self.job_id and not self.target_category and not (self.target_role and self.target_role.strip()):
            raise ValueError("Choose a saved job or provide a target category/role.")
        return self


class InterviewPracticeSetResponse(BaseModel):
    session_id: str
    questions: list[InterviewPracticeQuestionRead]
    reused_count: int
    generated_count: int
    job_id: str | None
    target_category: JobCategory | None
    target_role: str | None
    stage: InterviewStage
    question_type: str


class InterviewPracticeAnswerCreate(BaseModel):
    session_id: str
    question_id: str
    answer: str = Field(min_length=1)
    elapsed_seconds: int | None = Field(default=None, ge=0, le=604800)
    time_limit_seconds: int | None = Field(default=None, ge=30, le=3600)

    @field_validator("answer")
    @classmethod
    def nonblank_answer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter an answer")
        return value


class InterviewPracticeAnswerFeedback(InterviewAnswerFeedback):
    question_id: str
    follow_up_question: str
    follow_up_question_id: str | None
    follow_up: InterviewPracticeQuestionRead | None = None


class InterviewRecentScore(CareerPilotModel):
    message_id: str
    session_id: str
    question_id: str | None
    question: str
    answer: str | None = None
    score: int
    feedback: dict[str, Any] | None = None
    created_at: datetime
    weak_point_tags: list[str] = Field(default_factory=list)


class InterviewWeakPointInsight(BaseModel):
    tag: str
    count: int
    latest_note: str | None = None
    examples: list[InterviewRecentScore] = Field(default_factory=list)


class InterviewTrendPoint(BaseModel):
    created_at: datetime
    score: int


class InterviewTrendSeries(BaseModel):
    overall: list[InterviewTrendPoint] = Field(default_factory=list)
    knowledge: list[InterviewTrendPoint] = Field(default_factory=list)
    interview_skills: list[InterviewTrendPoint] = Field(default_factory=list)


class InterviewInsights(BaseModel):
    average_score: int | None
    recent_scores: list[InterviewRecentScore] = Field(default_factory=list)
    weak_points: list[InterviewWeakPointInsight] = Field(default_factory=list)
    coaching_themes: list[str] = Field(default_factory=list)
    trends: InterviewTrendSeries = Field(default_factory=InterviewTrendSeries)


class StudyPlanRequest(BaseModel):
    resume_profile_id: str | None = None
    timeframe: Literal["1 week", "2 weeks", "1 month"] = "2 weeks"
    target_roles: list[str] = Field(default_factory=list)
    focus_skills: list[str] = Field(default_factory=list)
    time_budget_hours: int | None = Field(default=None, ge=1)
    time_budget_unit: Literal["day", "week"] = "day"
    mode: Literal["weekly_plan", "project_ideas", "both"] = "both"


class StudyPlanItem(AIModel):
    period: str
    focus: str
    tasks: list[str]


class StudyPlanResponse(AIModel):
    top_gaps: list[str]
    priority_order: list[str]
    study_plan: list[StudyPlanItem]
    project_ideas: list[str]


class SavedStudyPlanCreate(BaseModel):
    resume_profile_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    timeframe: Literal["1 week", "2 weeks", "1 month"]
    time_budget_hours: int | None = Field(default=None, ge=1)
    time_budget_unit: Literal["day", "week"] = "day"
    mode: Literal["weekly_plan", "project_ideas", "both"] = "both"
    focus_skills: list[str] = Field(default_factory=list)
    plan: StudyPlanResponse


class SavedStudyPlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    completed_tasks: list[str] | None = None


class SavedStudyPlanContent(StudyPlanResponse):
    completed_tasks: list[str] = Field(default_factory=list)


class SavedStudyPlanRead(CareerPilotModel):
    id: str
    resume_profile_id: str
    title: str
    timeframe: str
    time_budget_hours: int | None
    time_budget_unit: str
    mode: str
    focus_skills: list[str]
    plan: SavedStudyPlanContent
    created_at: datetime
    updated_at: datetime


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
    asset_recommendation: AssetRecommendationRead | None = None
    errors: list[str] = Field(default_factory=list)


class DashboardJobInsight(BaseModel):
    id: str
    company: str
    role_title: str
    status: JobStatus
    last_movement_at: datetime
    issue_label: str
    recommended_action: str


class DashboardSankeyNode(BaseModel):
    recorded_count: int = 0
    id: str
    label: str
    count: int
    kind: Literal["stage", "terminal"]


class DashboardSankeyLink(BaseModel):
    source: str
    target: str
    value: int


class DashboardSankey(BaseModel):
    nodes: list[DashboardSankeyNode] = Field(default_factory=list)
    links: list[DashboardSankeyLink] = Field(default_factory=list)


class DashboardHealth(BaseModel):
    active_jobs: int
    stale_jobs: int
    missing_fit: int
    missing_pay: int
    low_confidence: int
    missing_data: int
    ghosted_jobs: int
    archived_jobs: int


class DashboardSearchHealth(BaseModel):
    stale_jobs: list[DashboardJobInsight] = Field(default_factory=list)
    missing_data: list[DashboardJobInsight] = Field(default_factory=list)
    needs_analysis: list[DashboardJobInsight] = Field(default_factory=list)


class DashboardRiskSignal(BaseModel):
    label: str
    count: int
    job_ids: list[str] = Field(default_factory=list)


class DashboardCoverageRisk(BaseModel):
    missing_pay: list[DashboardJobInsight] = Field(default_factory=list)
    missing_fit: list[DashboardJobInsight] = Field(default_factory=list)
    low_confidence: list[DashboardJobInsight] = Field(default_factory=list)
    recurring_risks: list[DashboardRiskSignal] = Field(default_factory=list)


class DashboardSkillGap(BaseModel):
    skill_name: str
    count: int
    source: Literal["resume_match", "analysis"]
    affected_jobs: list[DashboardJobInsight] = Field(default_factory=list)
    suggested_action: str


class DashboardSummary(BaseModel):
    total_jobs: int
    archived_jobs: int
    ghosted_jobs: int
    by_status: dict[str, int]
    needs_resume_tailoring: int
    interviewing: int
    top_skill_gaps: list[DashboardSkillGap]
    recent_interviews: list[InterviewSessionRead]
    next_recommended_action: str
    sankey: DashboardSankey
    health: DashboardHealth
    search_health: DashboardSearchHealth
    coverage_risk: DashboardCoverageRisk
