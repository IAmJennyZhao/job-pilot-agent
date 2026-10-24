"""Fictional four-pass provider; no network or private source files."""
import json
from app.generation_schemas import ResumeDraft, CritiqueReport, RevisedResume, PolishedResume


def current_draft(draft, data):
    if data.get('contract', {}).get('composition_version') not in (2, 3):
        return draft
    from app.services.resume_v4 import DraftV4, refresh_coverage
    value = draft.model_dump()
    value['requirements'] = [{**r, 'kind': 'basic_skill' if r['quote'] == 'Python' else 'experience',
                              'skill_name': 'Python' if r['quote'] == 'Python' else None} for r in value['requirements']]
    value['assessments'] = [{'requirement_id': r['id'],
        'full_claim_ids': [cid for b in draft.bullets if r['id'] in b.requirement_ids for cid in b.evidence_ids],
        'partial_claim_ids': [], 'explanation': 'Synthetic fixture evidence assessment.'} for r in value['requirements']]
    value['coverage'] = []
    return refresh_coverage(DraftV4.model_validate(value), data['approved_evidence'])


def fake_generation(output_model, system, payload, *, model, timeout):
    data = json.loads(payload)
    if data['stage'] in ('write', 'review'):
        from app.services import resume_v6 as policy
        metadata = {"model": model, "usage": {"input_tokens": 100, "output_tokens": 50}, "latency_ms": 1}
        if data['stage'] == 'write':
            claim = data['approved_evidence']['claims'][0]
            plan = policy.WriterPlan(bullets=[{'record_id': claim['record_id'], 'text': claim['text'], 'evidence_ids': [claim['id']]}], skills=['Python'])
            metadata.update(composition_plan=plan.model_dump(), composition_version=4)
            return policy.compile_plan(plan, data), metadata
        return policy.Advisory(findings=[{'bullet_id': b['bullet_id'], 'verdict': 'supported', 'explanation': 'Supported by the cited source.'} for b in data['bullets']]), metadata
    evidence = data["approved_evidence"]
    previous = data["prior_outputs"]
    if issubclass(output_model, ResumeDraft):
        claim = evidence["claims"][0]
        output = ResumeDraft(requirements=[{"id": "REQ-1", "quote": "Python", "description": "Python development"}],
            bullets=[{"id": "B-1", "record_id": claim["record_id"], "evidence_ids": [claim["id"]], "requirement_ids": ["REQ-1"], "text": claim["text"]}],
            skills=[{"name": "Python", "source_ids": ["SK-1"]}], unmet_requirement_ids=[], change_summary=["Selected supported Python work."])
        output = current_draft(output, data)
    elif issubclass(output_model, CritiqueReport):
        output = CritiqueReport(issues=[{"issue_id": "I-1", "severity": "improvement", "field_path": "bullets.B-1",
            "requirement_ids": ["REQ-1"], "evidence_ids": [evidence["claims"][0]["id"]], "finding": "Keep wording direct.",
            "proposed_action": "Preserve the supported implementation detail.", "requires_user_fact_confirmation": False}])
        if data.get('contract', {}).get('composition_version') in (2, 3):
            output = output_model(**output.model_dump(), assessment_corrections=[])
    elif issubclass(output_model, RevisedResume):
        output = output_model(draft=previous["select"], decisions=[{"issue_id": "I-1", "action": "accepted", "reason": "The supported wording is already concise."}])
    elif issubclass(output_model, PolishedResume):
        from app.services.resume_v4 import DraftV4
        draft = (DraftV4 if data.get('contract', {}).get('composition_version') in (2, 3) else ResumeDraft).model_validate(previous["revise"]["draft"])
        edits = []
        for bullet in draft.bullets:
            text = bullet.text.replace("Successfully ", "").replace("successfully ", "")
            if text != bullet.text:
                edits.append({"bullet_id": bullet.id, "before": bullet.text, "after": text})
                bullet.text = text
        output = output_model(draft=draft, edits=edits)
    else:
        raise AssertionError("Unknown generation contract")
    return output, {"model": model, "usage": {"input_tokens": 100, "output_tokens": 50}, "latency_ms": 1}
