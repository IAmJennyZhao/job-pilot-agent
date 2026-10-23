"""Request-bound, checkpointed four-pass coordinator. Reads never call a model."""
import copy
import json
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app import models
from app.resume_prompts import system_for
from app.services import ai_service, profile_service, tailoring_source_service
from app.services.generation_inputs import capture, require_capture
from app.services.intake_preferences import digest
from app.services.resume_validation import STAGES, validate_stage, accuracy_report, assemble_content, plain_text, generation_version, output_models, prompt_versions
from app.services.tailoring_provider import ProviderFailure


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def expire_runs(db):
    expired = list(db.scalars(select(models.TailoringRun).where(models.TailoringRun.state.in_(["pending", "running"]), models.TailoringRun.deadline_at <= now())))
    for run in expired:
        message = "Run deadline expired or the server was interrupted. No automatic retry was made."
        changed = db.execute(update(models.TailoringRun).where(models.TailoringRun.id == run.id,
            models.TailoringRun.state.in_(["pending", "running"]), models.TailoringRun.deadline_at <= now())
            .values(state="interrupted", active_key=None, finished_at=now(), error=message).execution_options(synchronize_session=False))
        if changed.rowcount:
            db.execute(update(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run.id, models.TailoringStageAttempt.state == "running").values(state="interrupted", finished_at=now(), error=message))
    if expired:
        db.commit()


def profile_id(db):
    profile = profile_service.get_active_profile(db)
    return profile.id if profile else None


def scoped_run(db, run_id):
    run = db.get(models.TailoringRun, run_id)
    if not run or run.profile_id != profile_id(db):
        raise HTTPException(404, "Generation run not found for this profile.")
    return run


def start(db, job, request, parent_id=None, document_kind="resume"):
    expire_runs(db)
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    pid = profile_id(db)
    fingerprint = digest({"request": request.model_dump(), "parent_run_id": parent_id})
    old = db.scalar(select(models.TailoringRun).where(models.TailoringRun.job_id == job.id,
        models.TailoringRun.profile_id == pid, models.TailoringRun.request_key == request.request_key))
    if old:
        if old.request_hash != fingerprint:
            raise HTTPException(409, "This request key belongs to different inputs.")
        return old.id, False
    snapshot = require_capture(db, job, request)
    if document_kind == "cover_letter":
        from app.services.cover_letters import extend_snapshot
        snapshot = extend_snapshot(db, snapshot, request.options)
    parent = scoped_run(db, parent_id) if parent_id else None
    if parent:
        if parent.job_id != job.id or parent.state not in {"failed", "interrupted"}:
            raise HTTPException(409, "Only a failed or interrupted run for this job can be retried.")
        if parent.input_hash != digest(snapshot):
            raise HTTPException(409, "Frozen inputs changed. Start a new generation instead of retrying this run.")
        snapshot = copy.deepcopy(parent.snapshot)
    key = f"{pid}:{job.id}:{document_kind}"
    if db.scalar(select(models.TailoringRun.id).where(models.TailoringRun.active_key == key)):
        raise HTTPException(409, "A resume run is already active for this job. Open its progress instead.")
    run = models.TailoringRun(job_id=job.id, profile_id=pid, source_id=snapshot["source_id"],
        parent_run_id=parent_id, request_key=request.request_key, request_hash=fingerprint,
        input_hash=digest(snapshot), snapshot=snapshot, state="pending", active_key=key,
        created_at=now(),
        deadline_at=now() + timedelta(seconds=snapshot["limits"]["run_seconds"]))
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another generation request won the save. Refresh progress before retrying.") from None
    return run.id, True


def stage_input(snapshot, stage, accepted, repair=None):
    data = {"job": snapshot["job"], "approved_evidence": snapshot["projection"],
            "presentation": {"section_order": ["Education", "Technical Skills", "Experience", "Projects"], "target_pages": 1},
            "prior_outputs": accepted, "stage": stage, "repair": repair,
            "dependencies_hash": digest({"input": digest(snapshot), "stage": stage, "prior": accepted})}
    if generation_version(snapshot) >= 2:
        projection = snapshot["projection"]
        data["contract"] = {
            "composition_version": 3 if generation_version(snapshot) >= 5 else 2 if generation_version(snapshot) >= 4 else 1,
            "critique_targets": ["draft", "skills", *[f"bullets.{b['id']}" for b in accepted.get("select", {}).get("bullets", [])]],
            "claim_ids": [c["id"] for c in projection["claims"]],
            "skill_source_ids": [c["id"] for key in ("technology_catalog", "skill_groups") for c in projection[key]],
            "overlap_policy": "At most one bullet per overlap group. Prefer one representative; permitted complementary claims may share that bullet up to 45 words.",
            "lineage_policy": "New bullet IDs require explicit parents and accepted critique issue links; retire every replaced parent.",
        }
        if generation_version(snapshot) >= 5:
            from app.services.resume_v5 import POLICY
            data['contract']['content_budget'] = dict(POLICY)
        if stage == "revise":
            from app.services.resume_composition import revision_seed
            data["contract"]["revision_seed"] = revision_seed(data)
    return data


def lock_live(db, run_id):
    claimed = db.execute(update(models.TailoringRun).where(models.TailoringRun.id == run_id,
        models.TailoringRun.state == "running", models.TailoringRun.deadline_at > now()).values(state="running").execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        raise ProviderFailure("Run is no longer active; late output was discarded.")
    run = db.get(models.TailoringRun, run_id)
    source = db.get(models.TailoringSourceVersion, run.source_id)
    if not source or tailoring_source_service.source_status(db, source) == "revoked":
        raise ProviderFailure("The source bundle was revoked. Activate approved sources before starting a new run.")
    return run


def fail(engine, run_id, message):
    with Session(engine) as db:
        result = db.execute(update(models.TailoringRun).where(models.TailoringRun.id == run_id,
            models.TailoringRun.state.in_(["pending", "running"])).values(state="failed", active_key=None, error=message, finished_at=now()))
        if result.rowcount:
            db.execute(update(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run_id,
                models.TailoringStageAttempt.state == "running").values(state="failed", error=message, finished_at=now()))
        db.commit()


def execute(engine, run_id):
    accepted = {}
    try:
        with Session(engine) as db:
            claimed = db.execute(update(models.TailoringRun).where(models.TailoringRun.id == run_id,
                models.TailoringRun.state == "pending", models.TailoringRun.deadline_at > now()).values(state="running"))
            if claimed.rowcount != 1:
                return
            run = db.get(models.TailoringRun, run_id)
            snapshot, parent_id = copy.deepcopy(run.snapshot), run.parent_run_id
            deadline = aware(run.deadline_at)
            db.commit()
        for stage in STAGES:
            base_input = stage_input(snapshot, stage, accepted)
            # Reuse only revalidated checkpoints with the exact dependency hash.
            reused = None
            if parent_id:
                with Session(engine) as db:
                    parent_stage = db.scalar(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == parent_id,
                        models.TailoringStageAttempt.stage == stage, models.TailoringStageAttempt.state == "passed").order_by(models.TailoringStageAttempt.attempt.desc()))
                    if parent_stage and parent_stage.input_data.get("dependencies_hash") == base_input["dependencies_hash"]:
                        candidate = output_models(snapshot)[stage].model_validate(parent_stage.output_data)
                        if validate_stage(stage, candidate, snapshot, accepted)["valid"]:
                            reused = (candidate, parent_stage.id)
            repair = None
            for attempt_number in (1, 2):
                data = stage_input(snapshot, stage, accepted, repair)
                output_model = output_models(snapshot)[stage]
                from app.services.resume_composition import plan_model
                wire_model = plan_model(output_model, data)
                payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                # Bytes are a conservative token bound; reserve space for schema/output.
                bound = len(payload.encode()) + len(system_for(stage, generation_version(snapshot)).encode()) + len(json.dumps(wire_model.model_json_schema()).encode()) + snapshot["limits"]["output_tokens"]
                if bound > snapshot["limits"]["context_tokens"]:
                    raise ProviderFailure("This stage exceeds the configured context budget. Sources and outputs were not truncated.")
                timeout = min(snapshot["limits"]["attempt_seconds"], (deadline - now()).total_seconds())
                if timeout <= 0:
                    raise ProviderFailure("Overall generation deadline exceeded. Saved checkpoints remain available.")
                with Session(engine) as db:
                    lock_live(db, run_id)
                    attempt = models.TailoringStageAttempt(run_id=run_id, stage=stage, attempt=attempt_number,
                        state="running", input_data=data, input_hash=digest(data), prompt_version=prompt_versions(snapshot)[stage], started_at=now())
                    db.add(attempt); db.commit(); attempt_id = attempt.id
                output, metadata, error, report = None, {}, None, None
                repairable = True
                try:
                    if reused:
                        output, metadata = reused[0], {"reused_from_attempt": reused[1], "provider_call": False}
                    else:
                        output, metadata = ai_service.get_tailoring_output(output_model, system_for(stage, generation_version(snapshot)), payload,
                            model=snapshot["model"], timeout=timeout)
                    output = output_model.model_validate(output)
                    report = validate_stage(stage, output, snapshot, accepted)
                    if not report["valid"]:
                        error = "Stage validation failed. See the recorded findings."
                except ValidationError:
                    output = None
                    error = "Output did not match the required stage schema."
                    report = {"valid": False, "blocking_issues": [error], "validator_version": f"resume-v{generation_version(snapshot)}"}
                except ProviderFailure as exc:
                    error, repairable = exc.safe_message, exc.repairable
                with Session(engine) as db:
                    lock_live(db, run_id)
                    attempt = db.get(models.TailoringStageAttempt, attempt_id)
                    attempt.output_data = output.model_dump(mode="json") if output is not None else None
                    attempt.output_hash = digest(attempt.output_data) if attempt.output_data is not None else None
                    attempt.validation, attempt.provider_metadata = report, metadata
                    attempt.state, attempt.error, attempt.finished_at = ("failed" if error else "passed"), error, now()
                    db.commit()
                if not error:
                    accepted[stage] = output.model_dump(mode="json")
                    break
                if not repairable or attempt_number == 2:
                    raise ProviderFailure(error)
                repair = {"findings": report["blocking_issues"] if report else [error],
                          "previous_output": output.model_dump(mode="json") if output is not None else None}
            else:
                raise ProviderFailure("Stage did not finish successfully.")
        final = output_models(snapshot)["polish"].model_validate(accepted["polish"]).draft
        report = accuracy_report(final, snapshot, accepted)
        if not report["valid"]:
            raise ProviderFailure("Final evidence validation failed; no successful revision was created.")
        content = assemble_content(final, snapshot)
        with Session(engine) as db:
            run = lock_live(db, run_id)
            db.add(models.TailoredRevision(run_id=run_id, content=content, content_hash=digest(content), plain_text=plain_text(content, snapshot), validation=report))
            run.state, run.active_key, run.finished_at = "completed", None, now()
            db.commit()
    except ProviderFailure as exc:
        fail(engine, run_id, exc.safe_message)
    except Exception:
        # No raw input, output, credential or provider exception reaches logs.
        fail(engine, run_id, "Generation stopped unexpectedly. Saved checkpoints are preserved; review before retrying.")


def run_view(db, run):
    attempts = list(db.scalars(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run.id)
        .order_by(models.TailoringStageAttempt.started_at, models.TailoringStageAttempt.stage, models.TailoringStageAttempt.attempt)))
    revision = db.scalar(select(models.TailoredRevision).where(models.TailoredRevision.run_id == run.id))
    job = db.get(models.Job, run.job_id)
    state = db.get(models.TailoringProfileState, run.profile_id)
    source_changed = not state or state.active_source_id != run.source_id or any(run.snapshot["job"][key] != getattr(job, key) for key in ("company", "role_title", "source_content"))
    return {"id": run.id, "job_id": run.job_id, "state": run.state, "parent_run_id": run.parent_run_id,
        "input_hash": run.input_hash, "source_changed": source_changed, "error": run.error,
        "created_at": run.created_at, "deadline_at": run.deadline_at,
        "stages": [{"id": a.id, "stage": a.stage, "attempt": a.attempt, "state": a.state,
            "output": a.output_data, "validation": a.validation, "metadata": a.provider_metadata,
            "error": a.error, "started_at": a.started_at, "finished_at": a.finished_at} for a in attempts],
        "revision": {"id": revision.id, "content": revision.content, "content_hash": revision.content_hash,
            "plain_text": revision.plain_text, "validation": revision.validation} if revision else None,
        "evidence": run.snapshot["projection"]["claims"] if revision else []}


def workspace(db, job, document_kind="resume"):
    expire_runs(db)
    readiness = capture(db, job)
    readiness.pop("snapshot")
    runs = list(db.scalars(select(models.TailoringRun).where(models.TailoringRun.job_id == job.id,
        models.TailoringRun.profile_id == profile_id(db)).order_by(models.TailoringRun.created_at.desc(), models.TailoringRun.id.desc())))
    return {"readiness": readiness, "runs": [{"id": r.id, "state": r.state, "created_at": r.created_at} for r in runs
        if r.snapshot.get("document_kind", "resume") == document_kind]}
