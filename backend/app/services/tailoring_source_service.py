"""Import/activation only. This module never generates or compiles a document."""
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.tailoring_schemas import ActivateSource, SourceImport
from app.services import profile_service
from app.services.tailoring_source_validation import SourceError, canonical, validate_bundle


def active_profile(db: Session):
    profile = profile_service.get_active_profile(db)
    if not profile:
        raise HTTPException(409, "Create a base profile before importing tailoring sources.")
    return profile


def get_source(db: Session, source_id: str):
    profile = active_profile(db)
    source = db.get(models.TailoringSourceVersion, source_id)
    if not source or source.profile_id != profile.id:
        raise HTTPException(404, "Source version not found for this profile.")
    return source


def state_for(db: Session, profile_id: str):
    return db.get(models.TailoringProfileState, profile_id)


def events_for(db: Session, source_id: str):
    return list(db.scalars(select(models.TailoringSourceEvent).where(
        models.TailoringSourceEvent.source_id == source_id).order_by(models.TailoringSourceEvent.sequence)))


def source_status(db: Session, source):
    events = events_for(db, source.id)
    return events[-1].action if events else "pending"


def summary(db: Session, source):
    return {"id": source.id, "profile_id": source.profile_id, "bank_version": source.bank_version,
            "bundle_hash": source.bundle_hash, "status": source_status(db, source),
            "eligible_count": len(source.validation["eligible_claim_ids"]),
            "excluded_count": len(source.validation["excluded_claim_ids"]),
            "created_at": source.created_at.isoformat()}


def list_sources(db: Session):
    profile = active_profile(db)
    state = state_for(db, profile.id)
    versions = db.scalars(select(models.TailoringSourceVersion).where(
        models.TailoringSourceVersion.profile_id == profile.id).order_by(models.TailoringSourceVersion.created_at.desc(), models.TailoringSourceVersion.id))
    return {"active_id": state.active_source_id if state else None,
            "versions": [summary(db, source) for source in versions]}


def preview(db: Session, source):
    return {**summary(db, source), "validation": source.validation, "claims": source.bank["claims"],
            "identity": source.bank["identity"], "education": source.bank["education"],
            "records": source.bank["records"], "unknowns": source.bank["unknowns"],
            "preferences": source.preferences, "template_hash": source.hashes["template_tex"],
            "style_hash": source.hashes["style_guide"], "template_tex": source.template_tex,
            "style_guide": source.style_guide, "approval": source.bank["approval"],
            "events": [{"action": e.action, "sequence": e.sequence, "created_at": e.created_at.isoformat(),
                        "content_hash": e.content_hash} for e in events_for(db, source.id)]}


def validate_stored(source):
    """Recompute trust-bearing content, including for restore and future generation."""
    payload = SourceImport(**{key: getattr(source, key) for key in SourceImport.model_fields})
    bank, preferences, projection, report, hashes, bundle_hash = validate_bundle(payload)
    expected = {"bank": bank.model_dump(), "preferences": preferences.model_dump(by_alias=True),
                "projection": projection.model_dump(), "hashes": hashes}
    for key, value in expected.items():
        if canonical(getattr(source, key)) != canonical(value):
            raise SourceError("Stored source integrity check failed; import a new validated version.")
    if source.bundle_hash != bundle_hash or source.bank_version != bank.bank_version:
        raise SourceError("Stored source hash/version does not match its contents.")
    # Freshness warnings are time-dependent; the approved claim selection is not.
    for key in ("eligible_claim_ids", "excluded_claim_ids", "validator_version", "status"):
        if source.validation.get(key) != report.model_dump()[key]:
            raise SourceError("Stored validation report does not match its contents.")
    return bank, report


def import_source(db: Session, payload: SourceImport):
    profile = active_profile(db)
    try:
        bank, preferences, projection, report, hashes, bundle_hash = validate_bundle(payload)
    except SourceError as exc:
        raise HTTPException(422, str(exc)) from None
    query = select(models.TailoringSourceVersion).where(models.TailoringSourceVersion.profile_id == profile.id,
                                                        models.TailoringSourceVersion.bundle_hash == bundle_hash)
    existing = db.scalar(query)
    if existing:
        return existing, False
    prior_versions = db.scalars(select(models.TailoringSourceVersion).where(
        models.TailoringSourceVersion.profile_id == profile.id,
        models.TailoringSourceVersion.bank_version == bank.bank_version))
    if any(old.hashes["bank_markdown"] != hashes["bank_markdown"] for old in prior_versions):
        raise HTTPException(409, "Bank content changed without a new bank version. Create and approve a new version.")
    source = models.TailoringSourceVersion(profile_id=profile.id, bank_version=bank.bank_version,
        bundle_hash=bundle_hash, **payload.model_dump(), bank=bank.model_dump(),
        preferences=preferences.model_dump(by_alias=True), projection=projection.model_dump(),
        validation=report.model_dump(), hashes=hashes)
    db.add(source)
    if not state_for(db, profile.id):
        db.add(models.TailoringProfileState(profile_id=profile.id, revision=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(query)
        if existing:
            return existing, False
        raise HTTPException(409, "Sources changed concurrently; reload and retry import.") from None
    db.refresh(source)
    return source, True


def append_event(db, source, action):
    events = events_for(db, source.id)
    db.add(models.TailoringSourceEvent(source_id=source.id, sequence=len(events) + 1,
                                      action=action, content_hash=source.bundle_hash))


def change_activation(db: Session, source, request: ActivateSource, revoke=False):
    if request.expected_hash != source.bundle_hash:
        raise HTTPException(409, "Source changed since preview; review it again.")
    try:
        bank, report = validate_stored(source)
    except SourceError as exc:
        raise HTTPException(409, str(exc)) from None
    state = state_for(db, source.profile_id)
    if not state or state.active_source_id != request.expected_active_id:
        raise HTTPException(409, "Active source changed; reload before confirming.")
    current_status = source_status(db, source)
    if revoke and current_status == "revoked":
        return source
    if not revoke:
        if current_status == "revoked":
            raise HTTPException(409, "Revoked source cannot be activated. Import a new approved version.")
        if bank.approval.status not in {"approved", "approved_with_exclusions"} or not report.eligible_claim_ids:
            raise HTTPException(409, "An approved bank with eligible claims is required.")
        if state.active_source_id == source.id:
            return source
    old_id = state.active_source_id
    new_id = (None if old_id == source.id else old_id) if revoke else source.id
    # Compare-and-swap serializes competing activations without changing source rows.
    result = db.execute(update(models.TailoringProfileState).where(
        models.TailoringProfileState.profile_id == source.profile_id,
        models.TailoringProfileState.revision == state.revision).values(
            active_source_id=new_id, revision=state.revision + 1), execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Source activation changed concurrently; reload.")
    if not revoke and old_id:
        append_event(db, db.get(models.TailoringSourceVersion, old_id), "superseded")
    append_event(db, source, "revoked" if revoke else "active")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Source activation changed concurrently; reload.") from None
    return source


def active_projection(db: Session):
    profile = active_profile(db)
    state = state_for(db, profile.id)
    if not state or not state.active_source_id:
        raise HTTPException(409, "Activate a validated source version first.")
    source = get_source(db, state.active_source_id)
    try:
        bank, _ = validate_stored(source)
    except SourceError as exc:
        raise HTTPException(409, str(exc)) from None
    if source_status(db, source) != "active" or bank.approval.status not in {"approved", "approved_with_exclusions"}:
        raise HTTPException(409, "Source is not active and approved.")
    return source.projection
