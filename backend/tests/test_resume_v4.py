"""Fictional regressions for omissions, duplicate gaps and skill-only coverage."""
import copy
import pytest
from pydantic import ValidationError
from app.services import resume_v4 as v4
from app.services.resume_composition import CompositionError


def example():
    projection = {'claims': [{'id': 'C1', 'record_id': 'R1', 'text': 'Successfully built internal Python checks.'},
                             {'id': 'C2', 'record_id': 'R1', 'text': 'Built a public demo.'}],
        'records': [{'id': 'R1'}], 'technology_catalog': [{'id': 'T1', 'name': 'Python', 'aliases': ['Python3']}],
        'skill_groups': [], 'claim_overlap_groups': []}
    requirements = [
        {'id': 'Q1', 'quote': 'Python proficiency (we are a Python shop mostly)', 'description': 'Python proficiency', 'kind': 'basic_skill', 'skill_name': 'Python'},
        {'id': 'Q2', 'quote': 'Production Kubernetes experience', 'description': 'Production Kubernetes experience', 'kind': 'experience', 'skill_name': None},
        {'id': 'Q3', 'quote': 'Build a public application', 'description': 'Public applications', 'kind': 'experience', 'skill_name': None},
        {'id': 'Q4', 'quote': 'Build production Python services', 'description': 'Production Python services', 'kind': 'experience', 'skill_name': None}]
    assessments = [{'requirement_id': f'Q{i}', 'full_claim_ids': ['C2'] if i == 3 else [],
                    'partial_claim_ids': ['C1'] if i == 4 else [], 'explanation': 'Fictional assessment.'} for i in range(1, 5)]
    draft = v4.DraftV4(requirements=requirements, assessments=assessments, coverage=[],
        bullets=[{'id': 'B1', 'record_id': 'R1', 'text': projection['claims'][0]['text'], 'evidence_ids': ['C1'], 'requirement_ids': ['Q4']}],
        skills=[{'name': 'Python', 'source_ids': ['T1']}], unmet_requirement_ids=[], change_summary=[])
    v4.refresh_coverage(draft, projection)
    return projection, draft


def test_all_four_coverage_states_and_skills_without_bullet_mapping():
    projection, draft = example()
    assert [c.status for c in draft.coverage] == ['supported', 'unsupported', 'not_included', 'partially_supported']
    assert draft.unmet_requirement_ids == ['Q2', 'Q4']
    assert v4.coverage_errors(draft, projection) == []
    draft.skills = []
    v4.refresh_coverage(draft, projection)
    assert draft.coverage[0].status == 'not_included'
    assert draft.coverage[0].available_support == 'full'


@pytest.mark.parametrize('quote', ['3 years of Python', 'Production Python expertise', 'Python and SQL', 'Experience with Python', 'Build Python services'])
def test_catalog_skill_does_not_satisfy_stronger_or_compound_requirements(quote):
    projection, draft = example()
    draft.requirements[0].quote = quote
    v4.refresh_coverage(draft, projection)
    assert draft.coverage[0].status == 'unsupported'


def test_duplicate_requirements_and_invented_source_ids_are_rejected():
    projection, draft = example()
    duplicate = draft.requirements[0].model_copy(update={'id': 'UNSAT-1', 'quote': draft.requirements[0].quote.upper()})
    draft.requirements.append(duplicate)
    draft.assessments.append(v4.EvidenceAssessment(requirement_id='UNSAT-1', full_claim_ids=['FAKE'], partial_claim_ids=[], explanation='Invented'))
    v4.refresh_coverage(draft, projection)
    errors = v4.coverage_errors(draft, projection)
    assert any('Duplicate job requirement' in e for e in errors)
    assert any('unavailable' in e for e in errors)


def test_edit_only_polish_preserves_entire_draft_and_builds_ordered_log():
    _, draft = example()
    draft.bullets.append(draft.bullets[0].model_copy(update={'id': 'B2'}))
    before = draft.model_dump()
    data = {'prior_outputs': {'revise': {'draft': before}}}
    output = v4.compile_polish(v4.PolishPlan(edits=[{'bullet_id': 'B2', 'replacement_text': 'Built internal Python checks.'}]), data)
    assert len(output.draft.bullets) == 2
    expected = copy.deepcopy(before)
    expected['bullets'][1]['text'] = 'Built internal Python checks.'
    assert output.draft.model_dump() == expected
    assert [e.bullet_id for e in output.edits] == ['B2']
    assert v4.compile_polish(v4.PolishPlan(edits=[]), data).draft == draft
    assert data['prior_outputs']['revise']['draft'] == before
    with pytest.raises(ValidationError):
        v4.PolishPlan.model_validate({'edits': [], 'draft': {'bullets': []}})


@pytest.mark.parametrize('edits', [
    [{'bullet_id': 'UNKNOWN', 'replacement_text': 'Built internal Python checks.'}],
    [{'bullet_id': 'B1', 'replacement_text': 'Built production Python checks.'}],
    [{'bullet_id': 'B1', 'replacement_text': 'Built internal Python checks.'}] * 2,
])
def test_polish_rejects_unknown_duplicate_and_factual_edits(edits):
    _, draft = example()
    with pytest.raises(CompositionError):
        v4.compile_polish(v4.PolishPlan(edits=edits), {'prior_outputs': {'revise': {'draft': draft.model_dump()}}})
