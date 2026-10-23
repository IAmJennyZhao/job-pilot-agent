"""Conservative source-preserving checks, never a claim of semantic proof."""
import re
from app.services.generation_v1 import validation as legacy
from app.generation_schemas import ResumeDraft, CritiqueReport, RevisedResume, PolishedResume, FactualAccuracyReport

STAGES = ("select", "critique", "revise", "polish")
OUTPUT_MODELS = dict(zip(STAGES, (ResumeDraft, CritiqueReport, RevisedResume, PolishedResume)))
PROMPT_VERSIONS = {stage: f"resume-{stage}-v4" for stage in STAGES}


def generation_version(snapshot):
    version = snapshot.get("generation_version", 1)
    if type(version) is not int or version not in (1, 2, 3, 4):
        raise ValueError("Unsupported generation version")
    return version


def output_models(snapshot):
    if generation_version(snapshot) == 4:
        from app.services.resume_v4 import DraftV4, CritiqueV4, RevisedV4, PolishedV4
        return dict(zip(STAGES, (DraftV4, CritiqueV4, RevisedV4, PolishedV4)))
    return legacy.OUTPUT_MODELS if generation_version(snapshot) == 1 else OUTPUT_MODELS


def prompt_versions(snapshot):
    return {stage: f"resume-{stage}-v{generation_version(snapshot)}" for stage in STAGES}


def requirement_errors(requirements, snapshot):
    from app.services.requirement_grounding import grounded_quote
    posting = snapshot["job"]["source_content"]
    if generation_version(snapshot) < 3:
        return [f"Requirement {r.id} lacks an exact posting quote." for r in requirements if r.quote not in posting]
    return [f"Requirement {r.id} cannot be grounded in the saved posting. Use a supported excerpt or a heading with its own list item; case, whitespace and typographic differences are allowed. Do not change technologies, numbers, negation or qualifications."
            for r in requirements if not grounded_quote(r.quote, posting)]


def comparison_draft(draft, snapshot):
    value = draft.model_dump()
    if generation_version(snapshot) >= 3:
        from app.services.requirement_grounding import quote_key
        for requirement in value["requirements"]:
            requirement["quote"] = quote_key(requirement["quote"])
    return value


def fact_tokens(text):
    # Only narrowly equivalent style edits are automatic. Arbitrary paraphrases
    # need review and cannot be accepted merely because an evidence ID exists.
    text = text.casefold().replace("utilized", "used").replace("utilizing", "using").replace("\u2212", "-")
    text = re.sub(r"\bin order to\b", "to", text)
    text = re.sub(r"\b(successfully|effectively)\b", "", text)
    return re.findall(r"[\w]+(?:[./+#%-][\w]+)*|[%+#<>\u2264\u2265\u2248~\u00b1$\u20ac\u00a3\u00a5]", text, flags=re.UNICODE) + ["#metrics#"] + re.findall(r"(?<!\w)[+-]?\d+(?:[.,/]\d+)*(?:%|x)?", text)


def unique(values, label, errors):
    if len(values) != len(set(values)):
        errors.append(f"Duplicate {label}.")


def validate_draft(draft, snapshot):
    if generation_version(snapshot) == 1:
        return legacy.validate_draft(draft, snapshot)
    errors = []
    if not draft.requirements:
        errors.append("Map at least one actual posting requirement, including unsupported requirements.")
    projection = snapshot["projection"]
    claims = {c["id"]: c for c in projection["claims"]}
    records = {r["id"] for r in projection["records"]}
    requirements = {r.id for r in draft.requirements}
    unique([r.id for r in draft.requirements], "requirement IDs", errors)
    unique([b.id for b in draft.bullets], "bullet IDs", errors)
    unique([s.name.casefold() for s in draft.skills], "skills", errors)
    errors.extend(requirement_errors(draft.requirements, snapshot))
    covered = set()
    selected_claims = set()
    for bullet in draft.bullets:
        unique(bullet.evidence_ids, "bullet evidence IDs", errors)
        source_claims = [claims.get(cid) for cid in bullet.evidence_ids]
        if selected_claims.intersection(bullet.evidence_ids):
            errors.append(f"Bullet {bullet.id} duplicates a claim already selected elsewhere.")
        selected_claims.update(bullet.evidence_ids)
        if bullet.record_id not in records or any(not c or c["record_id"] != bullet.record_id for c in source_claims):
            errors.append(f"Bullet {bullet.id} references unavailable or unrelated record evidence.")
            continue
        if not set(bullet.requirement_ids) <= requirements:
            errors.append(f"Bullet {bullet.id} references an unknown requirement.")
        covered.update(bullet.requirement_ids)
        if len(bullet.evidence_ids) > 1 and len(bullet.text.split()) > 45:
            errors.append(f"Bullet {bullet.id} combines too much text. Use separate nonoverlapping complete claims or select one representative; multi-claim bullets allow at most 45 words.")
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
    if generation_version(snapshot) >= 4:
        from app.services.resume_v4 import coverage_errors
        errors.extend(coverage_errors(draft, projection))
    elif set(draft.unmet_requirement_ids) != requirements - covered:
        errors.append("Unmet requirements must equal requirements without selected bullet evidence.")
    for overlap in projection["claim_overlap_groups"]:
        matching = [b.id for b in draft.bullets if set(b.evidence_ids).intersection(overlap["claim_ids"])]
        if len(matching) > 1:
            errors.append(f"Overlap group {overlap['id']} occurs in bullets {matching}. Keep one representative or combine permitted complementary claims in ONE bullet of at most 45 words.")
    return errors


def polish_diff(before, after):
    old = {b.id: b.text for b in before.bullets}
    return [{"bullet_id": b.id, "before": old[b.id], "after": b.text} for b in after.bullets if b.id in old and b.text != old[b.id]]


def validate_stage(stage, output, snapshot, accepted):
    if generation_version(snapshot) == 1:
        return legacy.validate_stage(stage, output, snapshot, accepted)
    errors = []
    draft = output if stage == "select" else output.draft if stage in {"revise", "polish"} else None
    if draft:
        errors.extend(validate_draft(draft, snapshot))
    if stage == "critique":
        original = output_models(snapshot)["select"].model_validate(accepted["select"])
        if generation_version(snapshot) >= 3:
            errors.extend(requirement_errors(original.requirements, snapshot))
        fields = {"draft", "skills", *[f"bullets.{b.id}" for b in original.bullets]}
        claim_ids = {c["id"] for c in snapshot["projection"]["claims"]}
        req_ids = {r.id for r in original.requirements}
        unique([i.issue_id for i in output.issues], "critique issue IDs", errors)
        for issue in output.issues:
            if issue.field_path not in fields:
                errors.append(f"Critique {issue.issue_id} has invalid target {issue.field_path!r}. Allowed targets: {sorted(fields)}. Never append .text; use draft for gaps.")
            allowed = claim_ids | {x["id"] for key in ("technology_catalog", "skill_groups") for x in snapshot["projection"][key]} if issue.field_path == "skills" else claim_ids
            if not set(issue.evidence_ids) <= allowed:
                errors.append(f"Critique {issue.issue_id} has invalid evidence IDs {sorted(set(issue.evidence_ids)-allowed)}. Allowed evidence IDs for this target: {sorted(allowed)}.")
            if not set(issue.requirement_ids) <= req_ids:
                errors.append(f"Critique {issue.issue_id} has invalid requirement IDs. Allowed: {sorted(req_ids)}.")
        if generation_version(snapshot) >= 4:
            issues = {i.issue_id: i for i in output.issues}
            unique([c.requirement_id for c in output.assessment_corrections], 'assessment corrections', errors)
            for correction in output.assessment_corrections:
                issue = issues.get(correction.issue_id)
                ids = correction.full_claim_ids + correction.partial_claim_ids
                if not issue or issue.field_path != 'draft' or issue.requires_user_fact_confirmation or correction.requirement_id not in issue.requirement_ids:
                    errors.append(f'Assessment correction {correction.requirement_id} needs a linked draft issue for that requirement using existing approved facts.')
                if correction.requirement_id not in req_ids or not set(ids) <= claim_ids or len(ids) != len(set(ids)):
                    errors.append(f'Assessment correction {correction.requirement_id} has unavailable or conflicting evidence.')
    if stage == "revise":
        original = output_models(snapshot)["select"].model_validate(accepted["select"])
        critique = output_models(snapshot)["critique"].model_validate(accepted["critique"])
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
        from app.services.resume_lineage import validate_lineage
        authorized_new, lineage_errors = validate_lineage(output, old, new, issues)
        errors.extend(lineage_errors)
        for bid in old.keys() | new.keys():
            if old.get(bid) != new.get(bid) and "draft" not in accepted_fields and f"bullets.{bid}" not in accepted_fields and bid not in authorized_new:
                errors.append(f"Bullet {bid} changed without an accepted critique recommendation.")
            if bid in old and bid in new and (old[bid].record_id, old[bid].evidence_ids) != (new[bid].record_id, new[bid].evidence_ids):
                errors.append(f"Bullet {bid} changed its source identity; a new claim needs a new bullet ID.")
        if [b.id for b in original.bullets] != [b.id for b in draft.bullets] and old.keys() == new.keys() and "draft" not in accepted_fields:
            errors.append("Reordering bullets needs an accepted draft recommendation.")
        if original.skills != draft.skills and not {"draft", "skills"} & accepted_fields:
            errors.append("Skills changed without an accepted recommendation.")
        if comparison_draft(original, snapshot)["requirements"] != comparison_draft(draft, snapshot)["requirements"]:
            errors.append("Revision must preserve the original requirement mapping.")
        if generation_version(snapshot) >= 4 and original.assessments != draft.assessments and 'draft' not in accepted_fields:
            errors.append('Changing requirement evidence assessments needs an accepted draft critique recommendation.')
        if generation_version(snapshot) >= 4:
            from app.services.resume_v4 import EvidenceAssessment
            accepted_ids = {d.issue_id for d in output.decisions if d.action == 'accepted'}
            corrections = {c.requirement_id: EvidenceAssessment.model_validate(c.model_dump(exclude={'issue_id'}))
                           for c in critique.assessment_corrections if c.issue_id in accepted_ids}
            expected = [corrections.get(a.requirement_id, a) for a in original.assessments]
            if draft.assessments != expected:
                errors.append('Revision must apply every accepted assessment correction exactly and preserve other assessments.')
    if stage == "polish":
        original = output_models(snapshot)["revise"].model_validate(accepted["revise"]).draft
        old, new = comparison_draft(original, snapshot), comparison_draft(draft, snapshot)
        for value in (old, new):
            for bullet in value["bullets"]:
                bullet.pop("text")
        if old != new:
            errors.append("Polish changed the selected content, order, provenance, skills or requirement mapping.")
        changes = polish_diff(original, draft)
        if [e.model_dump() for e in output.edits] != changes:
            errors.append("Polish edit log does not match computed changes.")
    return {"valid": not errors, "blocking_issues": errors, "validator_version": f"resume-v{generation_version(snapshot)}"}


def accuracy_report(draft, snapshot, accepted):
    if generation_version(snapshot) == 1:
        return legacy.accuracy_report(draft, snapshot, accepted)
    errors = validate_draft(draft, snapshot)
    before = output_models(snapshot)["revise"].model_validate(accepted["revise"]).draft
    return FactualAccuracyReport(validator_version=f"resume-v{generation_version(snapshot)}", valid=not errors, blocking_issues=errors,
        supported_claim_ids=sorted({cid for b in draft.bullets for cid in b.evidence_ids}),
        wording_changes=polish_diff(before, draft), unmet_requirement_ids=draft.unmet_requirement_ids).model_dump()


def assemble_content(draft, snapshot):
    if generation_version(snapshot) == 1:
        return legacy.assemble_content(draft, snapshot)
    draft = draft.model_copy(deep=True)
    draft.change_summary = [f"Selected {len(draft.bullets)} supported bullets from {len({b.record_id for b in draft.bullets})} records.", f"Selected {len(draft.skills)} supported skills; {len(draft.unmet_requirement_ids)} mapped requirements remain unmet."]
    if generation_version(snapshot) >= 4:
        counts = {status: sum(c.status == status for c in draft.coverage) for status in ('supported', 'partially_supported', 'unsupported', 'not_included')}
        draft.change_summary[1] = f"Coverage: {counts['supported']} supported, {counts['partially_supported']} partially supported, {counts['unsupported']} unsupported, {counts['not_included']} not included in this draft."
    selected = {b.record_id for b in draft.bullets}
    records = [r for r in snapshot["projection"]["records"] if r["id"] in selected]
    records.sort(key=lambda r: r.get("start") or "", reverse=True)
    return {"identity": snapshot["identity"], "education": snapshot["projection"]["education"],
            "records": records, "section_order": ["Education", "Technical Skills", "Experience", "Projects"],
            "draft": draft.model_dump()}


def plain_text(content, snapshot=None):
    if snapshot is not None and generation_version(snapshot) == 1:
        return legacy.plain_text(content)
    identity = content["identity"]
    lines = [identity.get("name", "")]
    contact = " | ".join(str(identity[k]) for k in ("location", "phone", "email", "website", "github", "linkedin") if identity.get(k))
    if contact:
        lines.append(contact)
    lines.append("Education")
    for education in content["education"]:
        parts = [education["institution"], education["degree"]]
        if education.get("graduation_display") or education.get("graduation"):
            parts.append(education.get("graduation_display") or education["graduation"])
        if education.get("gpa"):
            parts.append("GPA " + education["gpa"])
        if education.get("minors"):
            parts.append("Minors: " + ", ".join(education["minors"]))
        lines.append(" | ".join(parts))
    lines += ["Technical Skills", ", ".join(s["name"] for s in content["draft"]["skills"])]
    for section, kind in (("Experience", "employment"), ("Projects", "project")):
        lines.append(section)
        for record in content["records"]:
            if record["kind"] != kind:
                continue
            parts = [str(record[k]) for k in ("employer", "title_display", "name", "location") if record.get(k)]
            dates = record.get("dates_display") or " - ".join(record[k] for k in ("start", "end") if record.get(k))
            if dates:
                parts.append(dates)
            lines.append(" | ".join(parts))
            lines.extend("- " + b["text"] for b in content["draft"]["bullets"] if b["record_id"] == record["id"])
    return "\n".join(lines)
