"""Fictional regression for heading/list quotes and typography in all four passes."""
import json
import pytest
from types import SimpleNamespace
from app.generation_schemas import CritiqueReport, RevisedResume, PolishedResume
from app.services.resume_validation import validate_stage, validate_draft
from test_generation_consolidation import example
from test_resume_generation import prepared, generate

POSTING = """Python workflows and recovery.
Experience with:

Agentic AI systems, tools, frameworks and workflows
MCP server patterns
Eval pipelines

We let employees work from where they feel most productive and engaged (must be in the United States).
"""


def case(version=3):
    snapshot, draft = example()
    snapshot['generation_version'] = version
    snapshot['job']['source_content'] = POSTING
    quotes = ['Experience with: Agentic AI systems, tools, frameworks and workflows',
              'Experience with: MCP server patterns', 'Experience with: Eval pipelines',
              'Work from where they feel most productive and engaged (must be in the United States).']
    draft.requirements = [type(draft.requirements[0])(id=f'Q{i+1}', quote=q, description=q) for i, q in enumerate(quotes)]
    draft.unmet_requirement_ids = ['Q2', 'Q3', 'Q4']
    return snapshot, draft


def test_reported_four_quote_mismatches_pass_new_rules_but_keep_old_reports():
    snapshot, draft = case()
    assert validate_draft(draft, snapshot) == []
    snapshot['generation_version'] = 2
    errors = validate_draft(draft, snapshot)
    assert len(errors) == 4 and all('exact posting quote' in e for e in errors)


def test_all_four_passes_share_grounding_and_ignore_quote_only_format_changes():
    snapshot, draft = case()
    accepted = {}
    assert validate_stage('select', draft, snapshot, accepted)['valid']
    accepted['select'] = draft.model_dump()
    critique = CritiqueReport(issues=[])
    assert validate_stage('critique', critique, snapshot, accepted)['valid']
    accepted['critique'] = critique.model_dump()
    revision = RevisedResume(draft=draft.model_copy(deep=True), decisions=[])
    revision.draft.requirements[1].quote = '  EXPERIENCE WITH:\n  MCP server patterns '
    assert validate_stage('revise', revision, snapshot, accepted)['valid']
    accepted['revise'] = revision.model_dump()
    polished = PolishedResume(draft=revision.draft.model_copy(deep=True), edits=[])
    polished.draft.requirements[1].quote = 'Experience with: MCP server patterns'
    assert validate_stage('polish', polished, snapshot, accepted)['valid']
    polished.draft.requirements[1].description = 'Invented qualification'
    assert not validate_stage('polish', polished, snapshot, accepted)['valid']


@pytest.mark.parametrize('source,quote', [
    ('Use Python\n  and\tSQL.', 'use PYTHON and SQL'),
    ('Experience with:\n\n- Python\n- MCP server patterns\n- Eval pipelines', 'Experience with: MCP server patterns'),
    ('Build “read-only” tools — with Python.', 'Build "read-only" tools - with Python.'),
    ('Work with a team’s tools.', "work with a team's tools"),
])
def test_presentation_variations_are_grounded(source, quote):
    from app.services.requirement_grounding import grounded_quote
    assert grounded_quote(quote, source)


@pytest.mark.parametrize('source,quote', [
    ('Python required.', 'Java required.'),
    ('No Kubernetes experience required.', 'Kubernetes experience required for all candidates.'),
    ('3+ years required.', '5+ years required.'),
    ('Work from the United States only.', 'Work from anywhere worldwide.'),
    ('Use C++ and C#.', 'Use C and C.'),
    ('Use Python.', 'Py'),
    ('Experience with:\nPython\n\nOther notes:\nMCP server patterns', 'Experience with: MCP server patterns'),
    ('Python required.', '   '),
])
def test_meaning_changes_and_unrelated_heading_joins_still_fail(source, quote):
    from app.services.requirement_grounding import grounded_quote
    assert not grounded_quote(quote, source)


@pytest.mark.parametrize('stage', ['select', 'critique', 'revise', 'polish'])
def test_unsupported_requirement_is_rejected_at_each_pass(stage):
    snapshot, draft = case()
    draft.requirements[0].quote = 'Invented technology is mandatory.'
    critique = CritiqueReport(issues=[])
    revised = RevisedResume(draft=draft, decisions=[])
    outputs = {'select': draft, 'critique': critique, 'revise': revised, 'polish': PolishedResume(draft=draft, edits=[])}
    accepted = {'select': draft.model_dump(), 'critique': critique.model_dump(), 'revise': revised.model_dump()}
    report = validate_stage(stage, outputs[stage], snapshot, accepted)
    assert not report['valid'] and any('posting' in e for e in report['blocking_issues'])


def test_grounded_quotes_through_provider_all_passes_review_export_and_restore(client, prepared, monkeypatch, tmp_path):
    from app.config import get_settings
    from app.services import ai_service, tailoring_provider as provider
    from app.services.resume_composition import SelectionPlan, RevisionPlan
    from test_resume_exports import rendered, final
    import hashlib
    job, _ = prepared
    client.patch(f"/api/jobs/{job['id']}", json={'source_content': POSTING})
    monkeypatch.setattr(get_settings(), 'asset_storage_dir', str(tmp_path))
    calls = []
    class FakeClient:
        def __init__(self, **kwargs): self.responses = self
        async def parse(self, **kwargs):
            data = json.loads(kwargs['input'])
            schema = kwargs['text_format']
            calls.append(data['stage'])
            assert 'Requirements must quote exact substrings' not in kwargs['instructions']
            if issubclass(schema, SelectionPlan):
                _, draft = case()
                output = schema(requirements=[draft.requirements[0]], unsupported_requirements=draft.requirements[1:],
                    selections=[{'claim_id': 'C-ALLOWED', 'requirement_ids': ['Q1']}], skills=[])
            elif schema is CritiqueReport:
                output = CritiqueReport(issues=[])
            elif issubclass(schema, RevisionPlan):
                output = schema.model_validate(data['contract']['revision_seed'])
            else:
                output = PolishedResume(draft=data['prior_outputs']['revise']['draft'], edits=[])
            return SimpleNamespace(output=[], status='completed', output_parsed=output, id='fixture', model='fixture', usage=None)
    monkeypatch.setattr(provider, 'AsyncOpenAI', FakeClient)
    monkeypatch.setattr(ai_service, 'get_tailoring_output', provider.get_tailoring_output)
    run = generate(client, job).json()
    assert run['state'] == 'completed', run
    assert calls == ['select', 'critique', 'revise', 'polish']
    assert all(s['validation']['validator_version'] == 'resume-v3' for s in run['stages'])
    assert run['revision']['validation']['validator_version'] == 'resume-v3'
    monkeypatch.setattr(ai_service, 'get_tailoring_output', lambda *a, **k: pytest.fail('Read/export/restore called a model'))
    url = f"/api/tailoring/resumes/{run['revision']['id']}"
    view, render = rendered(client, url)
    final(client, url, view, render)
    route = url + f"/renders/{render['id']}/download/pdf"
    original = client.get(route).content
    raw = client.get('/api/data/backup').content
    restored = client.post('/api/data/restore', files={'file': ('backup.json', raw)}, data={'sha256': hashlib.sha256(raw).hexdigest(), 'confirmation': 'RESTORE'})
    assert restored.status_code == 200, restored.text
    assert client.get(route).content == original
