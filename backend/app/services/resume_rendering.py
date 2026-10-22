"""Frozen exports: compilation is explicit; reads and downloads never regenerate."""
import base64
import hashlib
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import models
from app.services import resume_review as review, resume_layout as layout, resume_compiler
from app.services.intake_preferences import digest


def sha(value):
    return hashlib.sha256(value).hexdigest()


def render_key(revision_id, content_hash, validation_hash, input_hash, engine):
    return digest([revision_id, content_hash, validation_hash, input_hash, layout.VERSION, layout.TEMPLATE_HASH, engine])


def decode_bundle(bundle):
    if set(bundle["files"]) != {"pdf", "tex", "txt"}:
        raise ValueError("Incomplete artifact bundle")
    files = {key: base64.b64decode(value, validate=True) for key, value in bundle["files"].items()}
    if any(len(value) > resume_compiler.MAX_PDF_BYTES for value in files.values()):
        raise ValueError("Oversized artifact")
    if bundle["hashes"] != {k: sha(v) for k, v in files.items()}:
        raise ValueError("Artifact checksum mismatch")
    return files


def manifest(bundle):
    return digest({k: v for k, v in bundle.items() if k != "files"})


def verify_bundle(row, content, snapshot, bank):
    bundle = row.bundle
    if bundle["renderer_version"] != layout.VERSION or bundle["template_hash"] != layout.TEMPLATE_HASH:
        raise ValueError("Unsupported historical renderer")
    if row.manifest_hash != manifest(bundle) or row.content_hash != digest(content):
        raise ValueError("Render manifest mismatch")
    if row.input_hash != digest(snapshot) or row.render_key != render_key(row.revision_id, row.content_hash, row.validation_hash, row.input_hash, bundle["engine"]):
        raise ValueError("Render input mismatch")
    metadata = layout.presentation_metadata(content, snapshot, bank)
    if bundle["presentation_metadata"] != metadata:
        raise ValueError("Project presentation metadata mismatch")
    doc = layout.document(content, snapshot, metadata)
    tex, text = layout.exports(doc)
    files = decode_bundle(bundle)
    if bundle["document"] != doc or files["tex"] != tex.encode() or files["txt"] != text.encode():
        raise ValueError("Artifact content mismatch")
    if bundle["source_template_hash"] != digest(snapshot["template_tex"]) or bundle["source_style_hash"] != digest(snapshot["style_guide"]):
        raise ValueError("Artifact source mismatch")
    report = resume_compiler.inspect_pdf(files["pdf"], text, bundle["compiler_warnings"])
    if report != bundle["validation"]:
        raise ValueError("Artifact layout validation mismatch")
    return files


def get_render(db, baseline_id, render_id):
    baseline, run = review.baseline_for(db, baseline_id)
    row = db.get(models.ResumeRender, render_id)
    if not row or row.baseline_id != baseline.id:
        raise HTTPException(404, "Resume artifact not found.")
    selected = review.selected_revision(baseline, review.revisions(db, baseline), row.revision_id)
    try:
        source = db.get(models.TailoringSourceVersion, run.source_id)
        files = verify_bundle(row, selected.content, run.snapshot, source.bank)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(409, "Stored artifact failed integrity checks. Restore an intact backup; historical bytes will not be replaced.") from None
    return row, files


def details(db, row):
    approval = db.scalar(select(models.ResumeExportApproval).where(models.ResumeExportApproval.render_id == row.id))
    return {"id": row.id, "revision_id": row.revision_id, "manifest_hash": row.manifest_hash, "content_hash": row.content_hash,
            "created_at": row.created_at, "renderer_version": row.bundle["renderer_version"], "engine": row.bundle["engine"],
            "validation": row.bundle["validation"], "approved_at": approval.approved_at if approval else None,
            "hashes": row.bundle["hashes"]}


def history(db, baseline_id, revision_id):
    baseline, _ = review.baseline_for(db, baseline_id)
    review.selected_revision(baseline, review.revisions(db, baseline), revision_id)
    rows = db.scalars(select(models.ResumeRender).where(models.ResumeRender.baseline_id == baseline_id, models.ResumeRender.revision_id == revision_id).order_by(models.ResumeRender.created_at.desc()))
    return [details(db, row) for row in rows]


def create(db, baseline_id, payload):
    workspace = review.view(db, baseline_id, payload.revision_id)
    selected = workspace["revision"]
    if (payload.content_hash, payload.validation_hash, payload.input_hash) != (selected["content_hash"], selected["validation_hash"], workspace["input_hash"]):
        raise HTTPException(409, "Saved revision changed. Refresh before rendering.")
    if not workspace["approval_eligible"]:
        raise HTTPException(409, workspace["source_problem"] or "Only the current valid saved revision can be rendered. Restore older content as a new revision first.")
    _, run = review.baseline_for(db, baseline_id)
    snapshot = run.snapshot
    try:
        executable, engine = resume_compiler.compiler()
        key = render_key(payload.revision_id, payload.content_hash, payload.validation_hash, payload.input_hash, engine)
        existing = db.scalar(select(models.ResumeRender).where(models.ResumeRender.render_key == key))
        if existing:
            get_render(db, baseline_id, existing.id)
            return details(db, existing)
        source = db.get(models.TailoringSourceVersion, run.source_id)
        metadata = layout.presentation_metadata(selected["content"], snapshot, source.bank)
        doc = layout.document(selected["content"], snapshot, metadata)
        tex, text = layout.exports(doc)
        db.rollback()  # Compiler never holds a database transaction/lock.
        pdf, warnings = resume_compiler.compile_pdf(tex, executable)
        validation = resume_compiler.inspect_pdf(pdf, text, warnings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    files = {"pdf": pdf, "tex": tex.encode(), "txt": text.encode()}
    bundle = {"renderer_version": layout.VERSION, "template_hash": layout.TEMPLATE_HASH, "engine": engine,
              "source_template_hash": digest(snapshot["template_tex"]), "source_style_hash": digest(snapshot["style_guide"]),
              "document": doc, "presentation_metadata": metadata, "files": {k: base64.b64encode(v).decode("ascii") for k, v in files.items()},
              "hashes": {k: sha(v) for k, v in files.items()}, "validation": validation, "compiler_warnings": warnings}
    # Keep an immutable preview even if another tab saved while it rendered. Final approval rechecks the head.
    row = models.ResumeRender(baseline_id=baseline_id, revision_id=payload.revision_id,
        edit_revision_id=payload.revision_id if payload.revision_id != baseline_id else None,
        content_hash=payload.content_hash, validation_hash=payload.validation_hash, input_hash=payload.input_hash,
        render_key=key, manifest_hash=manifest(bundle), bundle=bundle)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.scalar(select(models.ResumeRender).where(models.ResumeRender.render_key == key))
        if not row:
            raise HTTPException(409, "Resume history changed during rendering. Refresh and retry.") from None
    return details(db, row)


def preview(db, baseline_id, render_id):
    row, files = get_render(db, baseline_id, render_id)
    receipt = models.ResumePreviewReceipt(render_id=row.id, manifest_hash=row.manifest_hash)
    db.add(receipt); db.commit()
    import pymupdf
    with pymupdf.open(stream=files["pdf"], filetype="pdf") as document:
        pages = [base64.b64encode(page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).tobytes("png")).decode("ascii") for page in document]
    return {"preview_receipt_id": receipt.id, "manifest_hash": row.manifest_hash, "pdf_base64": base64.b64encode(files["pdf"]).decode("ascii"), "page_images": pages}


def approve(db, baseline_id, render_id, payload):
    review.baseline_for(db, baseline_id, lock=True)
    row, _ = get_render(db, baseline_id, render_id)
    workspace = review.view(db, baseline_id, row.revision_id)
    receipt = db.get(models.ResumePreviewReceipt, payload.preview_receipt_id)
    if not receipt or receipt.render_id != row.id or receipt.manifest_hash != row.manifest_hash or payload.manifest_hash != row.manifest_hash:
        raise HTTPException(409, "Open this exact PDF preview before final approval.")
    if not row.bundle["validation"]["valid"]:
        raise HTTPException(409, "Resolve page-fit and rendering issues before final approval.")
    if not workspace["approved_current"] or row.validation_hash != workspace["revision"]["validation_hash"]:
        raise HTTPException(409, workspace["source_problem"] or "Review the current saved content before final approval. A different revision cannot inherit approval.")
    existing = db.scalar(select(models.ResumeExportApproval).where(models.ResumeExportApproval.render_id == row.id))
    if not existing:
        db.add(models.ResumeExportApproval(render_id=row.id, content_approval_id=workspace["approval"]["id"],
            preview_receipt_id=receipt.id, manifest_hash=row.manifest_hash))
        db.commit()
    return details(db, row)


def download(db, baseline_id, render_id, format):
    if format not in {"pdf", "tex", "txt"}:
        raise HTTPException(404, "Unknown export format.")
    row, files = get_render(db, baseline_id, render_id)
    approval = db.scalar(select(models.ResumeExportApproval).where(models.ResumeExportApproval.render_id == row.id))
    if not approval or approval.manifest_hash != row.manifest_hash:
        raise HTTPException(409, "Preview and approve this exact artifact before downloading final exports.")
    return files[format], row.bundle["hashes"][format]


def delete_draft(db, baseline_id, render_id):
    review.baseline_for(db, baseline_id, lock=True)
    row = db.get(models.ResumeRender, render_id)
    if not row or row.baseline_id != baseline_id:
        raise HTTPException(404, "Resume artifact not found.")
    if db.scalar(select(models.ResumeExportApproval).where(models.ResumeExportApproval.render_id == row.id)):
        raise HTTPException(409, "Approved historical exports are retained. Only unapproved previews can be removed.")
    db.query(models.ResumePreviewReceipt).filter_by(render_id=row.id).delete()
    db.delete(row); db.commit()
