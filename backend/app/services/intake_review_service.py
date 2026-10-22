from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app import models, schemas
from app.intake_schemas import IntakeReview, IntakeSave
from app.services import job_service
from app.services.intake_preferences import digest, evaluate, active_preferences


def save(db, payload: IntakeSave):
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    fingerprint = digest(payload.model_dump(mode="json"))

    def existing():
        row = db.scalar(select(models.JobIntakeReview).where(models.JobIntakeReview.request_key == payload.request_key))
        if row and row.request_hash != fingerprint:
            raise HTTPException(409, "This save key belongs to a different review. Review your changes before saving again.")
        return db.get(models.Job, row.job_id) if row else None

    previous = existing()
    if previous:
        return previous
    review = IntakeReview.model_validate(payload.model_dump())
    evaluation = evaluate(db, review)
    if evaluation["evaluation_hash"] != payload.expected_evaluation_hash:
        raise HTTPException(409, "Preferences or review changed. Refresh the checks and review them before continuing.")
    if evaluation["duplicate_candidates"] and not payload.allow_duplicate:
        raise HTTPException(409, "A matching job is already saved. Open it, or explicitly confirm this is a separate posting.")
    source = active_preferences(db)
    # Recheck the active version within the save transaction.
    if (source.id if source else None) != evaluation["source_id"]:
        raise HTTPException(409, "Active sources changed. Refresh the preference checks.")
    try:
        job = job_service.save_job(db, payload.job.model_copy(update={"status": models.JobStatus.saved, "status_note": None}), commit=False)
        db.add(models.JobIntakeReview(job_id=job.id, request_key=payload.request_key, request_hash=fingerprint,
            review=review.model_dump(mode="json"), evaluation=evaluation,
            preference_snapshot=source.preferences if source else None, source_id=source.id if source else None,
            decision=payload.decision))
        db.commit()
        db.refresh(job)
        return job
    except IntegrityError:
        db.rollback()
        previous = existing()
        if previous:
            return previous
        raise HTTPException(409, "Save conflicted with another request. Review the saved jobs before retrying.") from None
    except Exception:
        db.rollback()
        raise


def preparation(db, job):
    saved = db.get(models.JobIntakeReview, job.id)
    source = active_preferences(db)
    stale = False
    current = None
    full_description_ready = False
    if saved:
        review = IntakeReview.model_validate(saved.review)
        for key in ("company", "role_title", "location", "remote_type", "pay_min", "pay_max", "pay_currency", "pay_period", "source_content"):
            stale |= getattr(review.job, key) != getattr(job, key)
        stale |= sorted(str(x.url) for x in review.job.links) != sorted(x.url for x in job.links)
        if not stale:
            current = evaluate(db, review)
            full_description_ready = current["full_description_ready"]
    return {"saved_evaluation": saved.evaluation if saved else None, "current_evaluation": current,
            "review_stale": stale, "sources_ready": bool(source), "full_description_ready": full_description_ready,
            "generation_available": False, "decision": saved.decision if saved else None}
