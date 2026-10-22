"""Validate immutable artifact bytes before any destructive restore."""
from types import SimpleNamespace
from app.services import resume_rendering as rendering


def validate_render_tables(tables):
    baselines = {r["id"]: r for r in tables["tailored_revisions"]}
    revisions = {**baselines, **{r["id"]: r for r in tables["resume_edit_revisions"]}}
    runs = {r["id"]: r for r in tables["tailoring_runs"]}
    sources = {r["id"]: r for r in tables["tailoring_source_versions"]}
    renders = {r["id"]: r for r in tables["resume_renders"]}
    receipts = {r["id"]: r for r in tables["resume_preview_receipts"]}
    reviews = {r["id"]: r for r in tables["resume_review_approvals"]}
    for row in renders.values():
        baseline, revision = baselines[row["baseline_id"]], revisions[row["revision_id"]]
        expected_edit = None if revision["id"] == baseline["id"] else revision["id"]
        if row["edit_revision_id"] != expected_edit or revision.get("baseline_id", baseline["id"]) != baseline["id"]:
            raise ValueError("Render revision reference mismatch")
        from app.services.resume_review import validation_for
        from app.services.intake_preferences import digest
        edits = [SimpleNamespace(**e) for e in tables["resume_edit_revisions"] if e["baseline_id"] == baseline["id"]]
        run = SimpleNamespace(**runs[baseline["run_id"]])
        if run.snapshot.get("document_kind", "resume") != "resume":
            raise ValueError("PDF render belongs to a non-resume document")
        validation = validation_for(SimpleNamespace(**revision), SimpleNamespace(**baseline), edits, run)
        if not validation["valid"] or row["validation_hash"] != digest(validation):
            raise ValueError("Render content validation mismatch")
        rendering.verify_bundle(SimpleNamespace(**row), revision["content"], run.snapshot, sources[run.source_id]["bank"])
    for receipt in receipts.values():
        if receipt["manifest_hash"] != renders[receipt["render_id"]]["manifest_hash"]:
            raise ValueError("Preview manifest mismatch")
    for approval in tables["resume_export_approvals"]:
        render, receipt, review = renders[approval["render_id"]], receipts[approval["preview_receipt_id"]], reviews[approval["content_approval_id"]]
        if not render["bundle"]["validation"]["valid"] or receipt["render_id"] != render["id"] or approval["manifest_hash"] != render["manifest_hash"]:
            raise ValueError("Invalid final approval")
        if review["revision_id"] != render["revision_id"] or any(review[k] != render[k] for k in ("content_hash", "validation_hash", "input_hash")):
            raise ValueError("Final approval content mismatch")
