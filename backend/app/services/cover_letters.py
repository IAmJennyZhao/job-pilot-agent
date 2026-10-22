"""Letters share immutable runs, revisions and approvals; prose has its own evidence policy."""
import copy
import json
from datetime import timedelta
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app import models
from app.letter_schemas import LetterDraft, LetterAssessment
from app.letter_prompts import VERSION, system
from app.services import ai_service, resume_generation as runs, resume_review as review, letter_validation as policy
from app.services.intake_preferences import digest
from app.services.tailoring_provider import ProviderFailure


def extend_snapshot(db, snapshot, options):
    snapshot = copy.deepcopy(snapshot)
    template = None
    if options.template_id:
        row = db.get(models.CoverLetterTemplate, options.template_id)
        if not row or row.resume_profile_id != snapshot["profile_id"]:
            raise HTTPException(404, "Letter template not found for this profile.")
        # Only measurements reach the writer. Referrals/history in a style sample are not facts.
        template = {"id": row.id, "title": row.title, "body": row.body, "hash": digest(row.body)}
    snapshot.update(document_kind="cover_letter", letter_version=1, letter_options=options.model_dump(),
        letter_template=template, letter_prompt_version=VERSION,
        letter_prompt_hashes={s: digest(system(s)) for s in ("letter_draft", "letter_assess")})
    return snapshot


def draft_input(snapshot, repair=None):
    template = snapshot["letter_template"]
    body = template["body"] if template else ""
    return {"input_hash": digest(snapshot), "approved_evidence": snapshot["projection"],
        "job_evidence": policy.job_evidence(snapshot), "options": snapshot["letter_options"],
        "style": {"paragraph_count": len([p for p in body.split("\n\n") if p.strip()]),
                  "word_count": len(body.split())} if template else None, "repair": repair}


def scoped(db, run_id):
    run = runs.scoped_run(db, run_id)
    if not policy.is_letter(run.snapshot):
        raise HTTPException(404, "Cover-letter run not found.")
    return run


def baseline(db, baseline_id):
    row, run = review.baseline_for(db, baseline_id)
    if not policy.is_letter(run.snapshot):
        raise HTTPException(404, "Cover-letter draft not found.")
    return row, run


def expire_checks(db):
    # Reads recover interrupted checks, but never call a provider.
    cutoff = runs.now() - timedelta(seconds=70)
    db.execute(update(models.TailoringStageAttempt).where(models.TailoringStageAttempt.stage == "letter_check",
        models.TailoringStageAttempt.state == "running", models.TailoringStageAttempt.started_at < cutoff)
        .values(state="interrupted", finished_at=runs.now(), error="Evidence check expired. Retry explicitly; no automatic request was made."))
    db.commit()


def assessment_for(db, run, row):
    attempts = list(db.scalars(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run.id)
        .order_by(models.TailoringStageAttempt.attempt.desc())))
    manual = [a for a in attempts if a.stage == "letter_check" and a.input_data.get("revision_id") == row.id]
    if manual:
        latest = manual[0]
        return latest.output_data if latest.state in {"passed", "failed"} and latest.input_data["content_hash"] == row.content_hash else None
    if isinstance(row, models.ResumeEditRevision):
        return None
    return next((a.output_data for a in attempts if a.stage == "letter_assess" and a.state == "passed"
        and a.input_data["content_hash"] == row.content_hash), None)


def structural_report(content, snapshot):
    report = policy.validate(content, snapshot)
    report["issues"] = [i for i in report["issues"] if i["message"] != "Run the independent sentence evidence check before review."]
    report["valid"] = not report["issues"]
    return report


def stage_call(engine, run_id, stage, number, data, snapshot, deadline, content=None, existing_id=None):
    model = LetterDraft if stage == "letter_draft" else LetterAssessment
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    bound = len(payload.encode()) + len(system(stage).encode()) + len(json.dumps(model.model_json_schema()).encode()) + snapshot["limits"]["output_tokens"]
    if bound > snapshot["limits"]["context_tokens"]:
        raise ProviderFailure("Letter request exceeds the context budget. No evidence was truncated.")
    timeout = min(snapshot["limits"]["attempt_seconds"], (deadline - runs.now()).total_seconds())
    if timeout <= 0:
        raise ProviderFailure("Letter request deadline expired.")
    if existing_id is None:
        with Session(engine) as db:
            runs.lock_live(db, run_id)
            row = models.TailoringStageAttempt(run_id=run_id, stage=stage, attempt=number, state="running",
                input_data=data, input_hash=digest(data), prompt_version=VERSION, started_at=runs.now())
            db.add(row); db.commit(); existing_id = row.id
    output, metadata, report, error, repairable = None, {}, None, None, True
    try:
        output, metadata = ai_service.get_tailoring_output(model, system(stage), payload, model=snapshot["model"], timeout=timeout)
        output = model.model_validate(output).model_dump(mode="json")
        report = structural_report(policy.build_content(LetterDraft.model_validate(output), None, snapshot), snapshot) if stage == "letter_draft" else policy.validate(content, snapshot, output)
        if not report["valid"]:
            error = "Letter evidence or structure needs correction. Inspect the saved findings."
    except ValidationError:
        output, error = None, "Output did not match the letter contract."
    except ProviderFailure as exc:
        error, repairable = exc.safe_message, exc.repairable
    except Exception:
        error, repairable = "Evidence provider stopped unexpectedly. Retry explicitly after checking progress.", False
    with Session(engine) as db:
        row = db.get(models.TailoringStageAttempt, existing_id)
        run = db.get(models.TailoringRun, run_id)
        if row.state != "running":
            raise ProviderFailure("Late evidence output discarded; the attempt is no longer active.")
        if stage != "letter_check":
            runs.lock_live(db, run_id)
        if runs.now() >= deadline or review.source_problem(db, run):
            output, report, error, repairable = None, None, "Sources changed or the request expired; output was discarded.", False
        row.output_data, row.output_hash = output, digest(output) if output is not None else None
        row.validation, row.provider_metadata = report, metadata
        row.state, row.error, row.finished_at = ("failed" if error else "passed"), error, runs.now()
        db.commit()
    if error and not repairable:
        raise ProviderFailure(error)
    return output, report, error


def execute(engine, run_id):
    try:
        with Session(engine) as db:
            claim = db.execute(update(models.TailoringRun).where(models.TailoringRun.id == run_id,
                models.TailoringRun.state == "pending", models.TailoringRun.deadline_at > runs.now()).values(state="running"))
            if claim.rowcount != 1:
                return
            run = db.get(models.TailoringRun, run_id)
            snapshot, deadline = copy.deepcopy(run.snapshot), runs.aware(run.deadline_at)
            db.commit()
        repair = None
        for attempt in (1, 2):
            output, report, error = stage_call(engine, run_id, "letter_draft", attempt, draft_input(snapshot, repair), snapshot, deadline)
            content = policy.build_content(LetterDraft.model_validate(output), None, snapshot) if output else None
            if not error:
                data = {"input_hash": digest(snapshot), **policy.assessment_payload(content, snapshot)}
                assessment, report, error = stage_call(engine, run_id, "letter_assess", attempt, data, snapshot, deadline, content)
            if not error:
                with Session(engine) as db:
                    run = runs.lock_live(db, run_id)
                    db.add(models.TailoredRevision(run_id=run_id, content=content, content_hash=digest(content),
                        plain_text=policy.text_for(content, snapshot), validation=report))
                    run.state, run.active_key, run.finished_at = "completed", None, runs.now()
                    db.commit()
                return
            repair = {"previous_output": output, "issues": report["issues"] if report else [error]}
        raise ProviderFailure("Letter validation failed after one repair. No successful draft was created.")
    except ProviderFailure as exc:
        runs.fail(engine, run_id, exc.safe_message)
    except Exception:
        runs.fail(engine, run_id, "Letter generation stopped unexpectedly. Saved checkpoints remain available.")


def check(db, baseline_id, request):
    expire_checks(db)
    row, run = baseline(db, baseline_id)
    review.baseline_for(db, baseline_id, lock=True)
    edits = review.revisions(db, row)
    head = edits[-1] if edits else row
    data = {"input_hash": run.input_hash, "revision_id": request.expected_revision_id,
        "request_key": request.request_key, "request_hash": digest(request.model_dump()),
        **policy.assessment_payload(head.content, run.snapshot)}
    attempts = list(db.scalars(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run.id,
        models.TailoringStageAttempt.stage == "letter_check").order_by(models.TailoringStageAttempt.attempt)))
    old = next((a for a in attempts if a.input_data["request_key"] == request.request_key), None)
    if old:
        if old.input_data["request_hash"] != data["request_hash"]:
            raise HTTPException(409, "Evidence-check request key belongs to different content.")
        return
    if head.id != request.expected_revision_id or head.content_hash != request.content_hash:
        raise HTTPException(409, "A newer revision was saved. Inspect it before checking evidence.")
    if db.scalar(select(models.ResumeReviewApproval).where(models.ResumeReviewApproval.revision_id == head.id)):
        raise HTTPException(409, "Reviewed evidence is frozen. Save a new revision before rechecking.")
    if any(a.state == "running" for a in attempts):
        raise HTTPException(409, "An evidence check is already running. Refresh progress.")
    problem = review.source_problem(db, run)
    if problem:
        raise HTTPException(409, problem)
    report = structural_report(head.content, run.snapshot)
    if not report["valid"]:
        raise HTTPException(422, "Fix the saved structural findings before checking sentence evidence.")
    from app.config import get_settings
    if not get_settings().openai_api_key:
        raise HTTPException(422, "Configure the AI provider before checking sentence evidence. Saved edits are preserved.")
    attempt = models.TailoringStageAttempt(run_id=run.id, stage="letter_check", attempt=len(attempts)+1,
        state="running", input_data=data, input_hash=digest(data), prompt_version=VERSION, started_at=runs.now())
    db.add(attempt); db.commit()
    attempt_id, run_id, snapshot, content, engine = attempt.id, run.id, copy.deepcopy(run.snapshot), copy.deepcopy(head.content), db.get_bind()
    db.close()
    try:
        stage_call(engine, run_id, "letter_check", len(attempts)+1, data, snapshot, runs.now()+timedelta(seconds=60), content, attempt_id)
    except ProviderFailure as exc:
        with Session(engine) as session:
            session.execute(update(models.TailoringStageAttempt).where(models.TailoringStageAttempt.id == attempt_id,
                models.TailoringStageAttempt.state == "running").values(state="failed", error=exc.safe_message, finished_at=runs.now()))
            session.commit()


def view(db, baseline_id, revision_id=None):
    expire_checks(db)
    base, run = baseline(db, baseline_id)
    result = review.view(db, baseline_id, revision_id)
    result["checks"] = [{"id": a.id, "revision_id": a.input_data["revision_id"], "state": a.state, "error": a.error}
        for a in db.scalars(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run.id,
            models.TailoringStageAttempt.stage == "letter_check").order_by(models.TailoringStageAttempt.attempt.desc()))]
    chosen = review.selected_revision(base, review.revisions(db, base), result["revision"]["id"])
    result["sentence_assessment"] = assessment_for(db, run, chosen)
    return result


def download(db, baseline_id, revision_id, variant, format):
    row, run = baseline(db, baseline_id)
    chosen = review.selected_revision(row, review.revisions(db, row), revision_id)
    approval = db.scalar(select(models.ResumeReviewApproval).where(models.ResumeReviewApproval.revision_id == chosen.id))
    report = policy.validate(chosen.content, run.snapshot, assessment_for(db, run, chosen))
    if not approval or not report["valid"] or (approval.content_hash, approval.validation_hash, approval.input_hash) != (digest(chosen.content), digest(report), run.input_hash):
        raise HTTPException(409, "Review this exact saved letter revision before exporting.")
    if format not in {"txt", "md"} or not 0 <= variant < len(chosen.content["variants"]):
        raise HTTPException(404, "Letter export not found.")
    text = policy.text_for(chosen.content, run.snapshot, variant)
    return (policy.markdown(text) if format == "md" else text).encode("utf-8")
