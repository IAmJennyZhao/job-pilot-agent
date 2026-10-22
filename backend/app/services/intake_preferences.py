"""Deterministic, advisory preferences. No AI calls or writes."""
import hashlib
import json
from app import models
from app.intake_facts import verified_facts
from app.intake_schemas import IntakeReview
from app.tailoring_preferences import Preferences
from app.services import profile_service, tailoring_source_service, job_service
from app.services.tailoring_source_validation import SourceError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def active_preferences(db):
    profile = profile_service.get_active_profile(db)
    state = db.get(models.TailoringProfileState, profile.id) if profile else None
    source = db.get(models.TailoringSourceVersion, state.active_source_id) if state and state.active_source_id else None
    if not source or tailoring_source_service.source_status(db, source) != "active":
        return None
    try:
        tailoring_source_service.validate_stored(source)
    except SourceError:
        return None
    return source


def flags_for(review: IntakeReview, preferences: Preferences):
    facts = verified_facts(review.facts, review.job.source_content)
    job = review.job
    flags = []

    def value(key):
        return getattr(facts, key).value

    def flag(key, level, message, secondary=False):
        fact = getattr(facts, key, None)
        flags.append({"key": key, "level": level, "message": message, "secondary": secondary,
                      "evidence": fact.model_dump() if fact else None})

    pay = preferences.compensation
    if value("salary_component") != "base" or value("salary_band") != "applicable" or job.pay_period != "year" or (job.pay_currency or "").upper() != pay.currency.upper():
        flag("salary_component", "amber", f"Verify applicable annual {pay.currency} base pay against {pay.minimum:,}; total compensation and converted hourly pay are not base salary.")
    elif job.pay_max is not None and job.pay_max < pay.minimum:
        flag("salary_component", "red", f"Base pay is below your {pay.currency} {pay.minimum:,} target. Lower priority; you can still continue.")
    elif job.pay_min is not None and job.pay_min >= pay.minimum:
        flag("salary_component", "green", f"Base pay meets your {pay.currency} {pay.minimum:,} target.")
    else:
        flag("salary_component", "amber", "Salary range overlaps the target or has an unknown lower bound; verify the offer.")
    nyc = value("nyc_compatible")
    flag("nyc_compatible", "green" if nyc == "yes" else "red" if nyc == "no" else "amber",
         "Work arrangement permits living in NYC." if nyc == "yes" else "Work arrangement does not permit living in NYC; you can still continue." if nyc == "no" else "Confirm NYC residence eligibility and any remote/location restrictions.")
    required = value("required_years")
    maximum = preferences.experience.preferred_required_years_max
    flag("required_years", "amber" if required is None else "red" if required > maximum else "green",
         "Mandatory years are not stated; preferred years are separate." if required is None else f"Minimum mandatory experience: {required:g} years; preference is at most {maximum}. This does not assess your experience.")
    employer = value("employer_source")
    flag("employer_source", "green" if employer == "direct" else "red" if employer == "agency" else "amber",
         "Direct employer/application destination confirmed." if employer == "direct" else "Third-party agency placement conflicts with your direct-employer preference." if employer == "agency" else "Verify the hiring employer and direct application destination; a job board alone does not establish either.")
    for key, allowed, label in [("role_family", preferences.roles.target_families, "Role family"), ("employment_type", preferences.roles.employment_types, "Employment type")]:
        v = value(key)
        flag(key, "amber" if v is None else "green" if v in allowed else "red", f"{label}: {v or 'unknown'}." + (" Outside your preferences; continuation is available." if v and v not in allowed else ""))
    count, stage = value("employee_count"), value("company_stage")
    preferred = stage == "startup" or count is not None and count >= preferences.company.large_enterprise_min_employees
    flag("company_stage", "green" if preferred else "amber", "Company matches startup/large-enterprise preference." if preferred else "Company size/stage needs review against startup or large-enterprise preference.", True)
    if stage == "startup" and preferences.company.startup.prefer_higher_compensation_than_established_companies:
        flag("startup_premium", "amber", "You prefer higher startup compensation; no numeric premium has been assumed.", True)
    hours = value("hours_week")
    flag("hours_week", "amber" if hours is None else "red" if hours > preferences.work_life_balance.preferred_max_hours_per_week else "green" if hours <= preferences.work_life_balance.ideal_hours_per_week else "amber",
         "Team hours are unknown." if hours is None else f"Expected hours: {hours:g}/week; ideal {preferences.work_life_balance.ideal_hours_per_week}, preferred maximum {preferences.work_life_balance.preferred_max_hours_per_week}.", True)
    return flags


def evaluate(db, review: IntakeReview):
    source = active_preferences(db)
    preferences = Preferences.model_validate(source.preferences) if source else None
    result = {"available": bool(source), "source_id": source.id if source else None,
              "preference_hash": digest(source.preferences) if source else None,
              "preference_version": preferences.profile_version if preferences else None,
              "input_hash": digest(review.model_dump(mode="json")),
              "flags": flags_for(review, preferences) if preferences else [],
              "message": "Flags are advisory. Continue acknowledges the displayed checks." if source else "Preference checks unavailable. Activate reviewed sources in Application Assets; you can still save this job.",
              "full_description_ready": bool(review.full_description_reviewed and review.job.source_content.strip())}
    result["evaluation_hash"] = digest(result)
    result["duplicate_candidates"] = [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in job_service.find_duplicate_candidates(db, review.job.company, review.job.role_title, [str(link.url) for link in review.job.links])]
    return result
