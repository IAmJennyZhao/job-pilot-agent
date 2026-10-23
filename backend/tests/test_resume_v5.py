"""Versioned coverage and page-budget regression/evaluation cases."""
import json
from pathlib import Path
import pytest
from app.services import resume_v5 as v5, resume_v4 as v4
from app.services.resume_composition import compile_plan
from app.services.resume_validation import validate_stage
from test_resume_v4 import example

CASES = json.loads((Path(__file__).parent / 'fixtures' / 'coverage_cases.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_reviewed_coverage_guard_examples(case):
    actual = 'partial' if v5.guard_reason(case['requirement'], {'text': case['claim']}) else 'full'
    assert actual == case['expected'], case['rationale']


def test_independent_requirements_are_split_but_shared_quotes_and_basic_agents_remain_valid():
    _, draft = example()
    draft.requirements[0].description = 'Build AI agents, backend services, APIs and web UIs'
    assert len(v5.atomic_errors(draft.requirements)) == 1
    requirements = [draft.requirements[0].model_copy(update={'id': str(i), 'description': name})
                    for i, name in enumerate(('Build AI agents', 'Build backend services', 'Build APIs', 'Build web UIs'))]
    assert v5.atomic_errors(requirements) == []


def test_guard_cannot_be_undone_by_critique_and_preserves_original_plan():
    projection, draft = example()
    req = draft.requirements[0].model_copy(update={'description': 'Experience with evaluation pipelines', 'quote': 'Eval pipelines', 'kind': 'experience', 'skill_name': None})
    plan = v4.SelectionPlanV4(requirements=[req], assessments=[{'requirement_id': req.id, 'full_claim_ids': ['C1'], 'partial_claim_ids': [], 'explanation': 'Overstated model assessment.'}], selections=[{'claim_id': 'C1'}], skills=[])
    raw = plan.model_dump()
    data = {'contract': {'composition_version': 3}, 'stage': 'select', 'approved_evidence': projection, 'prior_outputs': {}}
    output = compile_plan(plan, data)
    assert output.coverage[0].status == 'partially_supported'
    assert plan.model_dump() == raw
    issue = {'issue_id': 'I1', 'severity': 'improvement', 'field_path': 'draft', 'requirement_ids': [req.id], 'evidence_ids': ['C1'], 'finding': 'Upgrade.', 'proposed_action': 'Upgrade.', 'requires_user_fact_confirmation': False}
    critique = v4.CritiqueV4(issues=[issue], assessment_corrections=[{**raw['assessments'][0], 'issue_id': 'I1'}])
    data.update(stage='revise', prior_outputs={'select': output.model_dump(), 'critique': critique.model_dump()})
    revised = compile_plan(v4.RevisionPlanV4(selections=[{'claim_id': 'C1', 'issue_ids': []}], skills=[], decisions=[{'issue_id': 'I1', 'action': 'accepted', 'reason': 'Accepted.'}]), data)
    assert revised.draft.coverage[0].status == 'partially_supported'
    snapshot = {'generation_version': 5, 'job': {'source_content': 'Eval pipelines'}, 'projection': projection}
    assert validate_stage('revise', revised, snapshot, data['prior_outputs'])['valid']


def test_budget_counts_all_choices_keeps_full_claims_and_marks_omitted_evidence():
    projection, draft = example()
    projection['records'][0]['kind'] = 'employment'
    draft.bullets = []
    for i in range(16):
        text = f'Built component {i} with unique capability {i*i} and measured outcome {i+100}.'
        projection['claims'].append({'id': f'X{i}', 'record_id': 'R1', 'text': text})
        draft.bullets.append(v4.ResumeBullet(id=f'B{i}', record_id='R1', evidence_ids=[f'X{i}'], requirement_ids=[], text=text))
    draft.bullets[-1].requirement_ids = ['Q3']
    draft.assessments[2].full_claim_ids = ['X15']
    v4.refresh_coverage(draft, projection)
    original = draft.model_dump()
    bounded = v5.budget(draft, projection)
    assert len(bounded.bullets) <= 10 and v5.budget_report(bounded, projection)['within_budget']
    assert 'X15' in [c for b in bounded.bullets for c in b.evidence_ids]
    assert all(b.text == next(c['text'] for c in projection['claims'] if c['id'] == b.evidence_ids[0]) for b in bounded.bullets)
    assert draft.model_dump() == original
    assert v5.budget(bounded, projection) == bounded


def test_space_and_repetition_matter_more_than_bullet_count():
    projection, draft = example()
    short = v5.estimate(draft, projection)
    draft.bullets[0].text = 'A long complete approved accomplishment with preserved qualifiers. ' * 15
    assert v5.estimate(draft, projection) > short
    duplicate = draft.bullets[0].model_copy(update={'id': 'B2', 'evidence_ids': ['C2']})
    draft.bullets.append(duplicate)
    assert len(v5.budget(draft, projection).bullets) == 1


def test_v4_compilation_is_unchanged_by_new_default():
    projection, draft = example()
    data = {'stage': 'select', 'contract': {'composition_version': 2}, 'approved_evidence': projection, 'prior_outputs': {}}
    req = draft.requirements[0].model_copy(update={'description': 'Own production services', 'quote': 'Own production services', 'kind': 'experience', 'skill_name': None})
    plan = v4.SelectionPlanV4(requirements=[req], assessments=[{'requirement_id': req.id, 'full_claim_ids': ['C1'], 'partial_claim_ids': [], 'explanation': 'Historical interpretation.'}], selections=[{'claim_id': 'C1'}], skills=[])
    assert compile_plan(plan, data).coverage[0].status == 'supported'
    data['contract']['composition_version'] = 3
    assert compile_plan(plan, data).coverage[0].status == 'partially_supported'


def test_partial_coverage_does_not_remove_priority_for_direct_evidence(monkeypatch):
    projection, draft = example()
    monkeypatch.setitem(v5.POLICY, 'max_bullets', 2)
    draft.skills = []
    texts = ['Quick partial result.', 'Designed a complete public application with accessible navigation and authenticated account management.', 'Analyzed unrelated data.']
    draft.bullets = [v4.ResumeBullet(id=f'B{i}', record_id='R1', evidence_ids=[f'X{i}'], requirement_ids=['Q1', 'Q2', 'Q3', 'Q4'] if i == 0 else ['Q3'] if i == 1 else [], text=text) for i, text in enumerate(texts)]
    for i, text in enumerate(texts):
        projection['claims'].append({'id': f'X{i}', 'record_id': 'R1', 'text': text})
    for a in draft.assessments:
        a.full_claim_ids = ['X1'] if a.requirement_id == 'Q3' else []
        a.partial_claim_ids = ['X0']
    bounded = v5.budget(draft, projection)
    assert [b.id for b in bounded.bullets] == ['B0', 'B1']
    assert bounded.coverage[2].status == 'supported'


def test_space_omission_preserves_available_support(monkeypatch):
    projection, draft = example()
    monkeypatch.setitem(v5.POLICY, 'max_bullets', 1)
    draft.bullets.append(v4.ResumeBullet(id='B2', record_id='R1', evidence_ids=['C2'], requirement_ids=['Q3'], text=projection['claims'][1]['text']))
    bounded = v5.budget(draft, projection)
    assert bounded.coverage[2].status == 'supported'
    assert bounded.coverage[3].status == 'not_included'
    assert bounded.coverage[3].available_support == 'partial'
