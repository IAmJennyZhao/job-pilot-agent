"""Versioned, strict contracts for the four resume passes."""
from typing import Literal
from pydantic import Field
from app.tailoring_schemas import StrictModel

class Requirement(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=1, max_length=1500)
    description: str = Field(min_length=1, max_length=500)

class ResumeBullet(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    record_id: str
    evidence_ids: list[str] = Field(min_length=1, max_length=6)
    requirement_ids: list[str] = Field(max_length=20)
    text: str = Field(min_length=1, max_length=1800)

class ResumeSkill(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    source_ids: list[str] = Field(min_length=1, max_length=10)

class ResumeDraft(StrictModel):
    schema_version: Literal[1] = 1
    requirements: list[Requirement] = Field(max_length=40)
    bullets: list[ResumeBullet] = Field(min_length=1, max_length=20)
    skills: list[ResumeSkill] = Field(max_length=40)
    unmet_requirement_ids: list[str] = Field(max_length=40)
    change_summary: list[str] = Field(max_length=12)

class CritiqueIssue(StrictModel):
    issue_id: str
    severity: Literal["blocking", "improvement"]
    field_path: str = Field(pattern=r"^(draft|skills|bullets\.[^.]+)$", description="Exact target: draft, skills, or bullets.<existing bullet ID>. Never append .text; use draft for gaps.")
    requirement_ids: list[str]
    evidence_ids: list[str]
    finding: str = Field(max_length=800)
    proposed_action: str = Field(max_length=800)
    requires_user_fact_confirmation: bool

class CritiqueReport(StrictModel):
    issues: list[CritiqueIssue] = Field(max_length=30)

class RevisionDecision(StrictModel):
    issue_id: str
    action: Literal["accepted", "rejected"]
    reason: str = Field(min_length=1, max_length=800)

class BulletLineage(StrictModel):
    bullet_id: str
    parent_bullet_ids: list[str] = Field(max_length=20, description="Replaced original bullet IDs for a split/merge; empty for wholly new evidence.")
    issue_ids: list[str] = Field(min_length=1, max_length=30, description="Accepted critique issues authorizing this new bullet.")

class RevisedResume(StrictModel):
    draft: ResumeDraft
    decisions: list[RevisionDecision] = Field(max_length=30)
    lineage: list[BulletLineage] = Field(default_factory=list, max_length=20, description="Exactly one entry for each new bullet ID; none for retained IDs. Changed evidence requires new IDs.")

class PolishEdit(StrictModel):
    bullet_id: str
    before: str
    after: str

class PolishedResume(StrictModel):
    draft: ResumeDraft
    edits: list[PolishEdit] = Field(max_length=20)

class GenerateResume(StrictModel):
    request_key: str = Field(min_length=16, max_length=128)
    expected_input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_description_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    acknowledged_evaluation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

class FactualAccuracyReport(StrictModel):
    validator_version: Literal["resume-v1", "resume-v2", "resume-v3", "resume-v4"] = "resume-v2"
    valid: bool
    blocking_issues: list[str]
    supported_claim_ids: list[str]
    wording_changes: list[PolishEdit] = Field(default_factory=list)
    unmet_requirement_ids: list[str]
    human_review_required: Literal[True] = True
    scope: str = "Checks compare content with user-approved sources; they do not independently verify employment or prove semantic accuracy."
