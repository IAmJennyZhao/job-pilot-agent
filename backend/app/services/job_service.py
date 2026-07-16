from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas

MAX_TOP_GAPS = 3
LOW_CONFIDENCE_THRESHOLD = 80
FUNNEL_STATUSES = (
    models.JobStatus.saved,
    models.JobStatus.applied,
    models.JobStatus.recruiter_screen,
    models.JobStatus.tech_screen,
    models.JobStatus.final_interview,
    models.JobStatus.offer,
)
STAGE_RANK = {status: index for index, status in enumerate(FUNNEL_STATUSES)}
OPEN_OPPORTUNITY_STATUSES = set(FUNNEL_STATUSES)
HIDDEN_STATUSES = (
    models.JobStatus.archived,
    models.JobStatus.ghosted,
    models.JobStatus.rejected,
)
STALE_DAYS = {
    models.JobStatus.saved: 7,
    models.JobStatus.applied: 14,
    models.JobStatus.recruiter_screen: 7,
    models.JobStatus.tech_screen: 7,
    models.JobStatus.final_interview: 7,
}

PAY_MULTIPLIERS = {
    "hour": 40 * 52,
    "day": 260,
    "week": 52,
    "month": 12,
    "year": 1,
}


def _unique_nonempty(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        key = item.casefold()
        if item and key not in seen:
            output.append(item)
            seen.add(key)
    return output


def _normalize_link_url(url: str) -> str:
    return url.strip()


def _replace_links(db: Session, job: models.Job, links: list[schemas.JobLinkCreate]) -> None:
    job.links.clear()
    db.flush()
    seen: set[tuple[str, str]] = set()
    for link in links:
        url = _normalize_link_url(str(link.url))
        key = (link.kind.value, url.casefold())
        if not url or key in seen:
            continue
        seen.add(key)
        job.links.append(
            models.JobLink(
                kind=link.kind,
                label=link.label.strip(),
                url=url,
            )
        )


def annualize_pay(
    pay_min: int | None,
    pay_max: int | None,
    pay_period: str | None,
) -> tuple[int | None, int | None, str | None]:
    period = (pay_period or "unknown").strip().casefold()
    multiplier = PAY_MULTIPLIERS.get(period)
    if multiplier is None or (pay_min is None and pay_max is None):
        return None, None, None
    note = "Annual equivalent"
    if period != "year":
        note = {
            "hour": "Annual equivalent using 40 hours/week and 52 weeks/year.",
            "day": "Annual equivalent using 260 work days/year.",
            "week": "Annual equivalent using 52 weeks/year.",
            "month": "Annual equivalent using 12 months/year.",
        }.get(period, note)
    return (
        pay_min * multiplier if pay_min is not None else None,
        pay_max * multiplier if pay_max is not None else None,
        note,
    )


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def latest_movement_at(job: models.Job) -> datetime:
    if job.status_events:
        return max(as_utc(event.changed_at) for event in job.status_events)
    return as_utc(job.updated_at or job.created_at)


def days_since(value: datetime) -> int:
    return max(0, (as_utc(datetime.now(timezone.utc)) - as_utc(value)).days)


def is_open_opportunity(job: models.Job) -> bool:
    return job.status in OPEN_OPPORTUNITY_STATUSES


def has_pay(job: models.Job) -> bool:
    return any(
        value is not None
        for value in [job.pay_min, job.pay_max, job.pay_annual_min, job.pay_annual_max]
    ) or bool((job.pay_raw or "").strip())


def is_stale(job: models.Job) -> bool:
    stale_threshold = STALE_DAYS.get(job.status)
    if stale_threshold is None:
        return False
    return days_since(latest_movement_at(job)) >= stale_threshold


def is_missing_core_data(job: models.Job) -> bool:
    return is_open_opportunity(job) and (
        not has_pay(job)
        or job.fit_score is None
        or job.analysis is None
        or job.extraction_confidence is None
        or job.extraction_confidence < LOW_CONFIDENCE_THRESHOLD
    )


def needs_analysis(job: models.Job) -> bool:
    return is_open_opportunity(job) and (job.fit_score is None or job.analysis is None)


def current_stage_rank(job: models.Job) -> int:
    return STAGE_RANK.get(job.status, -1)


def furthest_stage_rank(job: models.Job) -> int:
    rank = STAGE_RANK.get(job.status, 0)
    for event in job.status_events:
        event_rank = STAGE_RANK.get(event.to_status)
        if event_rank is not None:
            rank = max(rank, event_rank)
    return rank


def health_filtered_jobs(
    jobs: list[models.Job],
    health_filter: str | None,
) -> list[models.Job]:
    if not health_filter:
        return jobs
    normalized = health_filter.strip().replace("-", "_").casefold()
    if normalized == "stale":
        return [job for job in jobs if is_stale(job)]
    if normalized == "missing_data":
        return [job for job in jobs if is_missing_core_data(job)]
    raise ValueError("Unsupported health filter")


def _apply_pay_annualization(job: models.Job) -> None:
    annual_min, annual_max, note = annualize_pay(job.pay_min, job.pay_max, job.pay_period)
    job.pay_annual_min = annual_min
    job.pay_annual_max = annual_max
    job.pay_conversion_note = note


def _status_event(
    job: models.Job,
    from_status: models.JobStatus | None,
    to_status: models.JobStatus,
    note: str | None = None,
) -> models.JobStatusEvent:
    return models.JobStatusEvent(
        job=job,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )


def _ordered_status_events(db: Session, job: models.Job) -> list[models.JobStatusEvent]:
    return list(
        db.scalars(
            select(models.JobStatusEvent)
            .where(models.JobStatusEvent.job_id == job.id)
            .order_by(models.JobStatusEvent.changed_at, models.JobStatusEvent.id)
        ).all()
    )


def _reconcile_status_history(db: Session, job: models.Job) -> None:
    events = _ordered_status_events(db, job)
    if not events:
        replacement = _status_event(job, None, models.JobStatus.saved)
        db.add(replacement)
        db.flush()
        events = [replacement]

    previous_status: models.JobStatus | None = None
    for event in events:
        event.from_status = previous_status
        previous_status = event.to_status
        db.add(event)
    job.status = events[-1].to_status


def save_job(db: Session, payload: schemas.JobCreate) -> models.Job:
    job = models.Job(
        company=payload.company,
        role_title=payload.role_title,
        category=payload.category,
        location=payload.location,
        remote_type=payload.remote_type,
        summary=payload.summary,
        responsibilities=payload.responsibilities,
        required_skills=payload.required_skills,
        pay_min=payload.pay_min,
        pay_max=payload.pay_max,
        pay_currency=payload.pay_currency,
        pay_period=payload.pay_period,
        pay_raw=payload.pay_raw,
        benefits=payload.benefits,
        source_content=payload.source_content,
        status=payload.status,
        notes=payload.notes,
        extraction_confidence=payload.extraction_confidence,
        extraction_warnings=payload.extraction_warnings,
    )
    _apply_pay_annualization(job)
    db.add(job)
    db.flush()
    _replace_links(db, job, payload.links)
    db.add(_status_event(job, None, payload.status, payload.status_note))
    db.commit()
    db.refresh(job)
    return job


def _matches_search(job: models.Job, search: str) -> bool:
    query = search.casefold().strip()
    if not query:
        return True
    values = [
        job.company,
        job.role_title,
        job.category.value,
        job.status.value,
        job.notes or "",
        job.location or "",
        job.remote_type or "",
    ]
    values.extend(link.url for link in job.links)
    values.extend(link.label for link in job.links)
    return any(query in value.casefold() for value in values)


def list_jobs(
    db: Session,
    include_archived: bool = False,
    search: str | None = None,
    status: models.JobStatus | None = None,
    category: models.JobCategory | None = None,
    health_filter: str | None = None,
) -> list[models.Job]:
    statement = select(models.Job).order_by(models.Job.updated_at.desc())
    if not include_archived:
        statement = statement.where(models.Job.status.notin_(HIDDEN_STATUSES))
    if status:
        statement = statement.where(models.Job.status == status)
    if category:
        statement = statement.where(models.Job.category == category)
    jobs = list(db.scalars(statement).all())
    if search:
        jobs = [job for job in jobs if _matches_search(job, search)]
    jobs = health_filtered_jobs(jobs, health_filter)
    return jobs


def top_gaps_for_job(db: Session, job: models.Job) -> tuple[list[str], str | None]:
    suggestion = latest_resume_suggestion(db, job.id)
    if suggestion:
        gaps = _unique_nonempty([*suggestion.missing_skills, *suggestion.weak_skills])
        return gaps[:MAX_TOP_GAPS], "resume_match"

    if job.analysis:
        gaps = _unique_nonempty([*job.analysis.required_skills, *job.analysis.technologies])
        if gaps:
            return gaps[:MAX_TOP_GAPS], "analysis"

    gaps = _unique_nonempty([*job.required_skills])
    if gaps:
        return gaps[:MAX_TOP_GAPS], "analysis"

    return [], None


def to_job_list_item(db: Session, job: models.Job) -> schemas.JobListItem:
    top_gaps, top_gaps_source = top_gaps_for_job(db, job)
    return schemas.JobListItem.model_validate(job).model_copy(
        update={
            "top_gaps": top_gaps,
            "top_gaps_source": top_gaps_source,
        }
    )


def list_job_items(
    db: Session,
    include_archived: bool = False,
    search: str | None = None,
    status: models.JobStatus | None = None,
    category: models.JobCategory | None = None,
    health_filter: str | None = None,
) -> list[schemas.JobListItem]:
    return [
        to_job_list_item(db, job)
        for job in list_jobs(
            db,
            include_archived=include_archived,
            search=search,
            status=status,
            category=category,
            health_filter=health_filter,
        )
    ]


def get_job(db: Session, job_id: str) -> models.Job | None:
    return db.get(models.Job, job_id)


def update_job(db: Session, job: models.Job, payload: schemas.JobUpdate) -> models.Job:
    values = payload.model_dump(exclude_unset=True)
    links = values.pop("links", None)
    status_note = values.pop("status_note", None)
    if values.get("selected_resume_option_id") is not None and not db.get(
        models.ResumeOption,
        values["selected_resume_option_id"],
    ):
        raise ValueError("Resume option not found")
    if values.get("selected_cover_letter_template_id") is not None and not db.get(
        models.CoverLetterTemplate,
        values["selected_cover_letter_template_id"],
    ):
        raise ValueError("Cover letter template not found")
    old_status = job.status
    pay_keys = {"pay_min", "pay_max", "pay_currency", "pay_period", "pay_raw"}
    for key, value in values.items():
        setattr(job, key, value)
    if pay_keys.intersection(values):
        _apply_pay_annualization(job)
    if links is not None:
        _replace_links(db, job, [schemas.JobLinkCreate(**link) for link in links])
    if "status" in values and old_status != job.status:
        db.add(_status_event(job, old_status, job.status, status_note))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_status_event(
    db: Session,
    job: models.Job,
    payload: schemas.JobStatusEventCreate,
) -> models.Job:
    event = models.JobStatusEvent(job=job, to_status=payload.to_status, note=payload.note)
    if payload.changed_at is not None:
        event.changed_at = payload.changed_at
    db.add(event)
    db.flush()
    _reconcile_status_history(db, job)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_status_event(
    db: Session,
    job: models.Job,
    event_id: str,
    payload: schemas.JobStatusEventUpdate,
) -> models.Job:
    event = next((item for item in job.status_events if item.id == event_id), None)
    if event is None:
        raise LookupError("Status event not found")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(event, key, value)
    db.add(event)
    db.flush()
    _reconcile_status_history(db, job)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def delete_status_event(
    db: Session,
    job: models.Job,
    event_id: str,
) -> models.Job:
    event = next((item for item in job.status_events if item.id == event_id), None)
    if event is None:
        raise LookupError("Status event not found")
    db.delete(event)
    db.flush()
    db.refresh(job)
    _reconcile_status_history(db, job)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_application_status(
    db: Session,
    job: models.Job,
    status: models.JobStatus,
    notes: str | None = None,
) -> models.Job:
    old_status = job.status
    job.status = status
    if notes is not None:
        job.notes = notes
    if old_status != status:
        db.add(_status_event(job, old_status, status, notes))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def archive_job(db: Session, job: models.Job) -> models.Job:
    return update_application_status(db, job, models.JobStatus.archived)


def latest_resume_suggestion(
    db: Session,
    job_id: str,
) -> models.ResumeSuggestion | None:
    return db.scalars(
        select(models.ResumeSuggestion)
        .where(models.ResumeSuggestion.job_id == job_id)
        .order_by(models.ResumeSuggestion.created_at.desc())
        .limit(1)
    ).first()


def latest_advanced_analysis(
    db: Session,
    job_id: str,
) -> models.AdvancedJobAnalysis | None:
    return db.scalars(
        select(models.AdvancedJobAnalysis)
        .where(models.AdvancedJobAnalysis.job_id == job_id)
        .order_by(models.AdvancedJobAnalysis.created_at.desc())
        .limit(1)
    ).first()


def latest_asset_recommendation(
    db: Session,
    job_id: str,
) -> models.AssetRecommendationSnapshot | None:
    return db.scalars(
        select(models.AssetRecommendationSnapshot)
        .where(models.AssetRecommendationSnapshot.job_id == job_id)
        .order_by(models.AssetRecommendationSnapshot.created_at.desc())
        .limit(1)
    ).first()


def find_duplicate_candidates(
    db: Session,
    company: str,
    role_title: str,
    urls: list[str],
) -> list[schemas.JobDuplicateCandidate]:
    normalized_urls = {url.strip().casefold() for url in urls if url and url.strip()}
    candidates: dict[str, schemas.JobDuplicateCandidate] = {}

    for job in db.scalars(select(models.Job)).all():
        matched_on: list[str] = []
        if company.strip() and role_title.strip():
            same_company = job.company.strip().casefold() == company.strip().casefold()
            same_role = job.role_title.strip().casefold() == role_title.strip().casefold()
            if same_company and same_role:
                matched_on.append("company_role")
        if normalized_urls:
            job_urls = {link.url.strip().casefold() for link in job.links}
            if job_urls.intersection(normalized_urls):
                matched_on.append("url")
        if matched_on:
            candidates[job.id] = schemas.JobDuplicateCandidate(
                id=job.id,
                company=job.company,
                role_title=job.role_title,
                status=job.status,
                matched_on=matched_on,
            )

    return list(candidates.values())
