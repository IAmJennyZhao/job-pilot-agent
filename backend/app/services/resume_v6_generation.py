"""Write once (bounded structural repair), then best-effort advisory review."""
import json
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app import models
from app.services import resume_v6 as policy, resume_generation as runs, ai_service
from app.services.intake_preferences import digest
from app.services.tailoring_provider import ProviderFailure


def complete(db, run):
    """Recover a saved writer checkpoint even when advisory work was interrupted."""
    attempts = list(db.scalars(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run.id,
        models.TailoringStageAttempt.state == 'passed').order_by(models.TailoringStageAttempt.attempt)))
    accepted = {a.stage: a.output_data for a in attempts}
    if 'write' not in accepted:
        return False
    draft = policy.Draft.model_validate(accepted['write'])
    content = policy.assemble(draft, run.snapshot, policy.advisory_for(draft, accepted))
    from app.services.resume_validation import plain_text
    existing = db.scalar(select(models.TailoredRevision).where(models.TailoredRevision.run_id == run.id))
    if not existing:
        db.add(models.TailoredRevision(run_id=run.id, content=content, content_hash=digest(content),
            plain_text=plain_text(content, run.snapshot), validation=policy.report(draft, run.snapshot)))
    run.state, run.active_key, run.error, run.finished_at = 'completed', None, None, runs.now()
    return True


def execute(engine, run_id):
    accepted = {}
    try:
        with Session(engine) as db:
            if db.execute(update(models.TailoringRun).where(models.TailoringRun.id == run_id, models.TailoringRun.state == 'pending')
                          .values(state='running')).rowcount != 1:
                return
            run = db.get(models.TailoringRun, run_id)
            snapshot, deadline, parent_id = run.snapshot, runs.aware(run.deadline_at), run.parent_run_id
            db.commit()
        for stage in policy.STAGES:
            repair = None
            for number in range(1, 3 if stage == 'write' else 2):
                data = policy.stage_input(snapshot, stage, accepted, repair)
                output_model = policy.Draft if stage == 'write' else policy.Advisory
                from app.services.resume_composition import plan_model
                wire_model = plan_model(output_model, data)
                payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
                bound = len(payload.encode()) + len(policy.PROMPTS[stage].encode()) + len(json.dumps(wire_model.model_json_schema()).encode()) + snapshot['limits']['output_tokens']
                timeout = min(snapshot['limits']['attempt_seconds'], (deadline-runs.now()).total_seconds())
                if timeout <= 0 or bound > snapshot['limits']['context_tokens']:
                    raise ProviderFailure('Generation deadline or context budget reached. Saved writing is preserved.')
                with Session(engine) as db:
                    runs.lock_live(db, run_id)
                    attempt = models.TailoringStageAttempt(run_id=run_id, stage=stage, attempt=number, state='running',
                        input_data=data, input_hash=digest(data), prompt_version=f'resume-{stage}-v6', started_at=runs.now())
                    db.add(attempt); db.commit(); aid = attempt.id
                output, metadata, error, report, repairable = None, {}, None, None, True
                try:
                    reused = None
                    if parent_id and stage == 'write':
                        with Session(engine) as db:
                            old = db.scalar(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == parent_id,
                                models.TailoringStageAttempt.stage == 'write', models.TailoringStageAttempt.state == 'passed'))
                            if old and old.input_data == data:
                                reused = (old.output_data, old.id)
                    if reused:
                        output, metadata = output_model.model_validate(reused[0]), {'reused_from_attempt': reused[1], 'provider_call': False}
                    else:
                        output, metadata = ai_service.get_tailoring_output(output_model, policy.PROMPTS[stage], payload, model=snapshot['model'], timeout=timeout)
                    output = output_model.model_validate(output)
                    report = policy.validate_stage(stage, output, snapshot, accepted)
                    if not report['valid']:
                        error = 'Stage validation failed. See the recorded findings.'
                except ValidationError:
                    output = None
                    error = 'Output did not match the stage schema.'
                except ProviderFailure as exc:
                    error, repairable = exc.safe_message, exc.repairable
                with Session(engine) as db:
                    runs.lock_live(db, run_id)
                    attempt = db.get(models.TailoringStageAttempt, aid)
                    attempt.output_data = output.model_dump(mode='json') if output is not None else None
                    attempt.output_hash = digest(attempt.output_data) if attempt.output_data is not None else None
                    attempt.validation, attempt.provider_metadata = report, metadata
                    attempt.state, attempt.error, attempt.finished_at = ('failed' if error else 'passed'), error, runs.now()
                    db.commit()
                if not error:
                    accepted[stage] = output.model_dump(mode='json')
                    break
                if stage == 'review':
                    break  # Advisory output never edits or discards the writer's draft.
                if not repairable or number == 2:
                    raise ProviderFailure(error)
                repair = {'findings': report['blocking_issues'] if report else [error], 'previous_output': output.model_dump() if output else None}
        with Session(engine) as db:
            # Lock state, but permit finishing an already saved draft after the AI deadline.
            changed = db.execute(update(models.TailoringRun).where(models.TailoringRun.id == run_id, models.TailoringRun.state == 'running').values(state='running'))
            if changed.rowcount:
                complete(db, db.get(models.TailoringRun, run_id))
                db.commit()
    except Exception as exc:
        with Session(engine) as db:
            changed = db.execute(update(models.TailoringRun).where(models.TailoringRun.id == run_id, models.TailoringRun.state.in_(['pending', 'running'])).values(state='running'))
            if changed.rowcount:
                db.execute(update(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run_id, models.TailoringStageAttempt.state == 'running')
                    .values(state='interrupted', error='Request interrupted; saved writing is preserved.', finished_at=runs.now()))
                run = db.get(models.TailoringRun, run_id)
                if not complete(db, run):
                    run.state, run.active_key, run.finished_at = 'failed', None, runs.now()
                    run.error = exc.safe_message if isinstance(exc, ProviderFailure) else 'Generation stopped unexpectedly. Saved checkpoints are preserved.'
                db.commit()
