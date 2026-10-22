"""Deterministic manual revision validation and comparisons. No model calls."""
import copy
import re
from fastapi import HTTPException
from app.review_schemas import EditedDraft, ResumeEdit
from app.services.intake_preferences import digest
from app.services.resume_validation import validate_draft, assemble_content, plain_text

VERSION = "resume-review-v1"


def editable(content):
    return {"bullets": copy.deepcopy(content["draft"]["bullets"]), "skills": copy.deepcopy(content["draft"]["skills"]),
            "project_order": [r["id"] for r in content["records"] if r["kind"] == "project"]}


def differences(before, after):
    changes = []
    old = {b["id"]: b for b in before["draft"]["bullets"]}
    new = {b["id"]: b for b in after["draft"]["bullets"]}
    for bid in dict.fromkeys([*old, *new]):
        if old.get(bid) != new.get(bid):
            changes.append({"field": f"bullets.{bid}", "kind": "added" if bid not in old else "removed" if bid not in new else "changed",
                            "before": old.get(bid), "after": new.get(bid)})
    for name, a, b in (("bullet_order", list(old), list(new)),
                       ("skills", before["draft"]["skills"], after["draft"]["skills"]),
                       ("project_order", editable(before)["project_order"], editable(after)["project_order"]),
                       ("unmet_requirements", before["draft"]["unmet_requirement_ids"], after["draft"]["unmet_requirement_ids"])):
        if a != b:
            changes.append({"field": name, "kind": "changed", "before": a, "after": b})
    return changes


def build_content(edit: ResumeEdit, baseline, snapshot):
    requirements = copy.deepcopy(baseline["draft"]["requirements"])
    covered = {rid for b in edit.bullets for rid in b.requirement_ids}
    draft = EditedDraft(requirements=requirements, bullets=edit.bullets, skills=edit.skills,
        unmet_requirement_ids=[r["id"] for r in requirements if r["id"] not in covered], change_summary=[])
    content = assemble_content(draft, snapshot)
    projects = {r["id"] for r in content["records"] if r["kind"] == "project"}
    if len(edit.project_order) != len(set(edit.project_order)) or set(edit.project_order) != projects:
        raise HTTPException(422, "Project order must contain each selected approved project exactly once.")
    positions = {rid: index for index, rid in enumerate(edit.project_order)}
    content["records"] = [r for r in content["records"] if r["kind"] == "employment"] + sorted(
        (r for r in content["records"] if r["kind"] == "project"), key=lambda r: positions[r["id"]])
    changes = differences(baseline, content)
    content["draft"]["change_summary"] = [f"{c['kind'].capitalize()}: {c['field']}" for c in changes[:12]]
    return content


def bullet_identities(contents):
    identities = {}
    for content in contents:
        for bullet in content["draft"]["bullets"]:
            identities.setdefault(bullet["id"], (bullet["record_id"], bullet["evidence_ids"]))
    return identities


def validate_revision(content, snapshot, parent=None, identities=None):
    draft = EditedDraft.model_validate(content["draft"])
    errors = validate_draft(draft, snapshot)
    if not draft.bullets:
        errors.append("Select at least one supported bullet before review.")
    protected = assemble_content(draft, snapshot)
    for field in ("identity", "education", "section_order"):
        if content[field] != protected[field]:
            errors.append(f"Protected {field} differs from the approved source.")
    if sorted(content["records"], key=lambda r: r["id"]) != sorted(protected["records"], key=lambda r: r["id"]):
        errors.append("Protected employment/project metadata differs from the approved source.")
    if [r for r in content["records"] if r["kind"] == "employment"] != [r for r in protected["records"] if r["kind"] == "employment"]:
        errors.append("Employment must remain reverse chronological.")
    identities = identities if identities is not None else bullet_identities([parent] if parent else [])
    for bullet in draft.bullets:
        original = identities.get(bullet.id)
        if original and original != (bullet.record_id, bullet.evidence_ids):
            errors.append(f"Bullet {bullet.id} changes its source identity; add approved content as a new bullet instead.")
    issues = []
    for message in errors:
        match = re.match(r"Bullet (\S+) ", message)
        issues.append({"field_path": f"bullets.{match.group(1)}" if match else "draft", "message": message})
    return {"validator_version": VERSION, "valid": not errors, "issues": issues,
            "validated_content_hash": digest(content), "input_hash": digest(snapshot),
            "unmet_requirement_ids": draft.unmet_requirement_ids, "human_review_required": True}


def check_stored_edit(row, baseline, snapshot, parent, identities):
    expected = build_content(ResumeEdit.model_validate(editable(row["content"])), baseline, snapshot)
    if row["content"] != expected or row["content_hash"] != digest(expected) or row["plain_text"] != plain_text(expected):
        raise ValueError("Edited resume content or derived text was altered")
    if row["validation"] != validate_revision(expected, snapshot, parent, identities):
        raise ValueError("Edited resume validation was altered")
