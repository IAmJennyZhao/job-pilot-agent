from collections import Counter, defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import job_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

FUNNEL_STAGES = [
    models.JobStatus.saved,
    models.JobStatus.applied,
    models.JobStatus.recruiter_screen,
    models.JobStatus.tech_screen,
    models.JobStatus.final_interview,
    models.JobStatus.offer,
]
STAGE_RANK = {status: index for index, status in enumerate(FUNNEL_STAGES)}
TERMINAL_STATUSES = {
    models.JobStatus.rejected,
    models.JobStatus.withdrawn,
    models.JobStatus.ghosted,
}
HIDDEN_STATUSES = {
    models.JobStatus.archived,
    models.JobStatus.ghosted,
}
OPEN_OPPORTUNITY_STATUSES = set(FUNNEL_STAGES)
STALE_DAYS = {
    models.JobStatus.saved: 7,
    models.JobStatus.applied: 14,
    models.JobStatus.recruiter_screen: 7,
    models.JobStatus.tech_screen: 7,
    models.JobStatus.final_interview: 7,
}
LOW_CONFIDENCE_THRESHOLD = 80
MAX_INSIGHTS = 6
MAX_TOP_GAPS = 5


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _latest_movement_at(job: models.Job) -> datetime:
    if job.status_events:
        return max(_as_utc(event.changed_at) for event in job.status_events)
    return _as_utc(job.updated_at or job.created_at)


def _days_since(value: datetime) -> int:
    return max(0, (_as_utc(datetime.now(timezone.utc)) - _as_utc(value)).days)


def _job_insight(
    job: models.Job,
    issue_label: str,
    recommended_action: str,
    last_movement_at: datetime | None = None,
) -> schemas.DashboardJobInsight:
    return schemas.DashboardJobInsight(
        id=job.id,
        company=job.company,
        role_title=job.role_title,
        status=job.status,
        last_movement_at=last_movement_at or _latest_movement_at(job),
        issue_label=issue_label,
        recommended_action=recommended_action,
    )


def _unique_nonempty(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _furthest_stage_rank(job: models.Job) -> int:
    rank = STAGE_RANK.get(job.status, 0)
    for event in job.status_events:
        event_rank = STAGE_RANK.get(event.to_status)
        if event_rank is not None:
            rank = max(rank, event_rank)
    return rank


def _build_sankey(jobs: list[models.Job]) -> schemas.DashboardSankey:
    node_counts: Counter[str] = Counter()
    link_counts: Counter[tuple[str, str]] = Counter()

    for job in jobs:
        if job.status == models.JobStatus.archived:
            continue

        rank = _furthest_stage_rank(job)
        reached = FUNNEL_STAGES[: rank + 1]
        for status in reached:
            node_counts[status.value] += 1
        for source, target in zip(reached, reached[1:]):
            link_counts[(source.value, target.value)] += 1

        if job.status in TERMINAL_STATUSES:
            terminal_id = job.status.value
            node_counts[terminal_id] += 1
            link_counts[(FUNNEL_STAGES[rank].value, terminal_id)] += 1

    nodes = [
        schemas.DashboardSankeyNode(
            id=status.value,
            label=status.value,
            count=node_counts.get(status.value, 0),
            kind="stage",
        )
        for status in FUNNEL_STAGES
    ]
    nodes.extend(
        schemas.DashboardSankeyNode(
            id=status.value,
            label=status.value,
            count=node_counts.get(status.value, 0),
            kind="terminal",
        )
        for status in [models.JobStatus.rejected, models.JobStatus.withdrawn, models.JobStatus.ghosted]
    )
    links = [
        schemas.DashboardSankeyLink(source=source, target=target, value=value)
        for (source, target), value in sorted(link_counts.items())
        if value > 0
    ]
    return schemas.DashboardSankey(nodes=nodes, links=links)


def _build_search_health(open_jobs: list[models.Job]) -> schemas.DashboardSearchHealth:
    stale_jobs: list[tuple[int, schemas.DashboardJobInsight]] = []
    needs_analysis: list[schemas.DashboardJobInsight] = []

    for job in open_jobs:
        last_movement = _latest_movement_at(job)
        days = _days_since(last_movement)
        stale_threshold = STALE_DAYS.get(job.status)
        if stale_threshold is not None and days >= stale_threshold:
            stale_jobs.append(
                (
                    days,
                    _job_insight(
                        job,
                        f"No movement for {days}d",
                        "Review or mark ghosted.",
                        last_movement,
                    ),
                )
            )
        if job.fit_score is None or job.analysis is None:
            needs_analysis.append(
                _job_insight(
                    job,
                    "Missing fit analysis" if job.fit_score is None else "Missing job analysis",
                    "Run job intelligence.",
                )
            )

    return schemas.DashboardSearchHealth(
        stale_jobs=[item for _, item in sorted(stale_jobs, key=lambda pair: pair[0], reverse=True)[:MAX_INSIGHTS]],
        needs_analysis=needs_analysis[:MAX_INSIGHTS],
    )


def _has_pay(job: models.Job) -> bool:
    return any(
        value is not None
        for value in [job.pay_min, job.pay_max, job.pay_annual_min, job.pay_annual_max]
    ) or bool((job.pay_raw or "").strip())


def _latest_advanced_analysis(job: models.Job) -> models.AdvancedJobAnalysis | None:
    return max(job.advanced_analyses, key=lambda analysis: analysis.created_at, default=None)


def _build_coverage_risk(open_jobs: list[models.Job]) -> schemas.DashboardCoverageRisk:
    missing_pay: list[schemas.DashboardJobInsight] = []
    missing_fit: list[schemas.DashboardJobInsight] = []
    low_confidence: list[schemas.DashboardJobInsight] = []
    risk_jobs: dict[str, set[str]] = defaultdict(set)
    risk_labels: dict[str, str] = {}

    for job in open_jobs:
        if not _has_pay(job):
            missing_pay.append(_job_insight(job, "Missing pay", "Review posting or add pay."))
        if job.fit_score is None:
            missing_fit.append(_job_insight(job, "Missing fit score", "Run job intelligence."))
        if job.extraction_confidence is None or job.extraction_confidence < LOW_CONFIDENCE_THRESHOLD:
            label = "No extraction confidence" if job.extraction_confidence is None else f"Confidence {job.extraction_confidence}"
            low_confidence.append(_job_insight(job, label, "Review extracted details."))

        analysis = _latest_advanced_analysis(job)
        for risk in analysis.risks_gaps if analysis else []:
            label = risk.strip()
            key = label.casefold()
            if not label:
                continue
            risk_jobs[key].add(job.id)
            risk_labels.setdefault(key, label)

    recurring_risks = [
        schemas.DashboardRiskSignal(
            label=risk_labels[key],
            count=len(job_ids),
            job_ids=sorted(job_ids),
        )
        for key, job_ids in risk_jobs.items()
        if len(job_ids) >= 1
    ]
    recurring_risks.sort(key=lambda item: (-item.count, item.label.casefold()))

    return schemas.DashboardCoverageRisk(
        missing_pay=missing_pay[:MAX_INSIGHTS],
        missing_fit=missing_fit[:MAX_INSIGHTS],
        low_confidence=low_confidence[:MAX_INSIGHTS],
        recurring_risks=recurring_risks[:MAX_INSIGHTS],
    )


def _gap_skills_for_job(
    db: Session,
    job: models.Job,
) -> tuple[list[str], str | None]:
    suggestion = job_service.latest_resume_suggestion(db, job.id)
    if suggestion:
        return _unique_nonempty([*suggestion.missing_skills, *suggestion.weak_skills]), "resume_match"
    if job.analysis:
        return _unique_nonempty([*job.analysis.required_skills, *job.analysis.technologies]), "analysis"
    return _unique_nonempty(job.required_skills), "analysis"


def _build_top_skill_gaps(
    db: Session,
    open_jobs: list[models.Job],
) -> list[schemas.DashboardSkillGap]:
    gap_jobs: dict[str, list[models.Job]] = defaultdict(list)
    gap_labels: dict[str, str] = {}
    gap_sources: dict[str, set[str]] = defaultdict(set)

    for job in open_jobs:
        skills, source = _gap_skills_for_job(db, job)
        if source is None:
            continue
        for skill in skills:
            key = skill.casefold()
            if any(existing.id == job.id for existing in gap_jobs[key]):
                continue
            gap_jobs[key].append(job)
            gap_labels.setdefault(key, skill)
            gap_sources[key].add(source)

    rows: list[schemas.DashboardSkillGap] = []
    for key, affected_jobs in gap_jobs.items():
        source = "resume_match" if "resume_match" in gap_sources[key] else "analysis"
        skill_name = gap_labels[key]
        rows.append(
            schemas.DashboardSkillGap(
                skill_name=skill_name,
                count=len(affected_jobs),
                source=source,
                affected_jobs=[
                    _job_insight(job, f"Needs {skill_name}", "Review affected job.")
                    for job in affected_jobs[:4]
                ],
                suggested_action=f"Affects {len(affected_jobs)} active opportunities.",
            )
        )

    rows.sort(key=lambda row: (-row.count, row.skill_name.casefold()))
    return rows[:MAX_TOP_GAPS]


@router.get("/summary", response_model=schemas.DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    jobs = list(db.scalars(select(models.Job)).all())
    active_jobs = [job for job in jobs if job.status not in HIDDEN_STATUSES]
    open_jobs = [job for job in jobs if job.status in OPEN_OPPORTUNITY_STATUSES]
    archived_jobs = sum(1 for job in jobs if job.status == models.JobStatus.archived)
    ghosted_jobs = sum(1 for job in jobs if job.status == models.JobStatus.ghosted)
    status_counts = Counter(job.status.value for job in jobs)
    by_status = {
        status.value: status_counts.get(status.value, 0)
        for status in models.JobStatus
    }
    sankey = _build_sankey(jobs)
    search_health = _build_search_health(open_jobs)
    coverage_risk = _build_coverage_risk(open_jobs)
    top_skill_gaps = _build_top_skill_gaps(db, open_jobs)
    needs_resume_tailoring = sum(
        1
        for job in open_jobs
        if job.status == models.JobStatus.saved or job.fit_score is None
    )
    interviewing = sum(
        1
        for job in active_jobs
        if job.status
        in {
            models.JobStatus.recruiter_screen,
            models.JobStatus.tech_screen,
            models.JobStatus.final_interview,
        }
    )
    health = schemas.DashboardHealth(
        active_jobs=len(active_jobs),
        stale_jobs=len(search_health.stale_jobs),
        missing_fit=sum(1 for job in open_jobs if job.fit_score is None),
        missing_pay=sum(1 for job in open_jobs if not _has_pay(job)),
        low_confidence=sum(
            1
            for job in open_jobs
            if job.extraction_confidence is None or job.extraction_confidence < LOW_CONFIDENCE_THRESHOLD
        ),
        ghosted_jobs=ghosted_jobs,
        archived_jobs=archived_jobs,
    )

    if search_health.stale_jobs:
        next_action = "Review stale applications."
    elif search_health.needs_analysis:
        next_action = "Run job intelligence for active roles."
    elif top_skill_gaps:
        next_action = f"Study or prove {top_skill_gaps[0].skill_name}."
    else:
        next_action = "Add a job description to start tracking your search."

    return schemas.DashboardSummary(
        total_jobs=len(active_jobs),
        archived_jobs=archived_jobs,
        ghosted_jobs=ghosted_jobs,
        by_status=by_status,
        needs_resume_tailoring=needs_resume_tailoring,
        interviewing=interviewing,
        top_skill_gaps=top_skill_gaps,
        recent_interviews=[],
        next_recommended_action=next_action,
        sankey=sankey,
        health=health,
        search_health=search_health,
        coverage_risk=coverage_risk,
    )
