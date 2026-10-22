"""Conservative source-preserving checks, never a claim of semantic proof."""
import re
from app.generation_schemas import ResumeDraft, CritiqueReport, RevisedResume, PolishedResume, FactualAccuracyReport

STAGES = ("select", "critique", "revise", "polish")
OUTPUT_MODELS = dict(zip(STAGES, (ResumeDraft, CritiqueReport, RevisedResume, PolishedResume)))
PROMPT_VERSIONS = {stage: f"resume-{stage}-v1" for stage in STAGES}


def fact_tokens(text):
    # Only narrowly equivalent style edits are automatic. Arbitrary paraphrases
    # need review and cannot be accepted merely because an evidence ID exists.
    text = text.casefold().replace("utilized", "used").replace("utilizing", "using")
    text = re.sub(r"\bin order to\b", "to", text)
    text = re.sub(r"\b(successfully|effectively)\b", "", text)
    return re.findall(r"[\w]+(?:[./+#%-][\w]+)*|[%+#]", text, flags=re.UNICODE)


def unique(values, label, errors):
    if len(values) != len(set(values)):
        errors.append(f"Duplicate {label}.")


def validate_draft(draft, snapshot):
    errors = []
    projection = snapshot["projection"]
    claims = {c["id"]: c for c in projection["claims"]}
    records = {r["id"] for r in projection["records"]}
    requirements = {r.id for r in draft.requirements}
    unique([r.id for r in draft.requirements], "requirement IDs", errors)
    unique([b.id for b in draft.bullets], "bullet IDs", errors)
    unique([s.name.casefold() for s in draft.skills], "skills", errors)
    for requirement in draft.requirements:
        if requirement.quote not in snapshot["job"]["source_content"]:
            errors.append(f"Requirement {requirement.id} lacks an exact posting quote.")
    covered = set()
    for bullet in draft.bullets:
        unique(bullet.evidence_ids, "bullet evidence IDs", errors)
        source_claims = [claims.get(cid) for cid in bullet.evidence_ids]
        if bullet.record_id not in records or any(not c or c["record_id"] != bullet.record_id for c in source_claims):
            errors.append(f"Bullet {bullet.id} references unavailable or unrelated record evidence.")
            continue
        if not set(bullet.requirement_ids) <= requirements:
            errors.append(f"Bullet {bullet.id} references an unknown requirement.")
        covered.update(bullet.requirement_ids)
        source_text = " ".join(c["text"] for c in source_claims)
        if fact_tokens(bullet.text) != fact_tokens(source_text):
            errors.append(f"Bullet {bullet.id} changes source facts or uses an unverified paraphrase. Use the cited claim text with wording-only edits; do not remove qualifiers, clauses, metrics or units.")
        if re.search(r"\\(?:input|include|write|begin)|<\s*(?:script|iframe)|https?://", bullet.text, re.I):
            errors.append(f"Bullet {bullet.id} contains executable markup or an external resource.")
    allowed_skills = {}
    for group in projection["skill_groups"]:
        allowed_skills[group["id"]] = {v.casefold() for v in group["values"]}
    for tech in projection["technology_catalog"]:
        allowed_skills[tech["id"]] = {tech["name"].casefold(), *[v.casefold() for v in tech["aliases"]]}
    for skill in draft.skills:
        if any(skill.name.casefold() not in allowed_skills.get(sid, set()) for sid in skill.source_ids):
            errors.append(f"Skill {skill.name} lacks matching approved skill provenance.")
    if set(draft.unmet_requirement_ids) != requirements - covered:
        errors.append("Unmet requirements must equal requirements without selected bullet evidence.")
    return errors


def polish_diff(before, after):
    old = {b.id: b.text for b in before.bullets}
    return [{"bullet_id": b.id, "before": old[b.id], "after": b.text} for b in after.bullets if b.id in old and b.text != old[b.id]]


def validate_stage(stage, output, snapshot, accepted):
    errors = []
    draft = output if stage == "select" else output.draft if stage in {"revise", "polish"} else None
    if draft:
        errors.extend(validate_draft(draft, snapshot))
    if stage == "critique":
        original = ResumeDraft.model_validate(accepted["select"])
        fields = {"draft", "skills", *[f"bullets.{b.id}" for b in original.bullets]}
        claim_ids = {c["id"] for c in snapshot["projection"]["claims"]}
        req_ids = {r.id for r in original.requirements}
        unique([i.issue_id for i in output.issues], "critique issue IDs", errors)
        for issue in output.issues:
            if issue.field_path not in fields or not set(issue.evidence_ids) <= claim_ids or not set(issue.requirement_ids) <= req_ids:
                errors.append(f"Critique {issue.issue_id} has invalid field or evidence references.")
    if stage == "revise":
        original = ResumeDraft.model_validate(accepted["select"])
        critique = CritiqueReport.model_validate(accepted["critique"])
        issues = {i.issue_id: i for i in critique.issues}
        unique([d.issue_id for d in output.decisions], "revision decisions", errors)
        if {d.issue_id for d in output.decisions} != set(issues):
            errors.append("Revision must account for every critique issue exactly once.")
        accepted_fields = set()
        for decision in output.decisions:
            issue = issues.get(decision.issue_id)
            if not issue:
                continue
            if decision.action == "accepted":
                accepted_fields.add(issue.field_path)
                if issue.requires_user_fact_confirmation:
                    errors.append(f"Revision cannot accept {issue.issue_id} without newly approved facts.")
            elif issue.severity == "blocking":
                errors.append(f"Blocking critique {issue.issue_id} remains unresolved.")
        old = {b.id: b for b in original.bullets}
        new = {b.id: b for b in draft.bullets}
        for bid in old.keys() | new.keys():
            if old.get(bid) != new.get(bid) and "draft" not in accepted_fields and f"bullets.{bid}" not in accepted_fields:
                errors.append(f"Bullet {bid} changed without an accepted critique recommendation.")
            if bid in old and bid in new and (old[bid].record_id, old[bid].evidence_ids) != (new[bid].record_id, new[bid].evidence_ids):
                errors.append(f"Bullet {bid} changed its source identity; a new claim needs a new bullet ID.")
        if original.skills != draft.skills and not {"draft", "skills"} & accepted_fields:
            errors.append("Skills changed without an accepted recommendation.")
        if original.requirements != draft.requirements:
            errors.append("Revision must preserve the original requirement mapping.")
    if stage == "polish":
        original = RevisedResume.model_validate(accepted["revise"]).draft
        old, new = original.model_dump(), draft.model_dump()
        for value in (old, new):
            for bullet in value["bullets"]:
                bullet.pop("text")
        if old != new:
            errors.append("Polish changed the selected content, order, provenance, skills or requirement mapping.")
        changes = polish_diff(original, draft)
        if [e.model_dump() for e in output.edits] != changes:
            errors.append("Polish edit log does not match computed changes.")
    return {"valid": not errors, "blocking_issues": errors, "validator_version": "resume-v1"}


def accuracy_report(draft, snapshot, accepted):
    errors = validate_draft(draft, snapshot)
    before = RevisedResume.model_validate(accepted["revise"]).draft
    return FactualAccuracyReport(valid=not errors, blocking_issues=errors,
        supported_claim_ids=sorted({cid for b in draft.bullets for cid in b.evidence_ids}),
        wording_changes=polish_diff(before, draft), unmet_requirement_ids=draft.unmet_requirement_ids).model_dump()


def assemble_content(draft, snapshot):
    selected = {b.record_id for b in draft.bullets}
    records = [r for r in snapshot["projection"]["records"] if r["id"] in selected]
    records.sort(key=lambda r: r.get("start") or "", reverse=True)
    return {"identity": snapshot["identity"], "education": snapshot["projection"]["education"],
            "records": records, "section_order": ["Education", "Technical Skills", "Experience", "Projects"],
            "draft": draft.model_dump()}


def plain_text(content):
    lines = [content["identity"].get("name", ""), "Education"]
    for education in content["education"]:
        lines.append(" | ".join(str(education[k]) for k in ("institution", "degree", "field", "dates_display", "gpa") if education.get(k)))
    lines += ["Technical Skills", ", ".join(s["name"] for s in content["draft"]["skills"])]
    for section, kind in (("Experience", "employment"), ("Projects", "project")):
        lines.append(section)
        for record in content["records"]:
            if record["kind"] != kind:
                continue
            lines.append(" | ".join(str(record[k]) for k in ("employer", "title_display", "name", "location", "dates_display") if record.get(k)))
            lines.extend("- " + b["text"] for b in content["draft"]["bullets"] if b["record_id"] == record["id"])
    return "\n".join(lines)
