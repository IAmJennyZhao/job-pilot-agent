"""Manual edits expose only editable fields; facts and derived fields stay server-owned."""
from pydantic import Field
from app.tailoring_schemas import StrictModel
from app.generation_schemas import ResumeBullet, ResumeSkill, ResumeDraft


class ResumeEdit(StrictModel):
    bullets: list[ResumeBullet] = Field(max_length=20)
    skills: list[ResumeSkill] = Field(max_length=40)
    project_order: list[str] = Field(max_length=20)


class EditedDraft(ResumeDraft):
    # Empty content can be saved for recovery, but cannot pass review.
    bullets: list[ResumeBullet] = Field(max_length=20)


class RevisionRequest(StrictModel):
    request_key: str = Field(min_length=16, max_length=128)
    expected_revision_id: str = Field(min_length=1, max_length=36)


class SaveResumeEdit(RevisionRequest):
    edit: ResumeEdit


class RestoreResumeRevision(RevisionRequest):
    revision_id: str = Field(min_length=1, max_length=36)


class ReviewResume(StrictModel):
    revision_id: str = Field(min_length=1, max_length=36)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    validation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
