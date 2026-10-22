import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobIntakeReview(Base):
    __tablename__ = "job_intake_reviews"
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(128), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    review: Mapped[dict] = mapped_column(JSON)
    evaluation: Mapped[dict] = mapped_column(JSON)
    preference_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tailoring_source_versions.id", ondelete="RESTRICT"), nullable=True)
    decision: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def new_uuid() -> str:
    return str(uuid.uuid4())


class TailoringRun(Base):
    __tablename__ = "tailoring_runs"
    __table_args__ = (UniqueConstraint("profile_id", "job_id", "request_key", name="uq_tailoring_request"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="RESTRICT"))
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("resume_profiles.id", ondelete="RESTRICT"))
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("tailoring_source_versions.id", ondelete="RESTRICT"))
    parent_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tailoring_runs.id", ondelete="RESTRICT"), nullable=True)
    request_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(32), default="pending")
    active_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TailoringStageAttempt(Base):
    __tablename__ = "tailoring_stage_attempts"
    __table_args__ = (UniqueConstraint("run_id", "stage", "attempt", name="uq_tailoring_attempt"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("tailoring_runs.id", ondelete="RESTRICT"))
    stage: Mapped[str] = mapped_column(String(16))
    attempt: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32), default="running")
    input_data: Mapped[dict] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    prompt_version: Mapped[str] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TailoredRevision(Base):
    __tablename__ = "tailored_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("tailoring_runs.id", ondelete="RESTRICT"), unique=True)
    content: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    plain_text: Mapped[str] = mapped_column(Text)
    validation: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class JobStatus(str, enum.Enum):
    saved = "Saved"
    applied = "Applied"
    recruiter_screen = "Recruiter Screen"
    tech_screen = "Tech Screen"
    final_interview = "Final Interview"
    offer = "Offer"
    rejected = "Rejected"
    withdrawn = "Withdrawn"
    ghosted = "Ghosted"
    archived = "Archived"


class JobCategory(str, enum.Enum):
    ai_ml_engineer = "AI/ML Engineer"
    backend_engineer = "Backend Engineer"
    frontend_engineer = "Frontend Engineer"
    full_stack_engineer = "Full Stack Engineer"
    data_engineer = "Data Engineer"
    devops_infrastructure = "DevOps/Infrastructure"
    product_platform_engineer = "Product/Platform Engineer"
    other = "Other"


class JobLinkKind(str, enum.Enum):
    source = "source"
    company_portal = "company_portal"
    application_portal = "application_portal"
    recruiter = "recruiter"
    company_info = "company_info"
    custom = "custom"


class InterviewMode(str, enum.Enum):
    question_list = "question_list"
    live_practice = "live_practice"


class InterviewStage(str, enum.Enum):
    mixed = "mixed"
    recruiter_screen = "recruiter_screen"
    tech_screen = "tech_screen"
    final_interview = "final_interview"


class InterviewQuestionSource(str, enum.Enum):
    advanced_analysis = "advanced_analysis"
    generated = "generated"
    follow_up = "follow_up"
    manual = "manual"


class MessageRole(str, enum.Enum):
    ai = "ai"
    user = "user"


class SkillGapSource(str, enum.Enum):
    job_analysis = "job_analysis"
    resume_match = "resume_match"
    interview_feedback = "interview_feedback"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class UserLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    unknown = "unknown"


class ResumeOptionStatus(str, enum.Enum):
    draft = "draft"
    ready = "ready"


class RecommendationSource(str, enum.Enum):
    keyword = "keyword"
    ai = "ai"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[JobCategory] = mapped_column(
        Enum(
            JobCategory,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=JobCategory.other,
        nullable=False,
        index=True,
    )
    location: Mapped[str | None] = mapped_column(String(255))
    remote_type: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    required_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    pay_min: Mapped[int | None] = mapped_column(Integer)
    pay_max: Mapped[int | None] = mapped_column(Integer)
    pay_currency: Mapped[str | None] = mapped_column(String(16))
    pay_period: Mapped[str | None] = mapped_column(String(64))
    pay_raw: Mapped[str | None] = mapped_column(Text)
    pay_annual_min: Mapped[int | None] = mapped_column(Integer)
    pay_annual_max: Mapped[int | None] = mapped_column(Integer)
    pay_conversion_note: Mapped[str | None] = mapped_column(Text)
    benefits: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=JobStatus.saved,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    fit_score: Mapped[int | None] = mapped_column(Integer)
    extraction_confidence: Mapped[int | None] = mapped_column(Integer)
    extraction_warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    selected_resume_option_id: Mapped[str | None] = mapped_column(
        ForeignKey("resume_options.id", ondelete="SET NULL"),
        index=True,
    )
    selected_cover_letter_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("cover_letter_templates.id", ondelete="SET NULL"),
        index=True,
    )

    analysis: Mapped["JobAnalysis | None"] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
    )
    resume_suggestions: Mapped[list["ResumeSuggestion"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    interview_questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    links: Mapped[list["JobLink"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobLink.created_at",
    )
    status_events: Mapped[list["JobStatusEvent"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobStatusEvent.changed_at",
    )
    advanced_analyses: Mapped[list["AdvancedJobAnalysis"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="AdvancedJobAnalysis.created_at",
    )
    asset_recommendation_snapshots: Mapped[list["AssetRecommendationSnapshot"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="AssetRecommendationSnapshot.created_at",
    )

    @property
    def source_url(self) -> str | None:
        for link in self.links:
            if link.kind == JobLinkKind.source:
                return link.url
        return self.links[0].url if self.links else None


class ApplicationAttribution(Base):
    __tablename__ = "application_attributions"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    resume_version: Mapped[str] = mapped_column(String(500), nullable=False)


class JobAction(TimestampMixin, Base):
    __tablename__ = "job_actions"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job: Mapped[Job] = relationship()


class JobLink(Base):
    __tablename__ = "job_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[JobLinkKind] = mapped_column(
        Enum(
            JobLinkKind,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=JobLinkKind.custom,
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job: Mapped[Job] = relationship(back_populates="links")


class JobStatusEvent(Base):
    __tablename__ = "job_status_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[JobStatus | None] = mapped_column(
        Enum(
            JobStatus,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    to_status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    job: Mapped[Job] = relationship(back_populates="status_events")


class JobAnalysis(TimestampMixin, Base):
    __tablename__ = "job_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    responsibilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    required_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    technologies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    resume_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    interview_topics: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    job: Mapped[Job] = relationship(back_populates="analysis")


class CompanyResearchSnapshot(TimestampMixin, Base):
    __tablename__ = "company_research_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_company_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    sentiment: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    themes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    highlight_phrases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_links: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[int | None] = mapped_column(Integer)
    coverage_note: Mapped[str | None] = mapped_column(Text)

    advanced_analyses: Mapped[list["AdvancedJobAnalysis"]] = relationship(back_populates="company_research")


class AdvancedJobAnalysis(TimestampMixin, Base):
    __tablename__ = "advanced_job_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    company_research_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_research_snapshots.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="complete", nullable=False)
    job_insights: Mapped[dict | None] = mapped_column(JSON)
    company_sentiment: Mapped[dict | None] = mapped_column(JSON)
    top_company_fit: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    resume_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risks_gaps: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    highlight_phrases: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    expected_questions: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    source_links: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    job: Mapped[Job] = relationship(back_populates="advanced_analyses")
    company_research: Mapped[CompanyResearchSnapshot | None] = relationship(back_populates="advanced_analyses")


class ResumeProfile(TimestampMixin, Base):
    __tablename__ = "resume_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    skill_groups: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    projects: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    experience: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    education: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    resume_options: Mapped[list["ResumeOption"]] = relationship(
        back_populates="resume_profile",
        cascade="all, delete-orphan",
        order_by="ResumeOption.updated_at.desc()",
    )
    cover_letter_templates: Mapped[list["CoverLetterTemplate"]] = relationship(
        back_populates="resume_profile",
        cascade="all, delete-orphan",
        order_by="CoverLetterTemplate.updated_at.desc()",
    )
    resume_suggestions: Mapped[list["ResumeSuggestion"]] = relationship(
        back_populates="resume_profile",
        cascade="all, delete-orphan",
    )
    skill_gaps: Mapped[list["SkillGap"]] = relationship(
        back_populates="resume_profile",
        cascade="all, delete-orphan",
    )
    saved_study_plans: Mapped[list["SavedStudyPlan"]] = relationship(
        back_populates="resume_profile",
        cascade="all, delete-orphan",
        order_by="SavedStudyPlan.created_at.desc()",
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="resume_profile",
    )


class ResumeOption(TimestampMixin, Base):
    __tablename__ = "resume_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    resume_profile_id: Mapped[str] = mapped_column(
        ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ResumeOptionStatus] = mapped_column(
        Enum(
            ResumeOptionStatus,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=ResumeOptionStatus.draft,
        nullable=False,
        index=True,
    )
    source_filename: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(1024))
    content_type: Mapped[str | None] = mapped_column(String(128))
    file_size: Mapped[int | None] = mapped_column(Integer)
    parsed_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    target_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    skill_groups: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    projects: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    experience: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    education: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    resume_profile: Mapped[ResumeProfile] = relationship(back_populates="resume_options")


class CoverLetterTemplate(TimestampMixin, Base):
    __tablename__ = "cover_letter_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    resume_profile_id: Mapped[str] = mapped_column(
        ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    target_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    resume_profile: Mapped[ResumeProfile] = relationship(back_populates="cover_letter_templates")


class ResumeSuggestion(Base):
    __tablename__ = "resume_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_profile_id: Mapped[str] = mapped_column(
        ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    matched_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    weak_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    keyword_suggestions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bullet_suggestions: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    fit_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job: Mapped[Job] = relationship(back_populates="resume_suggestions")
    resume_profile: Mapped[ResumeProfile] = relationship(back_populates="resume_suggestions")


class AssetRecommendationSnapshot(Base):
    __tablename__ = "asset_recommendation_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[RecommendationSource] = mapped_column(
        Enum(
            RecommendationSource,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=RecommendationSource.keyword,
        nullable=False,
        index=True,
    )
    resume_rankings: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    cover_letter_rankings: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job: Mapped[Job] = relationship(back_populates="asset_recommendation_snapshots")


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resume_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("resume_profiles.id", ondelete="SET NULL"),
        index=True,
    )
    mode: Mapped[InterviewMode] = mapped_column(
        Enum(
            InterviewMode,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=InterviewMode.question_list,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255))
    target_category: Mapped[JobCategory | None] = mapped_column(
        Enum(
            JobCategory,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
        index=True,
    )
    target_role: Mapped[str | None] = mapped_column(String(255))
    stage: Mapped[InterviewStage] = mapped_column(
        Enum(
            InterviewStage,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=InterviewStage.mixed,
        nullable=False,
        index=True,
    )
    question_type: Mapped[str] = mapped_column(String(100), default="mixed", nullable=False, index=True)

    job: Mapped[Job | None] = relationship(back_populates="interview_sessions")
    resume_profile: Mapped[ResumeProfile | None] = relationship(back_populates="interview_sessions")
    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewMessage.created_at",
    )


class InterviewQuestion(TimestampMixin, Base):
    __tablename__ = "interview_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    resume_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("resume_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_category: Mapped[JobCategory | None] = mapped_column(
        Enum(
            JobCategory,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
        index=True,
    )
    target_role: Mapped[str | None] = mapped_column(String(255))
    stage: Mapped[InterviewStage] = mapped_column(
        Enum(
            InterviewStage,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=InterviewStage.mixed,
        nullable=False,
        index=True,
    )
    question_type: Mapped[str] = mapped_column(String(100), default="mixed", nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str | None] = mapped_column(Text)
    strong_answer_should_include: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[InterviewQuestionSource] = mapped_column(
        Enum(
            InterviewQuestionSource,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        default=InterviewQuestionSource.generated,
        nullable=False,
        index=True,
    )
    prompt_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    weak_point_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    asked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    job: Mapped[Job | None] = relationship(back_populates="interview_questions")
    resume_profile: Mapped[ResumeProfile | None] = relationship()
    messages: Mapped[list["InterviewMessage"]] = relationship(back_populates="question")


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str | None] = mapped_column(String(100))
    score: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped[InterviewSession] = relationship(back_populates="messages")
    question: Mapped[InterviewQuestion | None] = relationship(back_populates="messages")


class SkillGap(TimestampMixin, Base):
    __tablename__ = "skill_gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    resume_profile_id: Mapped[str] = mapped_column(
        ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, values_callable=enum_values, native_enum=False, validate_strings=True),
        default=Priority.medium,
        nullable=False,
    )
    user_level: Mapped[UserLevel] = mapped_column(
        Enum(UserLevel, values_callable=enum_values, native_enum=False, validate_strings=True),
        default=UserLevel.unknown,
        nullable=False,
    )
    suggested_action: Mapped[str | None] = mapped_column(Text)

    resume_profile: Mapped[ResumeProfile] = relationship(back_populates="skill_gaps")


class SavedStudyPlan(TimestampMixin, Base):
    __tablename__ = "saved_study_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    resume_profile_id: Mapped[str] = mapped_column(
        ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False)
    time_budget_hours: Mapped[int | None] = mapped_column(Integer)
    time_budget_unit: Mapped[str] = mapped_column(String(16), default="day", nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="both", nullable=False)
    focus_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    plan: Mapped[dict] = mapped_column(JSON, nullable=False)

    resume_profile: Mapped[ResumeProfile] = relationship(back_populates="saved_study_plans")


class TailoringSourceVersion(Base):
    """Content is immutable; activation lifecycle is recorded separately."""
    __tablename__ = "tailoring_source_versions"
    __table_args__ = (UniqueConstraint("profile_id", "bundle_hash", name="uq_tailoring_source_bundle"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    profile_id: Mapped[str] = mapped_column(ForeignKey("resume_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    bank_version: Mapped[str] = mapped_column(String(128), nullable=False)
    bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    bank_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    preferences_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    template_tex: Mapped[str] = mapped_column(Text, nullable=False)
    style_guide: Mapped[str] = mapped_column(Text, nullable=False)
    bank: Mapped[dict] = mapped_column(JSON, nullable=False)
    preferences: Mapped[dict] = mapped_column(JSON, nullable=False)
    projection: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation: Mapped[dict] = mapped_column(JSON, nullable=False)
    hashes: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TailoringSourceEvent(Base):
    __tablename__ = "tailoring_source_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("tailoring_source_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("source_id", "sequence", name="uq_tailoring_source_event"),)


class TailoringProfileState(Base):
    __tablename__ = "tailoring_profile_states"
    profile_id: Mapped[str] = mapped_column(ForeignKey("resume_profiles.id", ondelete="RESTRICT"), primary_key=True)
    active_source_id: Mapped[str | None] = mapped_column(ForeignKey("tailoring_source_versions.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
