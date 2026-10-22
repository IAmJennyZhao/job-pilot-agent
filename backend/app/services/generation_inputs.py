from fastapi import HTTPException
from app import models, schemas
from app.config import get_settings
from app.intake_schemas import IntakeReview
from app.services import intake_review_service, tailoring_source_service
from app.services.intake_preferences import active_preferences, digest, evaluate
from app.services.resume_validation import PROMPT_VERSIONS
from app.resume_prompts import system_for


def capture(db, job):
    source = active_preferences(db)
    settings = get_settings()
    missing = []
    if not source:
        missing.append("Activate a validated, approved source bundle in Application Assets.")
    if not job.source_content or not job.source_content.strip():
        missing.append("Save the full job description before generating a resume.")
    if not settings.openai_api_key or not settings.openai_api_key.strip() or not settings.openai_model or not settings.openai_model.strip():
        missing.append("Configure OPENAI_API_KEY and OPENAI_MODEL for resume generation.")
    if len(job.source_content or "") > 100000:
        missing.append("Description exceeds the 100,000-character limit; no text will be truncated.")
    prep = intake_review_service.preparation(db, job)
    saved = db.get(models.JobIntakeReview, job.id)
    if saved and not prep["review_stale"]:
        review = IntakeReview.model_validate(saved.review)
    else:
        review = IntakeReview(job=schemas.JobCreate(
            **{key: getattr(job, key) for key in ("company", "role_title", "location", "remote_type", "pay_min", "pay_max", "pay_currency", "pay_period", "source_content")},
            links=[schemas.JobLinkCreate(kind=link.kind, label=link.label, url=link.url) for link in job.links]))
    evaluation = evaluate(db, review)
    snapshot = None
    if source:
        projection = tailoring_source_service.active_projection(db)
        snapshot = {"schema_version": 1, "profile_id": source.profile_id, "source_id": source.id,
            "source_hash": source.bundle_hash, "projection": projection, "projection_hash": digest(projection),
            "identity": source.bank["identity"], "preferences": source.preferences,
            "template_tex": source.template_tex, "style_guide": source.style_guide,
            "source_hashes": source.hashes, "job": {"id": job.id, "company": job.company, "role_title": job.role_title, "source_content": job.source_content},
            "evaluation_hash": evaluation["evaluation_hash"], "model": (settings.openai_model or "").strip(),
            "prompt_versions": PROMPT_VERSIONS, "prompt_hashes": {s: digest(system_for(s)) for s in PROMPT_VERSIONS},
            "limits": {"attempt_seconds": 60, "run_seconds": 300, "output_tokens": 6000, "context_tokens": settings.tailoring_context_tokens}}
        # UTF-8 bytes conservatively bound tokens without guessing an encoding.
        import json
        initial_bytes = len(json.dumps({"projection": projection, "job": snapshot["job"]}, ensure_ascii=False).encode())
        if initial_bytes + 20000 > settings.tailoring_context_tokens:
            missing.append("Complete sources exceed the configured context budget; no evidence will be truncated.")
    return {"ready": not missing, "missing": missing, "input_hash": digest(snapshot) if snapshot else None,
            "description_hash": digest(job.source_content or ""), "description_reviewed": prep["full_description_ready"],
            "source_content": job.source_content or "", "evaluation": evaluation, "snapshot": snapshot}


def require_capture(db, job, request):
    state = capture(db, job)
    if state["missing"]:
        raise HTTPException(422, " ".join(state["missing"]))
    if request.expected_input_hash != state["input_hash"] or request.acknowledged_evaluation_hash != state["evaluation"]["evaluation_hash"]:
        raise HTTPException(409, "Sources, settings or preference checks changed. Refresh and review before generating.")
    if request.reviewed_description_hash != state["description_hash"]:
        raise HTTPException(409, "Review the current full job description before generating.")
    return state["snapshot"]
