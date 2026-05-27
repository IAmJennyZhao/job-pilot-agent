from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models import (
    InterviewMode,
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


class JobCreate(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    role_title: str = Field(min_length=1, max_length=255)
    job_url: HttpUrl | str | None = None
    job_description: str = Field(min_length=1)
    notes: str | None = None


class JobUpdate(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=255)
    role_title: str | None = Field(default=None, min_length=1, max_length=255)
    job_url: HttpUrl | str | None = None
    job_description: str | None = Field(default=None, min_length=1)
    status: JobStatus | None = None
    notes: str | None = None
    fit_score: int | None = Field(default=None, ge=0, le=100)


class JobRead(CareerPilotModel):
    id: str
    company: str
    role_title: str
    job_url: str | None
    job_description: str
    status: JobStatus
    notes: str | None
    fit_score: int | None
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
    analysis: JobAnalysisRead | None = None
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


class DashboardSummary(BaseModel):
    total_jobs: int
    archived_jobs: int
    by_status: dict[str, int]
    needs_resume_tailoring: int
    interviewing: int
    top_skill_gaps: list[SkillGapRead]
    recent_interviews: list[InterviewSessionRead]
    next_recommended_action: str
