"""Versioned source contracts. Archive data is never itself a model prompt."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Provenance(StrictModel):
    source_id: str
    source_lines: list[int] = Field(default_factory=list)
    source_locator: str | None = None


class Approval(StrictModel):
    status: Literal["draft", "validated", "approved", "approved_with_exclusions", "rejected", "revoked", "superseded"]
    approved_at: str | None = None
    date_precision: str | None = None
    approved_by: str | None = None
    recorded_by: str | None = None
    authorization_method: str | None = None
    authorization_text: str | None = None
    scope: str | None = None
    approved_claim_ids: list[str]
    excluded_claim_ids: list[str]
    app_activation_status: str | None = None
    note: str | None = None


class Source(StrictModel):
    id: str
    independently_verified: bool
    kind: str | None = None
    filename: str | None = None
    sha256: str | None = None
    file_id: str | None = None
    pages: int | list[int] | None = None
    received_at: str | None = None
    retrieved_at: str | None = None
    source_locator: str | None = None
    source_summary: str | None = None
    source_excerpt: str | None = None
    authority_note: str | None = None
    line_number_note: str | None = None


class Relocation(Provenance):
    display: str
    note: str | None = None


class Identity(Provenance):
    name: str
    location: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    github: str | None = None
    linkedin: str | None = None
    link_source: str | None = None
    relocation_preference: Relocation | None = None


class Education(Provenance):
    id: str
    institution: str
    degree: str
    graduation: str | None = None
    graduation_display: str | None = None
    gpa: str | None = None
    minors: list[str] = Field(default_factory=list)


class Record(Provenance):
    id: str
    kind: Literal["employment", "project"]
    employer: str | None = None
    title_display: str | None = None
    location: str | None = None
    name: str | None = None
    subtitle: str | None = None
    start: str | None = None
    end: str | None = None
    current_as_of: str | None = None
    dates_display: str | None = None
    project_dates: None = None
    public_url: str | None = None
    technologies: list[str] = Field(default_factory=list)
    status: str | None = None


class Claim(Provenance):
    id: str
    record_id: str
    text: str = Field(min_length=1)
    evidence_status: Literal["source_supported", "needs_user_confirmation"]
    generation_eligible: bool
    technologies: list[str] = Field(default_factory=list)
    technology_ids: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    corroborating_source_ids: list[str] = Field(default_factory=list)
    accomplishment_group_id: str | None = None
    confirmation_note: str | None = None
    review_basis: str | None = None
    review_state: str | None = None


class Group(StrictModel):
    id: str
    record_id: str
    name: str
    claim_ids: list[str]
    status: str
    role_emphasis: list[str]
    note: str


class Detail(StrictModel):
    text: str
    evidence_claim_ids: list[str] = Field(min_length=1)
    evidence_status: Literal["source_supported", "needs_user_confirmation"]
    generation_eligible: bool


class Choice(StrictModel):
    observed_choice: Detail
    confirmed_rationale: Detail | None = None
    alternatives_evaluated: Detail | None = None


class OpenDetail(StrictModel):
    question: str
    answer: None = None
    generation_eligible: Literal[False]


class ImplementationProfile(StrictModel):
    id: str
    record_id: str
    accomplishment_group_id: str | None = None
    interpretation: str
    data_flow: list[Detail]
    component_roles: list[Detail]
    reliability_and_evaluation: list[Detail]
    outcomes: list[Detail]
    implementation_choices: list[Choice]
    open_details: list[OpenDetail]


class Overlap(StrictModel):
    id: str
    claim_ids: list[str]
    rule: str


class SkillGroup(Provenance):
    id: str
    label: str
    values: list[str]
    proficiency: str | None = None


class Metric(StrictModel):
    id: str
    claim_id: str  # Schema 4 also uses this field for an education reference.
    display: str
    unit: str
    before: int | float | None = None
    after: int | float | None = None
    derived_percentages_allowed: bool = False
    allowed_derived_display: str | None = None
    derivation: str | None = None
    constraints: list[str] = Field(default_factory=list)


class Award(Provenance):
    id: str
    name: str
    dates_display: str | None = None
    team: str | bool = False
    constraints: list[str] = Field(default_factory=list)


class Planned(StrictModel):
    record_id: str
    accomplishment_group_id: str | None = None
    items: list[str]
    source_ids: list[str] = Field(default_factory=list)
    status: str
    generation_eligible: Literal[False]


class GenerationPolicy(StrictModel):
    requires_approved_bank_snapshot: Literal[True]
    blocked_evidence_statuses: list[str]
    blocked_claim_ids: list[str]
    unknowns_are_not_facts: Literal[True]
    source_supported_means: str
    privacy: str
    requires_explicit_claim_eligibility: Literal[True]
    implementation_detail_policy: str
    no_cross_group_technology_inference: Literal[True]
    source_date_not_completion_date: Literal[True]
    unknown_schema_action: Literal["reject"]
    approval_is_not_claim_confirmation: Literal[True]
    eligibility_rule: str
    prompt_input: str
    version_pin_required: Literal[True]
    digest_verification_required: Literal[True]
    profile_dependencies_must_all_be_eligible: Literal[True]


class Reconciliation(StrictModel):
    id: str
    decision: str
    unresolved: str | None = None


class Technology(StrictModel):
    id: str
    name: str
    aliases: list[str]
    claim_ids: list[str]
    eligible_claim_ids: list[str]
    listed_skill_group_ids: list[str]
    record_ids: list[str]
    relationship: str
    proficiency: str | None = None


class RecordMetadata(StrictModel):
    record_id: str
    source_id: str
    date_precision: str
    project_dates_verified: bool | None
    public_url: str | None
    public_url_status: str
    completion_date_inferred: Literal[False]
    freshness_note: str


class ApprovalWorkflow(StrictModel):
    states: list[str]
    current_event_id: str
    snapshot_write_policy: Literal["create_new_version_only"]
    hash_policy: str
    edit_policy: str
    revocation_policy: str
    claim_confirmation_policy: str
    freshness_policy: str
    resume_review_policy: str


class Bank(StrictModel):
    schema_version: Literal[4]
    bank_version: str
    previous_bank_version: str | None
    prepared_at: str
    approval: Approval
    sources: list[Source]
    identity: Identity
    education: list[Education]
    records: list[Record]
    accomplishment_groups: list[Group]
    claims: list[Claim]
    implementation_profiles: list[ImplementationProfile]
    claim_overlap_groups: list[Overlap]
    skill_groups: list[SkillGroup]
    protected_metrics: list[Metric]
    unknowns: dict[str, None]
    awards: list[Award]
    planned_or_unverified_capabilities: list[Planned]
    generation_policy: GenerationPolicy
    reconciliation_notes: list[Reconciliation]
    technology_catalog: list[Technology]
    record_metadata: list[RecordMetadata]
    approval_workflow: ApprovalWorkflow


class ValidationReport(StrictModel):
    status: Literal["pass"] = "pass"
    eligible_claim_ids: list[str]
    excluded_claim_ids: list[str]
    warnings: list[str]
    validator_version: str


class SourceImport(StrictModel):
    bank_markdown: str = Field(max_length=524288)
    preferences_yaml: str = Field(max_length=65536)
    template_tex: str = Field(min_length=1, max_length=65536)
    style_guide: str = Field(min_length=1, max_length=65536)


class ActivateSource(StrictModel):
    expected_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_active_id: str | None


class SourceSummary(StrictModel):
    id: str
    profile_id: str
    bank_version: str
    bundle_hash: str
    status: Literal["pending", "active", "superseded", "revoked"]
    eligible_count: int
    excluded_count: int
    created_at: str


class SourcePreview(SourceSummary):
    validation: ValidationReport
    claims: list[Claim]
    identity: Identity
    education: list[Education]
    records: list[Record]
    unknowns: dict[str, None]
    preferences: dict
    template_hash: str
    style_hash: str
    template_tex: str
    style_guide: str
    approval: Approval
    events: list[dict]


class SourceList(StrictModel):
    active_id: str | None
    versions: list[SourceSummary]


class Projection(StrictModel):
    schema_version: Literal[1] = 1
    bank_version: str
    claims: list[dict]
    records: list[dict]
    education: list[dict]
    skill_groups: list[dict]
    technology_catalog: list[dict]
    implementation_profiles: list[dict]
    protected_metrics: list[dict]
    claim_overlap_groups: list[dict]
