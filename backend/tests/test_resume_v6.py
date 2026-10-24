"""Simple writing acceptance with deterministic providers, never live quality claims."""
import copy
import hashlib
import json
from types import SimpleNamespace
from datetime import timedelta
import pytest
from sqlalchemy import delete, select
from app import models
from app.database import get_db
from app.main import app
from app.services import ai_service, resume_generation as runs, resume_v6 as policy
from app.services.tailoring_provider import ProviderFailure
from generation_fixtures import fake_generation
from test_resume_generation import prepared, generate
from test_resume_review import save_payload, approval_payload


@pytest.fixture
def simple(prepared, pin_generation_version):
    pin_generation_version(6)
    return prepared[0]


def restore(client, archive):
    raw = json.dumps(archive).encode()
    return client.post('/api/data/restore', files={'file': ('backup.json', raw)},
        data={'sha256': hashlib.sha256(raw).hexdigest(), 'confirmation': 'RESTORE'})


def test_simple_writer_compiles_provenance_and_uses_focused_review(client, simple, monkeypatch):
    calls = []
    def provider(output_model, system, payload, **kwargs):
        data = json.loads(payload)
        calls.append(data)
        output, meta = fake_generation(output_model, system, payload, **kwargs)
        if data['stage'] == 'write':
            plan = policy.WriterPlan.model_validate(meta['composition_plan'])
            plan.bullets[0].text = 'Prototyped an internal tool in Python.'
            output = policy.compile_plan(plan, data)
            meta['composition_plan'] = plan.model_dump()
        return output, meta
    monkeypatch.setattr(ai_service, 'get_tailoring_output', provider)
    run = generate(client, simple).json()
    assert run['state'] == 'completed', run
    assert [c['stage'] for c in calls] == ['write', 'review']
    assert not {'job', 'approved_evidence', 'prior_outputs'} & calls[1].keys()
    assert len(calls[1]['bullets'][0]['evidence']) == 1
    content = run['revision']['content']
    assert content['draft']['bullets'][0]['text'] == 'Prototyped an internal tool in Python.'
    assert content['draft']['requirements'] == []
    assert run['revision']['validation']['valid']
    assert content['advisory_review']['status'] == 'available'
    assert restore(client, client.get('/api/data/backup').json()).status_code == 200


def test_real_provider_boundary_compiles_writer_plan_and_repairs_bad_reference(client, simple, monkeypatch):
    from app.services import tailoring_provider as provider
    calls = []
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs['max_retries'] == 0
            self.responses = self
        async def parse(self, **kwargs):
            data, schema = json.loads(kwargs['input']), kwargs['text_format']
            calls.append(data['stage'])
            assert kwargs['store'] is False
            if schema is policy.WriterPlan:
                claim = data['approved_evidence']['claims'][0]
                output = schema(bullets=[{'record_id': claim['record_id'], 'evidence_ids': [claim['id'] if data['repair'] else 'excluded-id'],
                    'text': 'Prototyped an internal tool in Python.'}], skills=['Python'])
            else:
                assert schema is policy.Advisory
                output = schema(findings=[{'bullet_id': b['bullet_id'], 'verdict': 'uncertain', 'explanation': 'Review this paraphrase.'} for b in data['bullets']])
            return SimpleNamespace(output=[], status='completed', output_parsed=output, id='fixture', model='fixture', usage=None)
    monkeypatch.setattr(provider, 'AsyncOpenAI', FakeClient)
    monkeypatch.setattr(ai_service, 'get_tailoring_output', provider.get_tailoring_output)
    run = generate(client, simple).json()
    assert run['state'] == 'completed', run
    assert calls == ['write', 'write', 'review']
    assert run['stages'][1]['metadata']['composition_version'] == 4
    assert run['revision']['validation']['valid']
    assert restore(client, client.get('/api/data/backup').json()).status_code == 200


@pytest.mark.parametrize('mode', ['concern', 'timeout', 'wrong_ids', 'unexpected'])
def test_advisory_never_discards_or_rewrites_draft(client, simple, monkeypatch, mode):
    def provider(output_model, system, payload, **kwargs):
        if output_model is policy.Advisory:
            if mode == 'timeout':
                raise ProviderFailure('Synthetic timeout')
            if mode == 'unexpected':
                raise RuntimeError('Synthetic interruption')
            value, meta = fake_generation(output_model, system, payload, **kwargs)
            value.findings[0].verdict = 'concern'
            if mode == 'wrong_ids':
                value.findings[0].bullet_id = 'missing'
            return value, meta
        return fake_generation(output_model, system, payload, **kwargs)
    monkeypatch.setattr(ai_service, 'get_tailoring_output', provider)
    run = generate(client, simple).json()
    assert run['state'] == 'completed', run
    assert run['revision']['content']['draft'] == run['stages'][0]['output']
    advisory = run['revision']['content']['advisory_review']
    assert advisory['status'] == ('available' if mode == 'concern' else 'unavailable')
    url = f"/api/tailoring/resumes/{run['revision']['id']}"
    view = client.get(url).json()
    assert view['approval_eligible'] and view['advisory_current']
    assert client.post(url + '/review', json=approval_payload(view)).status_code == 201
    archived = client.get('/api/data/backup').json()
    assert restore(client, archived).status_code == 200
    archived['tables']['tailored_revisions'][0]['content']['advisory_review']['findings'] = []
    if mode == 'concern':
        assert restore(client, archived).status_code == 400


def test_factual_failure_is_editable_and_advisory_becomes_stale(client, simple, monkeypatch):
    def provider(output_model, system, payload, **kwargs):
        value, meta = fake_generation(output_model, system, payload, **kwargs)
        if output_model is policy.Draft:
            value.bullets[0].text = 'Built a Python tool for 900 users.'
            meta.pop('composition_plan')  # Direct parsed-output fixture.
        return value, meta
    monkeypatch.setattr(ai_service, 'get_tailoring_output', provider)
    run = generate(client, simple).json()
    assert run['state'] == 'completed' and not run['revision']['validation']['valid']
    url = f"/api/tailoring/resumes/{run['revision']['id']}"
    view = client.get(url).json()
    assert not view['approval_eligible']
    assert client.post(url + '/review', json=approval_payload(view)).status_code == 409
    assert client.post(url + '/renders', json=approval_payload(view)).status_code == 409
    monkeypatch.setattr(ai_service, 'get_tailoring_output', lambda *a, **k: pytest.fail('Editing must not call AI'))
    payload = save_payload(view)
    payload['edit']['bullets'][0]['text'] = 'Prototyped an internal tool in Python.'
    result = client.post(url + '/revisions', json=payload)
    assert result.status_code == 201, result.text
    edited = result.json()
    assert edited['approval_eligible'] and not edited['advisory_current']
    assert edited['revision']['content']['advisory_review'] == view['revision']['content']['advisory_review']
    assert client.post(url + '/review', json=approval_payload(edited)).status_code == 201
    assert restore(client, client.get('/api/data/backup').json()).status_code == 200


def test_writer_structural_repair_is_bounded(client, simple, monkeypatch):
    calls = []
    def provider(*args, **kwargs):
        data = json.loads(args[2]); calls.append(data)
        raise ProviderFailure('Bullet references unavailable record evidence: bad-id.', repairable=True)
    monkeypatch.setattr(ai_service, 'get_tailoring_output', provider)
    run = generate(client, simple).json()
    assert run['state'] == 'failed' and not run['revision']
    assert len(calls) == 2 and 'bad-id' in calls[1]['repair']['findings'][0]
    assert restore(client, client.get('/api/data/backup').json()).status_code == 200


def test_deadline_recovers_writer_checkpoint_without_ai(client, simple, monkeypatch):
    run = generate(client, simple).json()
    dependency = app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        db.execute(delete(models.TailoredRevision).where(models.TailoredRevision.run_id == run['id']))
        review = db.scalar(select(models.TailoringStageAttempt).where(models.TailoringStageAttempt.run_id == run['id'], models.TailoringStageAttempt.stage == 'review'))
        review.state, review.output_data, review.output_hash, review.validation = 'running', None, None, None
        row = db.get(models.TailoringRun, run['id'])
        row.state, row.active_key, row.deadline_at = 'running', f'{row.profile_id}:{row.job_id}:resume', runs.now() - timedelta(seconds=1)
        db.commit()
    finally:
        dependency.close()
    monkeypatch.setattr(ai_service, 'get_tailoring_output', lambda *a, **k: pytest.fail('Recovery must not call AI'))
    recovered = client.get(f"/api/jobs/{simple['id']}/tailoring").json()['runs'][0]
    assert recovered['state'] == 'completed'
    recovered = client.get(f"/api/tailoring/runs/{run['id']}").json()
    assert recovered['revision']['content']['advisory_review']['status'] == 'unavailable'
    assert restore(client, client.get('/api/data/backup').json()).status_code == 200


@pytest.mark.parametrize(('text', 'valid'), [
    ('Collaborated on a read-only Python prototype; reduced runtime from 6 hours to 1.2 hours in internal testing.', True),
    ('Collaborated on a read-only Python prototype; reduced runtime from 6.0 to 1.2 hours in internal testing.', True),
    ('Collaborated on a read-only Python prototype; reduced runtime from 6 to 1.2 minutes in internal testing.', False),
    ('Collaborated on a read-only Python prototype; reduced runtime by 99% in internal testing.', False),
    ('Collaborated on a read-only Python prototype; reduced runtime from 6 to 1.2 hours.', False),
    ('Delivered a Python service in production.', False),
])
def test_focused_guards_allow_paraphrases_but_keep_metrics_and_qualifiers(text, valid):
    projection = {'records': [{'id': 'R'}], 'claims': [{'id': 'C', 'record_id': 'R',
        'text': 'Contributed to a read-only Python prototype that reduced runtime from 6 to 1.2 hours during internal testing.',
        'constraints': ['Preserve internal-testing status and team contribution.']}], 'skill_groups': [], 'technology_catalog': []}
    draft = policy.Draft(bullets=[{'id': 'B', 'record_id': 'R', 'evidence_ids': ['C'], 'requirement_ids': [], 'text': text}], skills=[], change_summary=[])
    errors = policy.factual_errors(draft, projection)
    assert (not errors) == valid, errors
