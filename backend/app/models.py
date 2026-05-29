import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


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
    custom = "custom"


class InterviewMode(str, enum.Enum):
    question_list = "question_list"
    live_practice = "live_practice"


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

    @property
    def source_url(self) -> str | None:
        for link in self.links:
            if link.kind == JobLinkKind.source:
                return link.url
        return self.links[0].url if self.links else None


class JobLink(Base):
    __tablename__ = "job_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
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


class ResumeProfile(TimestampMixin, Base):
    __tablename__ = "resume_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    projects: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    experience: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    education: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    resume_suggestions: Mapped[list["ResumeSuggestion"]] = relationship(
        back_populates="resume_profile",
        cascade="all, delete-orphan",
    )
    skill_gaps: Mapped[list["SkillGap"]] = relationship(
        back_populates="resume_profile",
        cascade="all, delete-orphan",
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="resume_profile",
    )


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


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
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

    job: Mapped[Job] = relationship(back_populates="interview_sessions")
    resume_profile: Mapped[ResumeProfile | None] = relationship(back_populates="interview_sessions")
    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewMessage.created_at",
    )


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
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


class SkillGap(TimestampMixin, Base):
    __tablename__ = "skill_gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    resume_profile_id: Mapped[str] = mapped_column(
        ForeignKey("resume_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[SkillGapSource] = mapped_column(
        Enum(
            SkillGapSource,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
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

