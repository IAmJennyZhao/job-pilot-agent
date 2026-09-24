from datetime import date, datetime, time, timezone
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import job_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

TERMINAL_STATUSES = {
    models.JobStatus.rejected,
    models.JobStatus.withdrawn,
    models.JobStatus.ghosted,
}
MAX_INSIGHTS = 6
MAX_NEEDS_ANALYSIS = 3
MAX_TOP_GAPS = 5


def _job_insight(
    job: models.Job,
    issue_label: str,
    recommended_action: str,
) -> schemas.DashboardJobInsight:
    return schemas.DashboardJobInsight(
        id=job.id,
        company=job.company,
        role_title=job.role_title,
        status=job.status,
        last_movement_at=job_service.latest_movement_at(job),
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


def _build_sankey(jobs: list[models.Job]) -> schemas.DashboardSankey:
    node_counts: Counter[str] = Counter()
    recorded_counts: Counter[str] = Counter()
    link_counts: Counter[tuple[str, str]] = Counter()

    for job in jobs:
        if job.status == models.JobStatus.archived:
            continue

        for recorded in {job.status, *(event.to_status for event in job.status_events)}:
            recorded_counts[recorded.value] += 1
        rank = job_service.furthest_stage_rank(job)
        reached = job_service.FUNNEL_STATUSES[: rank + 1]
        for status in reached:
            node_counts[status.value] += 1
        for source, target in zip(reached, reached[1:]):
            link_counts[(source.value, target.value)] += 1

        if job.status in TERMINAL_STATUSES:
            terminal_id = job.status.value
            node_counts[terminal_id] += 1
            link_counts[(job_service.FUNNEL_STATUSES[rank].value, terminal_id)] += 1

    nodes = [
        schemas.DashboardSankeyNode(
            id=status.value,
            label=status.value,
            count=node_counts.get(status.value, 0),
            recorded_count=recorded_counts.get(status.value, 0),
            kind="stage",
        )
        for status in job_service.FUNNEL_STATUSES
    ]
    nodes.extend(
        schemas.DashboardSankeyNode(
            id=status.value,
            label=status.value,
            count=node_counts.get(status.value, 0),
            recorded_count=recorded_counts.get(status.value, 0),
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
    missing_data: list[schemas.DashboardJobInsight] = []

    for job in open_jobs:
        last_movement = job_service.latest_movement_at(job)
        days = job_service.days_since(last_movement)
        if job_service.is_stale(job):
            stale_jobs.append(
                (
                    days,
                    _job_insight(
                        job,
                        f"No movement for {days}d",
                        "Review or mark ghosted.",
                    ),
                )
            )
        if job_service.is_missing_core_data(job):
            missing_data.append(
                _job_insight(job, "Missing core coverage", "Review missing data.")
            )
        if job_service.needs_analysis(job):
            needs_analysis.append(
                _job_insight(
                    job,
                    "Missing fit analysis" if job.fit_score is None else "Missing job analysis",
                    "Run job intelligence.",
                )
            )

    needs_analysis.sort(
        key=lambda item: _needs_analysis_sort_key(
            next(job for job in open_jobs if job.id == item.id)
        )
    )

    return schemas.DashboardSearchHealth(
        stale_jobs=[item for _, item in sorted(stale_jobs, key=lambda pair: pair[0], reverse=True)[:MAX_INSIGHTS]],
        missing_data=missing_data[:MAX_INSIGHTS],
        needs_analysis=needs_analysis[:MAX_NEEDS_ANALYSIS],
    )


def _needs_analysis_sort_key(job: models.Job) -> tuple[int, int, float]:
    return (
        -job_service.current_stage_rank(job),
        -(job.fit_score if job.fit_score is not None else -1),
        -job_service.as_utc(job.updated_at or job.created_at).timestamp(),
    )


def _latest_advanced_analysis(job: models.Job) -> models.AdvancedJobAnalysis | None:
    return max(job.advanced_analyses, key=lambda analysis: analysis.created_at, default=None)


def _build_coverage_risk(open_jobs: list[models.Job]) -> schemas.DashboardCoverageRisk:
    missing_pay: list[schemas.DashboardJobInsight] = []
    missing_fit: list[schemas.DashboardJobInsight] = []
    low_confidence: list[schemas.DashboardJobInsight] = []
    risk_jobs: dict[str, set[str]] = defaultdict(set)
    risk_labels: dict[str, str] = {}

    for job in open_jobs:
        if not job_service.has_pay(job):
            missing_pay.append(_job_insight(job, "Missing pay", "Review posting or add pay."))
        if job.fit_score is None:
            missing_fit.append(_job_insight(job, "Missing fit score", "Run job intelligence."))
        if job.extraction_confidence is None or job.extraction_confidence < job_service.LOW_CONFIDENCE_THRESHOLD:
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
    known_skills = {
        name.casefold()
        for name in db.scalars(
            select(models.SkillGap.skill_name).where(models.SkillGap.user_level == models.UserLevel.high)
        )
    }

    for job in open_jobs:
        skills, source = _gap_skills_for_job(db, job)
        if source is None:
            continue
        for skill in skills:
            key = skill.casefold()
            if key in known_skills:
                continue
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
def get_dashboard_summary(saved_since: date | None = None, db: Session = Depends(get_db)):
    statement = select(models.Job)
    if saved_since:
        statement = statement.where(models.Job.created_at >= datetime.combine(saved_since, time.min, tzinfo=timezone.utc))
    jobs = list(db.scalars(statement).all())
    active_jobs = [job for job in jobs if job_service.is_open_opportunity(job)]
    open_jobs = [job for job in jobs if job_service.is_open_opportunity(job)]
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
        stale_jobs=sum(1 for job in open_jobs if job_service.is_stale(job)),
        missing_fit=sum(1 for job in open_jobs if job.fit_score is None),
        missing_pay=sum(1 for job in open_jobs if not job_service.has_pay(job)),
        low_confidence=sum(
            1
            for job in open_jobs
            if job.extraction_confidence is None or job.extraction_confidence < job_service.LOW_CONFIDENCE_THRESHOLD
        ),
        missing_data=sum(1 for job in open_jobs if job_service.is_missing_core_data(job)),
        ghosted_jobs=ghosted_jobs,
        archived_jobs=archived_jobs,
    )

    if search_health.stale_jobs:
        next_action = "Review stale applications."
    elif search_health.needs_analysis:
        next_action = "Run job intelligence for active roles."
    elif search_health.missing_data:
        next_action = "Complete missing opportunity details."
    elif top_skill_gaps:
        next_action = f"Study or prove {top_skill_gaps[0].skill_name}."
    elif open_jobs:
        next_action = "Your tracked opportunities are up to date."
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
