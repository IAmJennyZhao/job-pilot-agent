"""Fictional regressions for omissions, duplicate gaps and skill-only coverage."""
import copy
import pytest
import json
from types import SimpleNamespace
from pydantic import ValidationError
from app.services import resume_v4 as v4
from app.services.resume_composition import CompositionError
from test_resume_generation import prepared, generate


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


def test_distinct_qualifications_may_share_a_posting_sentence():
    projection, draft = example()
    draft.requirements[1].quote = draft.requirements[2].quote = 'Kubernetes and public application experience'
    assert v4.coverage_errors(draft, projection) == []


def test_selection_schema_excludes_record_ids_from_claim_evidence():
    projection, draft = example()
    schema = v4.selection_model(projection)
    payload = {'requirements': draft.requirements, 'assessments': [a.model_dump() for a in draft.assessments], 'selections': [{'claim_id': 'C1'}], 'skills': draft.skills}
    assert schema.model_validate(payload)
    payload['assessments'][0]['partial_claim_ids'] = ['R1']
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_gap_judgments_belong_in_assessments_not_duplicate_requirements():
    projection, draft = example()
    draft.requirements[1].description = 'No approved evidence supports Kubernetes.'
    assert any('evidence gap' in e for e in v4.coverage_errors(draft, projection))


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


def test_accepted_coverage_correction_is_applied_locally_and_cannot_be_ignored():
    from app.services.resume_composition import compile_plan
    from app.services.resume_validation import validate_stage
    projection, draft = example()
    draft.assessments[3].full_claim_ids = ['C1']
    draft.assessments[3].partial_claim_ids = []
    v4.refresh_coverage(draft, projection)
    issue = {'issue_id': 'I1', 'severity': 'blocking', 'field_path': 'draft', 'requirement_ids': ['Q4'],
        'evidence_ids': ['C1'], 'finding': 'Internal checks do not prove production services.',
        'proposed_action': 'Downgrade to partial support.', 'requires_user_fact_confirmation': False}
    critique = v4.CritiqueV4(issues=[issue], assessment_corrections=[{'issue_id': 'I1', 'requirement_id': 'Q4',
        'full_claim_ids': [], 'partial_claim_ids': ['C1'], 'explanation': 'Internal Python checks are adjacent to production services.'}])
    prior = {'select': draft.model_dump(), 'critique': critique.model_dump()}
    data = {'contract': {'composition_version': 2}, 'approved_evidence': projection, 'prior_outputs': prior}
    snapshot = {'generation_version': 4, 'projection': projection, 'job': {'source_content': '\n'.join(r.quote for r in draft.requirements)}}
    assert validate_stage('critique', critique, snapshot, prior)['valid']
    plan = v4.RevisionPlanV4(selections=[{'claim_id': 'C1', 'issue_ids': []}], skills=draft.skills,
        decisions=[{'issue_id': 'I1', 'action': 'accepted', 'reason': 'Apply the correction.'}])
    result = compile_plan(plan, data)
    assert result.draft.coverage[3].status == 'partially_supported'
    assert validate_stage('revise', result, snapshot, prior)['valid']
    result.draft.assessments = draft.assessments
    v4.refresh_coverage(result.draft, projection)
    report = validate_stage('revise', result, snapshot, prior)
    assert any('apply every accepted' in e for e in report['blocking_issues'])


def test_critique_corrections_cannot_invent_evidence_or_target_unrelated_issues():
    from app.services.resume_validation import validate_stage
    projection, draft = example()
    snapshot = {'generation_version': 4, 'projection': projection, 'job': {'source_content': '\n'.join(r.quote for r in draft.requirements)}}
    critique = v4.CritiqueV4(issues=[], assessment_corrections=[{'issue_id': 'UNKNOWN', 'requirement_id': 'Q1',
        'full_claim_ids': ['EXCLUDED'], 'partial_claim_ids': [], 'explanation': 'Invalid.'}])
    report = validate_stage('critique', critique, snapshot, {'select': draft.model_dump()})
    assert not report['valid'] and len(report['blocking_issues']) == 2


def test_v4_provider_review_edit_render_backup_and_polish_repair(client, prepared, monkeypatch, tmp_path):
    from app.config import get_settings
    from app.services import ai_service, tailoring_provider as provider
    from app.generation_schemas import CritiqueReport
    from test_resume_review import save_payload
    from test_resume_exports import rendered, final
    import hashlib
    job, _ = prepared
    monkeypatch.setattr(get_settings(), 'asset_storage_dir', str(tmp_path))
    client.patch(f"/api/jobs/{job['id']}", json={'source_content': 'Python proficiency. Build internal Python checks. Kubernetes experience.'})
    calls = []
    class FakeClient:
        def __init__(self, **kwargs): self.responses = self
        async def parse(self, **kwargs):
            data, schema = json.loads(kwargs['input']), kwargs['text_format']
            calls.append(data['stage'])
            if issubclass(schema, v4.SelectionPlanV4):
                output = schema(requirements=[
                    {'id': 'Q1', 'quote': 'Python proficiency', 'description': 'Python proficiency', 'kind': 'basic_skill', 'skill_name': 'Python'},
                    {'id': 'Q2', 'quote': 'Build internal Python checks', 'description': 'Internal Python checks', 'kind': 'experience', 'skill_name': None},
                    {'id': 'Q3', 'quote': 'Kubernetes experience', 'description': 'Kubernetes experience', 'kind': 'experience', 'skill_name': None}],
                    assessments=[{'requirement_id': f'Q{i}', 'full_claim_ids': ['C-ALLOWED'] if i == 2 else [], 'partial_claim_ids': [], 'explanation': 'Fixture support.'} for i in (1, 2, 3)],
                    selections=[{'claim_id': 'C-ALLOWED'}], skills=[{'name': 'Python', 'source_ids': ['SK-1']}])
            elif schema is v4.CritiqueV4:
                output = schema(issues=[], assessment_corrections=[])
            elif issubclass(schema, v4.RevisionPlanV4):
                output = schema.model_validate(data['contract']['revision_seed'])
            else:
                assert schema is v4.PolishPlan
                bullet = data['prior_outputs']['revise']['draft']['bullets'][0]
                output = schema(edits=[{'bullet_id': bullet['id'] if data['repair'] else 'UNKNOWN',
                    'replacement_text': bullet['text'].replace('Successfully ', '')}])
            return SimpleNamespace(output=[], status='completed', output_parsed=output, id='fictional', model='fictional', usage=None)
    monkeypatch.setattr(provider, 'AsyncOpenAI', FakeClient)
    monkeypatch.setattr(ai_service, 'get_tailoring_output', provider.get_tailoring_output)
    run = generate(client, job).json()
    assert run['state'] == 'completed', run
    assert calls == ['select', 'critique', 'revise', 'polish', 'polish']
    assert run['stages'][-1]['metadata']['composition_plan'] == {'edits': [{'bullet_id': run['revision']['content']['draft']['bullets'][0]['id'], 'replacement_text': 'built an internal Python prototype.'}]}
    assert all(s['metadata']['composition_version'] == 2 for s in run['stages'] if 'composition_plan' in s['metadata'])
    draft = run['revision']['content']['draft']
    assert [c['status'] for c in draft['coverage']] == ['supported', 'supported', 'unsupported']
    assert len(draft['requirements']) == 3 and draft['unmet_requirement_ids'] == ['Q3']
    url = f"/api/tailoring/resumes/{run['revision']['id']}"
    view = client.get(url).json()
    edit = save_payload(view)
    edit['edit']['skills'] = []
    edited = client.post(url + '/revisions', json=edit).json()
    assert edited['revision']['validation']['valid']
    assert edited['revision']['content']['draft']['coverage'][0]['status'] == 'not_included'
    assert edited['revision']['content']['draft']['unmet_requirement_ids'] == ['Q3']
    monkeypatch.setattr(ai_service, 'get_tailoring_output', lambda *a, **k: pytest.fail('Read/export called model'))
    view, render = rendered(client, url)
    final(client, url, view, render)
    route = url + f"/renders/{render['id']}/download/pdf"
    pdf = client.get(route).content
    raw = client.get('/api/data/backup').content
    result = client.post('/api/data/restore', files={'file': ('backup.json', raw)}, data={'sha256': hashlib.sha256(raw).hexdigest(), 'confirmation': 'RESTORE'})
    assert result.status_code == 200, result.text
    assert client.get(route).content == pdf
    bad = json.loads(raw)
    stage = next(s for s in bad['tables']['tailoring_stage_attempts'] if s['stage'] == 'polish' and s['state'] == 'passed')
    stage['provider_metadata']['composition_plan']['edits'][0]['replacement_text'] = 'Invented production impact.'
    assert client.post('/api/data/restore-preview', files={'file': ('bad.json', json.dumps(bad).encode())}).status_code == 400
