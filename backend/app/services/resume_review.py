"""Append-only manual editing and exact-version approval, independent of AI settings."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app import models
from app.services.intake_preferences import digest
from app.services.resume_generation import now, aware, scoped_run
from app.services import tailoring_source_service
from app.services.resume_review_validation import editable, build_content, validate_revision, differences, VERSION
from app.services.resume_validation import plain_text


def baseline_for(db, baseline_id, lock=False):
    if lock:
        connection = db.connection()
        if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    query = select(models.TailoredRevision).where(models.TailoredRevision.id == baseline_id)
    baseline = db.scalar(query.with_for_update() if lock else query)
    if not baseline:
        raise HTTPException(404, "Generated resume not found.")
    run = scoped_run(db, baseline.run_id)
    return baseline, run


def revisions(db, baseline):
    return list(db.scalars(select(models.ResumeEditRevision).where(models.ResumeEditRevision.baseline_id == baseline.id).order_by(models.ResumeEditRevision.sequence)))


def selected_revision(baseline, edits, revision_id):
    chosen = next((r for r in [baseline, *edits] if r.id == revision_id), None)
    if chosen is None:
        raise HTTPException(404, "Revision does not belong to this resume.")
    return chosen


def source_problem(db, run):
    state = db.get(models.TailoringProfileState, run.profile_id)
    source = db.get(models.TailoringSourceVersion, run.source_id)
    if not source or tailoring_source_service.source_status(db, source) == "revoked":
        return "The source bundle was revoked. Activate approved sources and generate a fresh draft."
    if not state or state.active_source_id != run.source_id:
        return "The active source bundle changed. Generate a fresh draft before review."
    try:
        tailoring_source_service.validate_stored(source)
    except (ValueError, HTTPException):
        return "The source bundle failed integrity checks. Review approved sources before continuing."
    job = db.get(models.Job, run.job_id)
    if not job or any(run.snapshot["job"][key] != getattr(job, key) for key in ("company", "role_title", "source_content")):
        return "The job description or role changed. Generate a fresh draft before review."
    return None


def validation_for(row, baseline, edits, run):
    parent = None
    if row.id != baseline.id:
        parent = selected_revision(baseline, edits, row.parent_id or baseline.id).content
    return validate_revision(row.content, run.snapshot, parent)


def view(db, baseline_id, revision_id=None):
    baseline, run = baseline_for(db, baseline_id)
    edits = revisions(db, baseline)
    head = edits[-1] if edits else baseline
    selected = selected_revision(baseline, edits, revision_id or head.id)
    approvals = {a.revision_id: a for a in db.scalars(select(models.ResumeReviewApproval).where(models.ResumeReviewApproval.baseline_id == baseline.id))}
    validation = validation_for(selected, baseline, edits, run)
    problem = source_problem(db, run)
    approval = approvals.get(selected.id)
    eligible = selected.id == head.id and validation["valid"] and not problem
    parent = selected_revision(baseline, edits, selected.parent_id or baseline.id) if selected.id != baseline.id else baseline
    return {"baseline_id": baseline.id, "run_id": run.id, "job_id": run.job_id, "profile_id": run.profile_id,
        "current_revision_id": head.id, "input_hash": run.input_hash, "source_problem": problem,
        "revision": {"id": selected.id, "sequence": getattr(selected, "sequence", 0), "origin": getattr(selected, "origin", "generated"),
            "parent_id": parent.id if selected.id != baseline.id else None, "restored_from_id": getattr(selected, "restored_from_id", None),
            "content": selected.content, "content_hash": selected.content_hash, "plain_text": selected.plain_text,
            "edit": editable(selected.content), "validation": validation, "validation_hash": digest(validation),
            "created_at": aware(selected.created_at)},
        "approval": {"id": approval.id, "reviewed_at": aware(approval.reviewed_at), "content_hash": approval.content_hash} if approval else None,
        "approval_eligible": bool(eligible),
        "approved_current": bool(eligible and approval and approval.validation_hash == digest(validation) and approval.content_hash == selected.content_hash and approval.input_hash == run.input_hash),
        "history": [{"id": r.id, "sequence": getattr(r, "sequence", 0), "origin": getattr(r, "origin", "generated"),
            "created_at": aware(r.created_at), "valid": validation_for(r, baseline, edits, run)["valid"], "reviewed": r.id in approvals} for r in reversed([baseline, *edits])],
        "changes_from_baseline": differences(baseline.content, selected.content), "changes_from_parent": differences(parent.content, selected.content),
        "evidence": run.snapshot["projection"]["claims"], "records": run.snapshot["projection"]["records"],
        "skill_groups": run.snapshot["projection"]["skill_groups"], "technology_catalog": run.snapshot["projection"]["technology_catalog"]}


def save(db, baseline_id, payload, restore=False):
    baseline, run = baseline_for(db, baseline_id, lock=True)
    fingerprint = digest({"action": "restore" if restore else "edit", "payload": payload.model_dump()})
    duplicate = db.scalar(select(models.ResumeEditRevision).where(models.ResumeEditRevision.baseline_id == baseline.id,
        models.ResumeEditRevision.request_key == payload.request_key))
    if duplicate:
        if duplicate.request_hash != fingerprint:
            raise HTTPException(409, "This request key was used for different edits.")
        return duplicate.id, False
    edits = revisions(db, baseline)
    head = edits[-1] if edits else baseline
    if payload.expected_revision_id != head.id:
        raise HTTPException(409, "A newer revision was saved. Your edits are preserved locally; compare with the current version before saving again.")
    restored = selected_revision(baseline, edits, payload.revision_id) if restore else None
    if restored:
        from app.review_schemas import ResumeEdit
        edit = ResumeEdit.model_validate(editable(restored.content))
    else:
        edit = payload.edit
    content = build_content(edit, baseline.content, run.snapshot)
    validation = validate_revision(content, run.snapshot, head.content)
    row = models.ResumeEditRevision(baseline_id=baseline.id, parent_id=head.id if edits else None,
        sequence=len(edits)+1, origin="restored" if restore else "edited", restored_from_id=restored.id if restored else None,
        request_key=payload.request_key, request_hash=fingerprint, content=content, content_hash=digest(content),
        plain_text=plain_text(content), validation=validation, created_at=now())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another save completed first. Refresh history and compare before saving again.") from None
    return row.id, True


def approve(db, baseline_id, payload):
    baseline, run = baseline_for(db, baseline_id, lock=True)
    edits = revisions(db, baseline)
    head = edits[-1] if edits else baseline
    if payload.revision_id != head.id:
        raise HTTPException(409, "Only the current saved revision can be reviewed. Refresh the resume first.")
    validation = validation_for(head, baseline, edits, run)
    if (payload.content_hash, payload.validation_hash, payload.input_hash) != (digest(head.content), digest(validation), run.input_hash):
        raise HTTPException(409, "Content, validation or sources changed. Inspect the saved revision before reviewing it.")
    if not validation["valid"]:
        raise HTTPException(409, "Resolve blocking validation issues before marking this revision reviewed.")
    problem = source_problem(db, run)
    if problem:
        raise HTTPException(409, problem)
    existing = db.scalar(select(models.ResumeReviewApproval).where(models.ResumeReviewApproval.revision_id == head.id))
    if existing:
        if (existing.content_hash, existing.validation_hash, existing.input_hash) != (payload.content_hash, payload.validation_hash, payload.input_hash):
            raise HTTPException(409, "This historical approval used different validation. Create and review a new revision.")
        return False
    db.add(models.ResumeReviewApproval(baseline_id=baseline.id, edit_revision_id=head.id if edits else None,
        revision_id=head.id, content_hash=payload.content_hash, validation_hash=payload.validation_hash,
        input_hash=payload.input_hash, validator_version=VERSION, reviewed_at=now()))
    db.commit()
    return True
