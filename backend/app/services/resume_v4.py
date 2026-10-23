"""Canonical requirement evidence and edit-only polish for generation v4.

Evidence assessments are model judgments, not semantic proof. Coverage and edits
are derived locally; neither may silently change the frozen source facts.
"""
import re
from typing import Literal
from pydantic import Field
from app.tailoring_schemas import StrictModel
from app.generation_schemas import (Requirement, ResumeDraft, RevisedResume, PolishedResume,
    ResumeBullet, ResumeSkill, RevisionDecision)
from app.services.requirement_grounding import quote_key


class CanonicalRequirement(Requirement):
    kind: Literal["basic_skill", "experience", "other"]
    skill_name: str | None = Field(description="One technology for a basic_skill requirement, otherwise null. Split distinct qualifications into separate requirements.")


class EvidenceAssessment(StrictModel):
    requirement_id: str
    full_claim_ids: list[str] = Field(max_length=40, description="Approved claims directly supporting the ENTIRE atomic requirement. Adjacent work belongs in partial_claim_ids.")
    partial_claim_ids: list[str] = Field(max_length=40)
    explanation: str = Field(min_length=1, max_length=800)


class Coverage(StrictModel):
    requirement_id: str
    status: Literal["supported", "partially_supported", "unsupported", "not_included"]
    available_support: Literal["full", "partial", "none"]
    full_claim_ids: list[str]
    partial_claim_ids: list[str]
    skill_source_ids: list[str]
    selected_claim_ids: list[str]
    selected_skill_names: list[str]
    explanation: str


class DraftV4(ResumeDraft):
    requirements: list[CanonicalRequirement] = Field(min_length=1, max_length=40)
    assessments: list[EvidenceAssessment] = Field(max_length=40)
    coverage: list[Coverage] = Field(max_length=40)


class EditedDraftV4(DraftV4):
    bullets: list[ResumeBullet] = Field(max_length=20)


class RevisedV4(RevisedResume):
    draft: DraftV4


class PolishedV4(PolishedResume):
    draft: DraftV4


class TextEdit(StrictModel):
    bullet_id: str
    replacement_text: str = Field(min_length=1, max_length=1800)


class PolishPlan(StrictModel):
    edits: list[TextEdit] = Field(max_length=20, description="Changed bullet text only. Empty is valid; never reproduce the draft or change its structure.")


class Choice(StrictModel):
    claim_id: str


class RevisionChoice(Choice):
    issue_ids: list[str] = Field(max_length=30)


class SelectionPlanV4(StrictModel):
    requirements: list[CanonicalRequirement] = Field(min_length=1, max_length=40)
    assessments: list[EvidenceAssessment] = Field(max_length=40)
    selections: list[Choice] = Field(max_length=20)
    skills: list[ResumeSkill] = Field(max_length=40)


class RevisionPlanV4(StrictModel):
    selections: list[RevisionChoice] = Field(max_length=20)
    skills: list[ResumeSkill] = Field(max_length=40)
    assessments: list[EvidenceAssessment] = Field(max_length=40)
    decisions: list[RevisionDecision] = Field(max_length=30)


def skill_support(requirement, projection):
    """Only a named basic technology qualification may use catalog evidence.

    A skill listing cannot establish duration, project use, deployment or scope.
    Unknown/compound qualifications fall back to claim evidence.
    """
    if requirement.kind != "basic_skill" or not requirement.skill_name:
        return [], set()
    quote = quote_key(requirement.quote)
    if re.search(r"\b(experience|years?|months?|production|deploy\w*|built|build\w*|implement\w*|operat\w*|own\w*|lead\w*|expert\w*|advanced|distributed|scal\w*)\b|\d", quote):
        return [], set()
    name = requirement.skill_name.casefold()
    aliases = {name}
    source_ids = []
    for tech in projection["technology_catalog"]:
        names = {tech['name'].casefold(), *(a.casefold() for a in tech['aliases'])}
        if name in names:
            aliases.update(names)
            source_ids.append(tech['id'])
    for group in projection['skill_groups']:
        if any(v.casefold() in aliases for v in group['values']):
            source_ids.append(group['id'])
    if not any(re.search(r"(?<![\w+#])" + re.escape(a) + r"(?![\w+#])", quote) for a in aliases):
        return [], set()
    # Do not let one skill satisfy a combined requirement such as Python and SQL.
    without_skill = quote
    for alias in sorted(aliases, key=len, reverse=True):
        without_skill = re.sub(r"(?<![\w+#])" + re.escape(alias) + r"(?![\w+#])", "", without_skill)
    if re.search(r"\b(and|including|with)\b|[,;/]", without_skill):
        return [], set()
    return sorted(set(source_ids)), aliases


def derive_coverage(draft, projection):
    assessments = {a.requirement_id: a for a in draft.assessments}
    selected = {cid for b in draft.bullets for cid in b.evidence_ids}
    result = []
    for req in draft.requirements:
        assessment = assessments.get(req.id)
        full = set(assessment.full_claim_ids) if assessment else set()
        partial = set(assessment.partial_claim_ids) if assessment else set()
        sources, aliases = skill_support(req, projection)
        selected_skills = sorted({s.name for s in draft.skills if s.name.casefold() in aliases and set(s.source_ids).intersection(sources)})
        selected_full, selected_partial = full & selected, partial & selected
        available = 'full' if full or sources else 'partial' if partial else 'none'
        status = ('supported' if selected_full or selected_skills else
                  'partially_supported' if selected_partial else
                  'not_included' if available != 'none' else 'unsupported')
        result.append(Coverage(requirement_id=req.id, status=status, available_support=available,
            full_claim_ids=sorted(full), partial_claim_ids=sorted(partial), skill_source_ids=sources,
            selected_claim_ids=sorted(selected_full | selected_partial), selected_skill_names=selected_skills,
            explanation=assessment.explanation if assessment else 'No evidence assessment supplied.'))
    return result


def refresh_coverage(draft, projection):
    draft.coverage = derive_coverage(draft, projection)
    # Compatibility field means a genuine full/partial evidence gap, not omitted content.
    draft.unmet_requirement_ids = [c.requirement_id for c in draft.coverage if c.available_support != 'full']
    return draft


def coverage_errors(draft, projection):
    errors = []
    req_ids = [r.id for r in draft.requirements]
    assessment_ids = [a.requirement_id for a in draft.assessments]
    if len(assessment_ids) != len(set(assessment_ids)) or set(assessment_ids) != set(req_ids):
        errors.append('Provide exactly one evidence assessment per canonical requirement.')
    # Exact/format-equivalent duplicates are deterministic; semantic deduplication
    # is also requested of select/critique and remains a human-review concern.
    quotes = [quote_key(r.quote).strip(' .:;') for r in draft.requirements]
    descriptions = [quote_key(r.description).strip(' .:;') for r in draft.requirements]
    if len(quotes) != len(set(quotes)) or len(descriptions) != len(set(descriptions)):
        errors.append('Duplicate job requirement. Keep one canonical entry and one evidence assessment; do not add a separate unmet copy.')
    claims = {c['id'] for c in projection['claims']}
    for a in draft.assessments:
        ids = a.full_claim_ids + a.partial_claim_ids
        if len(ids) != len(set(ids)) or not set(ids) <= claims:
            errors.append(f'Assessment {a.requirement_id} has duplicate, conflicting or unavailable claim evidence.')
    for r in draft.requirements:
        if (r.kind == 'basic_skill') != bool(r.skill_name):
            errors.append(f'Requirement {r.id}: only basic_skill qualifications may name a catalog skill.')
    expected = derive_coverage(draft, projection)
    if draft.coverage != expected:
        errors.append('Coverage differs from approved evidence and selected content.')
    if draft.unmet_requirement_ids != [c.requirement_id for c in expected if c.available_support != 'full']:
        errors.append('Evidence gaps must be derived from available source support, not bullet selection alone.')
    return errors


def compile_polish(plan, data):
    from app.services.resume_composition import CompositionError
    from app.services.resume_validation import fact_tokens
    draft = DraftV4.model_validate(data['prior_outputs']['revise']['draft']).model_copy(deep=True)
    by_id = {b.id: b for b in draft.bullets}
    edits = {}
    for edit in plan.edits:
        if edit.bullet_id not in by_id or edit.bullet_id in edits:
            raise CompositionError(f'Polish edit {edit.bullet_id} is unknown or repeated. Return each changed existing bullet once.')
        original = by_id[edit.bullet_id].text
        if fact_tokens(original) != fact_tokens(edit.replacement_text):
            raise CompositionError(f'Polish edit {edit.bullet_id} changes source wording beyond permitted style edits. Preserve facts and qualifiers or omit this edit.')
        edits[edit.bullet_id] = edit.replacement_text
    log = []
    for bullet in draft.bullets:
        after = edits.get(bullet.id, bullet.text)
        if after != bullet.text:
            log.append({'bullet_id': bullet.id, 'before': bullet.text, 'after': after})
            bullet.text = after
    return PolishedV4(draft=draft, edits=log)


def compile_selection(plan, data):
    from app.services.resume_composition import SelectionPlan, RevisionPlan, compile_plan
    revision = isinstance(plan, RevisionPlanV4)
    raw = plan.model_dump()
    selections = [*raw['selections'], *[v for v in raw.get('overlap_choices', {}).values() if v is not None]]
    assessments = {a.requirement_id: a for a in plan.assessments}
    for selection in selections:
        selection['requirement_ids'] = [rid for rid, a in assessments.items() if selection['claim_id'] in a.full_claim_ids + a.partial_claim_ids]
        if revision:
            selection['parent_bullet_ids'] = []
    requirements = data['prior_outputs']['select']['requirements'] if revision else raw['requirements']
    legacy_requirements = [{k: r[k] for k in ('id', 'quote', 'description')} for r in requirements]
    legacy_data = {**data, 'contract': {'composition_version': 1}}
    if revision:
        prior = dict(data['prior_outputs']['select'])
        prior['requirements'] = legacy_requirements
        legacy_data['prior_outputs'] = {**data['prior_outputs'], 'select': prior}
        legacy_plan = RevisionPlan(selections=selections, skills=plan.skills, decisions=plan.decisions)
    else:
        legacy_plan = SelectionPlan(requirements=legacy_requirements, selections=selections, skills=plan.skills)
    compiled = compile_plan(legacy_plan, legacy_data)
    base = compiled.draft if revision else compiled
    value = base.model_dump()
    value.update(requirements=requirements, assessments=raw['assessments'], coverage=[])
    draft = refresh_coverage(DraftV4.model_validate(value), data['approved_evidence'])
    return RevisedV4(draft=draft, decisions=compiled.decisions, lineage=compiled.lineage) if revision else draft


def revision_seed(data):
    from app.services.resume_composition import exclusive_groups
    original = data['prior_outputs']['select']
    groups = exclusive_groups(data)
    result = {'selections': [], 'skills': original['skills'], 'assessments': original['assessments'], 'decisions': []}
    if groups:
        result['overlap_choices'] = {f'group_{i}': None for i in range(1, len(groups) + 1)}
    for bullet in original['bullets']:
        if len(bullet['evidence_ids']) != 1:
            return None
        cid = bullet['evidence_ids'][0]
        value = {'claim_id': cid, 'issue_ids': []}
        slot = next((f'group_{i}' for i, members in enumerate(groups, 1) if cid in members), None)
        if slot:
            result['overlap_choices'][slot] = value
        else:
            result['selections'].append(value)
    return result
