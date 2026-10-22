"""Validate review history before restore; never infer approval for legacy drafts."""
from app.services.intake_preferences import digest
from app.services.resume_review_validation import VERSION, validate_revision, check_stored_edit, editable, bullet_identities


def validate_review_tables(tables):
    baselines = {r["id"]: r for r in tables["tailored_revisions"]}
    runs = {r["id"]: r for r in tables["tailoring_runs"]}
    ordered = []
    indexed = dict(baselines)
    reports = {}
    owners = {rid: rid for rid in baselines}
    for baseline in baselines.values():
        snapshot = runs[baseline["run_id"]]["snapshot"]
        reports[baseline["id"]] = validate_revision(baseline["content"], snapshot)
        previous = baseline
        previous_contents = [baseline["content"]]
        rows = sorted((r for r in tables["resume_edit_revisions"] if r["baseline_id"] == baseline["id"]), key=lambda r: r["sequence"])
        for number, row in enumerate(rows, 1):
            if row["id"] in indexed or row["sequence"] != number or row["parent_id"] != (previous["id"] if number > 1 else None):
                raise ValueError("Invalid manual revision chain")
            restored = indexed.get(row["restored_from_id"])
            if row["origin"] not in {"edited", "restored"} or (row["origin"] == "restored") != bool(row["restored_from_id"]):
                raise ValueError("Invalid revision origin")
            if row["origin"] == "restored" and (not restored or owners[restored["id"]] != baseline["id"] or editable(restored["content"]) != editable(row["content"])):
                raise ValueError("Invalid restored revision reference")
            payload = {"request_key": row["request_key"], "expected_revision_id": previous["id"]}
            payload.update({"revision_id": row["restored_from_id"]} if row["origin"] == "restored" else {"edit": editable(row["content"])})
            if row["request_hash"] != digest({"action": "restore" if row["origin"] == "restored" else "edit", "payload": payload}):
                raise ValueError("Invalid edit request identity")
            check_stored_edit(row, baseline["content"], snapshot, previous["content"], bullet_identities(previous_contents))
            reports[row["id"]] = row["validation"]
            indexed[row["id"]] = row
            owners[row["id"]] = baseline["id"]
            ordered.append(row)
            previous = row
            previous_contents.append(row["content"])
    if len(ordered) != len(tables["resume_edit_revisions"]):
        raise ValueError("Manual revision has no generated baseline")
    tables["resume_edit_revisions"] = ordered
    for approval in tables["resume_review_approvals"]:
        row = indexed[approval["revision_id"]]
        baseline = baselines[approval["baseline_id"]]
        report = reports[row["id"]]
        if owners[row["id"]] != baseline["id"] or approval["edit_revision_id"] != (None if row["id"] == baseline["id"] else row["id"]):
            raise ValueError("Approval belongs to a different resume")
        if not report["valid"] or approval["content_hash"] != digest(row["content"]) or approval["validation_hash"] != digest(report) or approval["validator_version"] != VERSION or approval["input_hash"] != runs[baseline["run_id"]]["input_hash"]:
            raise ValueError("Approval does not match a valid exact revision")
