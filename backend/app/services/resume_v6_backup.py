"""Replay v6 writing and best-effort review without provider calls."""
from app.services import resume_v6 as policy
from app.services.intake_preferences import digest
from app.services.resume_validation import plain_text


def validate_run(tables, run):
    snapshot = run['snapshot']
    versions = {s: f'resume-{s}-v6' for s in policy.STAGES}
    if snapshot['prompt_versions'] != versions or snapshot['prompt_hashes'] != {s: digest(policy.PROMPTS[s]) for s in policy.STAGES}:
        raise ValueError('Unsupported simple-writer prompt version')
    if run['state'] not in {'pending', 'running', 'completed', 'failed', 'interrupted'}:
        raise ValueError('Invalid writer run state')
    expected_key = f"{run['profile_id']}:{run['job_id']}:resume" if run['state'] in {'pending', 'running'} else None
    if run['active_key'] != expected_key:
        raise ValueError('Invalid writer active identity')
    attempts = [a for a in tables['tailoring_stage_attempts'] if a['run_id'] == run['id']]
    if any(a['stage'] not in policy.STAGES for a in attempts):
        raise ValueError('Unknown writer stage')
    accepted = {}
    for stage in policy.STAGES:
        rows = sorted([a for a in attempts if a['stage'] == stage], key=lambda a: a['attempt'])
        for index, a in enumerate(rows, 1):
            if stage in accepted or (stage == 'review' and 'write' not in accepted):
                raise ValueError('Invalid writer stage sequence')
            if index > (2 if stage == 'write' else 1) or a['attempt'] != index or a['prompt_version'] != versions[stage]:
                raise ValueError('Invalid writer attempt identity')
            data = a['input_data']
            if data != policy.stage_input(snapshot, stage, accepted, data.get('repair')) or a['input_hash'] != digest(data):
                raise ValueError('Invalid writer attempt input')
            if a['state'] not in {'running', 'passed', 'failed', 'interrupted'}:
                raise ValueError('Invalid writer attempt state')
            output = a['output_data']
            if a['output_hash'] != (digest(output) if output is not None else None):
                raise ValueError('Invalid writer output hash')
            if output is not None:
                parsed = (policy.Draft if stage == 'write' else policy.Advisory).model_validate(output)
                meta = a['provider_metadata']
                if 'composition_plan' in meta:
                    if stage != 'write' or meta.get('composition_version') != 4:
                        raise ValueError('Invalid writer composition version')
                    if policy.compile_plan(policy.WriterPlan.model_validate(meta['composition_plan']), data).model_dump() != output:
                        raise ValueError('Writer output differs from its composition plan')
                report = policy.validate_stage(stage, parsed, snapshot, accepted)
                if a['validation'] != report or (a['state'] == 'passed' and not report['valid']):
                    raise ValueError('Invalid writer stage validation')
            elif a['state'] == 'passed':
                raise ValueError('Passed writer stage lacks output')
            if a['state'] == 'passed':
                accepted[stage] = output
    revisions = [r for r in tables['tailored_revisions'] if r['run_id'] == run['id']]
    if bool(revisions) != (run['state'] == 'completed') or len(revisions) > 1:
        raise ValueError('Writer completion/revision mismatch')
    for revision in revisions:
        if 'write' not in accepted:
            raise ValueError('Writer revision has no saved draft')
        draft = policy.Draft.model_validate(accepted['write'])
        content = policy.assemble(draft, snapshot, policy.advisory_for(draft, accepted))
        if revision['content'] != content or revision['content_hash'] != digest(content) or revision['plain_text'] != plain_text(content, snapshot) or revision['validation'] != policy.report(draft, snapshot):
            raise ValueError('Writer revision was altered')
