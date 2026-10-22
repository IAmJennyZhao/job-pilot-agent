"""Typed schema-2 preference snapshot; no candidate-specific defaults."""
from app.tailoring_schemas import StrictModel
from pydantic import Field


class PreferencesRolesTitleAliases(StrictModel):
    software_engineer: list[str]
    ai_engineer: list[str]
    applied_ai_developer: list[str]
    full_stack_engineer: list[str]
    backend_engineer: list[str]


class PreferencesRoles(StrictModel):
    target_families: list[str]
    title_aliases: PreferencesRolesTitleAliases
    assess_responsibilities_not_just_job_title: bool
    non_target_behavior: str
    employment_types: list[str]


class PreferencesLocationRemote(StrictModel):
    us_remote_allowed: bool
    any_remote_region_allowed_if_nyc_residence_permitted: bool
    nyc_eligibility_required: bool
    unclear_eligibility_behavior: str
    policy_confirmation: str


class PreferencesLocation(StrictModel):
    primary: str
    accepted_city_boroughs: list[str]
    onsite_allowed: bool
    hybrid_allowed: bool
    remote: PreferencesLocationRemote
    outside_nyc_nonremote: str
    nyc_metro_or_ny_state_ambiguous: str
    multi_location: str
    never_infer_work_location_from_headquarters: bool


class PreferencesCompensation(StrictModel):
    currency: str
    component: str
    minimum: int
    below_minimum: str
    overlapping_range: str
    unknown_or_unpublished: str
    total_comp_only: str
    count_bonus_equity_toward_base: bool
    geographic_band: str
    show_salary_in_resume: bool


class PreferencesExperience(StrictModel):
    preferred_required_years_max: int
    years_above_preference: str
    prefer_early_career: bool
    compare_minimum_mandatory_years_not_preferred_years: bool
    never_sum_overlapping_requirements: bool
    missing_years: str


class PreferencesCompanyStartup(StrictModel):
    classification: str
    employee_count_cap: float | None
    prefer_higher_compensation_than_established_companies: bool
    required_startup_compensation_premium_usd: float | None
    premium_unknown: str


class PreferencesCompany(StrictModel):
    size_policy: str
    preferred_categories: list[str]
    large_enterprise_min_employees: int
    startup: PreferencesCompanyStartup
    middle_sized_company: str
    size_or_stage_unknown: str
    no_startup_stage_assumptions_from_small_headcount: bool


class PreferencesEmployerSource(StrictModel):
    direct_company_applications_only: bool
    allow: list[str]
    exclude: list[str]
    missing_employer_or_direct_destination: str
    job_board_listing_can_be_discovered_but_apply_must_be_direct: bool
    auto_apply: bool


class PreferencesWorkLifeBalance(StrictModel):
    ideal_hours_per_week: int
    preferred_max_hours_per_week: int
    confirmed_more_than_50_hours: str
    unknown_hours: str
    company_wide_reputation_is_not_team_specific_evidence: bool


class PreferencesRanking(StrictModel):
    first: str
    then: list[str]
    preserve_uncertain_matches_for_review: bool
    do_not_invent_numeric_hiring_probability: bool
    do_not_silently_hide_saved_jobs: bool
    exclude_only_confirmed_third_party_recruiter_placements: bool
    allow_explicit_tailoring_override: bool


class PreferencesTailoringResume(StrictModel):
    passes: list[str]
    choose_emphasis_from_job_description: bool
    section_order: list[str]
    target_pages: int
    minimum_body_font_pt: int
    layout_reference: str
    style_guide: str
    preserve_approved_employers_titles_dates_and_metrics: bool
    formats: list[str]


class PreferencesTailoringCoverLetter(StrictModel):
    enabled_as_separate_explicit_action: bool
    default_variants: int
    formats: list[str]


class PreferencesTailoring(StrictModel):
    generate_only_on_user_click: bool
    source_of_candidate_facts: str
    always_use_full_job_description: bool
    no_new_candidate_facts_from_job_description: bool
    resume: PreferencesTailoringResume
    review_before_final_export: bool
    unresolved_claims_never_automatically_approved: bool
    never_update_application_status_as_side_effect: bool
    cover_letter: PreferencesTailoringCoverLetter


class PreferencesOutOfScope(StrictModel):
    automated_applications: bool
    auto_form_filling: bool
    recruiter_outreach: bool
    scheduled_tailoring: bool


class PreferencesIntake(StrictModel):
    preferred_inputs: list[str]
    pasted_description_takes_priority: bool
    basic_extraction_then_preference_flags: bool
    detailed_analysis: str
    decision_actions: list[str]
    not_pursuing: str
    continue_action: str = Field(alias="continue")
    red_flags_are_advisory: bool
    continue_acknowledges_current_flags: bool
    auto_mark_applied: bool


class Preferences(StrictModel):
    schema_version: int
    profile_version: str
    mode: str
    roles: PreferencesRoles
    location: PreferencesLocation
    compensation: PreferencesCompensation
    experience: PreferencesExperience
    company: PreferencesCompany
    employer_source: PreferencesEmployerSource
    work_life_balance: PreferencesWorkLifeBalance
    ranking: PreferencesRanking
    tailoring: PreferencesTailoring
    out_of_scope: PreferencesOutOfScope
    review_notes: list[str]
    intake: PreferencesIntake
