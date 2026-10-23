"""Compile compact model selections into source-owned text and bullet identities.

The raw plan remains in attempt metadata. Compilation never drops invalid selections;
the normal stage validator still decides whether the compiled draft can advance.
"""
import hashlib
from typing import Literal
from pydantic import Field, create_model
from app.tailoring_schemas import StrictModel
from app.generation_schemas import Requirement, ResumeSkill, ResumeDraft, RevisedResume, RevisionDecision


class CompositionError(ValueError):
    """Safe, application-authored feedback; never a raw provider exception."""


class Selection(StrictModel):
    claim_id: str = Field(description="Exactly one approved claim ID; never prose or a technology ID.")
    requirement_ids: list[str] = Field(max_length=20)


class SelectionPlan(StrictModel):
    requirements: list[Requirement] = Field(min_length=1, max_length=40)
    unsupported_requirements: list[Requirement] = Field(default_factory=list, max_length=40, description="Explicit posting requirements/preferences with NO approved evidence. Include these even when optional; never omit them just because they cannot be targeted.")
    selections: list[Selection] = Field(min_length=1, max_length=20)
    skills: list[ResumeSkill] = Field(max_length=40)


class RevisionSelection(Selection):
    parent_bullet_ids: list[str] = Field(max_length=0, description="Always empty. This compact protocol selects whole single claims, so new claims are additions authorized by draft issues, not splits of an old bullet. The application owns identities.")
    issue_ids: list[str] = Field(max_length=30, description="Accepted issues authorizing a new selection. Empty for unchanged selections.")


class RevisionPlan(StrictModel):
    selections: list[RevisionSelection] = Field(min_length=1, max_length=20)
    skills: list[ResumeSkill] = Field(max_length=40)
    decisions: list[RevisionDecision] = Field(max_length=30)


def exclusive_groups(data):
    # Disjoint choice slots make repeated overlap alternatives unrepresentable.
    # Merge intersecting groups conservatively rather than choosing which rule wins.
    ids = {c["id"] for c in data["approved_evidence"]["claims"]}
    groups = []
    for group in data["approved_evidence"]["claim_overlap_groups"]:
        members = set(group["claim_ids"]) & ids
        for previous in groups[:]:
            if previous & members:
                members |= previous
                groups.remove(previous)
        if members:
            groups.append(members)
    return groups


def plan_model(output_model, data):
    if data.get('contract', {}).get('composition_version') == 3:
        return plan_model(output_model, {**data, 'contract': {**data['contract'], 'composition_version': 2}})
    if data.get("contract", {}).get("composition_version") == 2:
        from app.services import resume_v4 as v4
        if output_model is v4.PolishedV4:
            return v4.PolishPlan
        if output_model is v4.DraftV4:
            return choice_model(v4.selection_model(data['approved_evidence']), v4.Choice, data)
        if output_model is v4.RevisedV4:
            return choice_model(v4.RevisionPlanV4, v4.RevisionChoice, data)
        return output_model
    if data.get("contract", {}).get("composition_version") != 1:
        return output_model
    base = SelectionPlan if output_model is ResumeDraft else RevisionPlan if output_model is RevisedResume else None
    if base is None:
        return output_model
    return choice_model(base, RevisionSelection if base is RevisionPlan else Selection, data)


def choice_model(base, item, data):
    groups = exclusive_groups(data)
    ids = {c["id"] for c in data["approved_evidence"]["claims"]}
    if not groups:
        return base
    grouped = set().union(*groups)
    independent = create_model("IndependentSelection", __base__=item,
        claim_id=(Literal[tuple(sorted(ids-grouped))] if ids-grouped else Literal["NO_INDEPENDENT_CLAIMS"], ...))
    choices = {}
    for index, members in enumerate(groups, 1):
        choice = create_model(f"OverlapChoice{index}", __base__=item, claim_id=(Literal[tuple(sorted(members))], ...))
        choices[f"group_{index}"] = (choice | None, Field(description="Select one representative or null. Never repeat these alternatives in independent selections."))
    slots = create_model("OverlapChoices", __base__=StrictModel, **choices)
    return create_model(base.__name__ + "WithChoices", __base__=base,
        selections=(list[independent], Field(min_length=0, max_length=20 if ids-grouped else 0)),
        overlap_choices=(slots, ...))


def revision_seed(data):
    """Give revision the same choice representation as selection, without lost slots."""
    if data.get("contract", {}).get("composition_version") in (2, 3):
        from app.services.resume_v4 import revision_seed as current_seed
        return current_seed(data)
    original = data["prior_outputs"]["select"]
    groups = exclusive_groups(data)
    slots = {f"group_{i}": None for i in range(1, len(groups) + 1)}
    selections = []
    for bullet in original["bullets"]:
        if len(bullet["evidence_ids"]) != 1:
            return None  # No lossy conversion of historical multi-claim bullets.
        cid = bullet["evidence_ids"][0]
        value = {"claim_id": cid, "requirement_ids": bullet["requirement_ids"], "parent_bullet_ids": [], "issue_ids": []}
        slot = next((f"group_{i}" for i, members in enumerate(groups, 1) if cid in members), None)
        if slot:
            slots[slot] = value
        else:
            selections.append(value)
    seed = {"selections": selections, "skills": original["skills"], "decisions": []}
    if groups:
        seed["overlap_choices"] = slots
    return seed


def compile_plan(plan, data):
    if data.get('contract', {}).get('composition_version') == 3:
        from app.services.resume_v5 import compile_plan as current
        return current(plan, data)
    if data.get("contract", {}).get("composition_version") == 2:
        from app.services.resume_v4 import PolishPlan, compile_polish, compile_selection
        return compile_polish(plan, data) if isinstance(plan, PolishPlan) else compile_selection(plan, data)
    claims = {c["id"]: c for c in data["approved_evidence"]["claims"]}
    previous = data["prior_outputs"].get("select")
    requirements = previous["requirements"] if isinstance(plan, RevisionPlan) else [*plan.requirements, *plan.unsupported_requirements]
    old = {tuple(b["evidence_ids"]): b for b in previous["bullets"]} if previous else {}
    bullets, lineage = [], []
    selections = list(plan.selections)
    choices = getattr(plan, "overlap_choices", None)
    if choices:
        selections.extend(value for name in type(choices).model_fields if (value := getattr(choices, name)) is not None)
    for selected in selections:
        claim = claims.get(selected.claim_id)
        if claim is None:
            raise CompositionError("Selection contains an unknown claim ID. Choose only contract.claim_ids.")
        retained = old.get((claim["id"],))
        bid = retained["id"] if retained else "B-" + hashlib.sha256(claim["id"].encode()).hexdigest()[:16]
        bullets.append({"id": bid, "record_id": claim["record_id"], "evidence_ids": [claim["id"]],
                        "requirement_ids": selected.requirement_ids, "text": claim["text"]})
        if isinstance(plan, RevisionPlan):
            if retained and (selected.parent_bullet_ids or selected.issue_ids):
                # Retained selections can cite an issue explaining mapping changes,
                # but they must not pretend to replace another bullet.
                if set(selected.parent_bullet_ids) - {retained["id"]}:
                    raise CompositionError("A retained selection cannot replace a different parent bullet.")
            if not retained:
                links = selected.issue_ids
                if not links:
                    accepted = {d.issue_id for d in plan.decisions if d.action == "accepted"}
                    issues = data["prior_outputs"].get("critique", {}).get("issues", [])
                    links = [i["issue_id"] for i in issues if i["issue_id"] in accepted and not i["requires_user_fact_confirmation"]
                             and (i["field_path"] == "draft" or i["field_path"] in {f"bullets.{p}" for p in selected.parent_bullet_ids})]
                if not links:
                    raise CompositionError("A new selection needs an accepted draft recommendation, or an accepted parent recommendation for its existing evidence. Preserve the previous selection if none applies.")
                lineage.append({"bullet_id": bid, "parent_bullet_ids": selected.parent_bullet_ids, "issue_ids": links})
    # A plan may target the same fact at several requirements. Coalesce identical
    # claim identities, preserving every link, instead of repeating the same prose.
    # No distinct claim or skill is discarded to make validation pass.
    merged = {}
    for bullet in bullets:
        if bullet["id"] in merged:
            old_links = merged[bullet["id"]]["requirement_ids"]
            merged[bullet["id"]]["requirement_ids"] = list(dict.fromkeys([*old_links, *bullet["requirement_ids"]]))
        else:
            merged[bullet["id"]] = bullet
    bullets = list(merged.values())
    merged_lineage = {}
    for entry in lineage:
        if entry["bullet_id"] in merged_lineage:
            existing = merged_lineage[entry["bullet_id"]]
            for field in ("parent_bullet_ids", "issue_ids"):
                existing[field] = list(dict.fromkeys([*existing[field], *entry[field]]))
        else:
            merged_lineage[entry["bullet_id"]] = entry
    skills = {}
    for skill in plan.skills:
        key = skill.name.casefold()
        if key in skills:
            skills[key].source_ids = list(dict.fromkeys([*skills[key].source_ids, *skill.source_ids]))
        else:
            skills[key] = skill.model_copy(deep=True)
    covered = {rid for b in bullets for rid in b["requirement_ids"]}
    if isinstance(plan, SelectionPlan) and covered.intersection(r.id for r in plan.unsupported_requirements):
        raise CompositionError("Unsupported requirements cannot be targeted by a selection. Keep their IDs out of requirement_ids.")
    ids = [r["id"] if isinstance(r, dict) else r.id for r in requirements]
    draft = ResumeDraft(requirements=requirements, bullets=bullets, skills=list(skills.values()),
        unmet_requirement_ids=[rid for rid in ids if rid not in covered], change_summary=[])
    return RevisedResume(draft=draft, decisions=plan.decisions, lineage=list(merged_lineage.values())) if isinstance(plan, RevisionPlan) else draft
