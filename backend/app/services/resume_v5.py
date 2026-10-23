"""V5 evidence guardrails and deterministic page-budget selection.

These conservative lexical checks prevent known overstatements; they are not a
general entailment engine. The real PDF renderer remains the page-fit authority.
"""
import math
import re
from app.services import resume_v4 as v4

POLICY = {'version': 1, 'estimated_page_points': 670, 'max_bullets': 10, 'max_skills': 12}


def atomic_errors(requirements):
    groups = {
        'AI agents': r'\b(?:ai |autonomous )?agents?\b',
        'backend services': r'\bbackend (?:services?|systems?)\b',
        'APIs': r'\bapis?\b',
        'web interfaces': r'\b(?:web (?:uis?|user interfaces?)|front[- ]?end interfaces?)\b',
    }
    errors = []
    for req in requirements:
        facets = [name for name, pattern in groups.items() if re.search(pattern, req.description, re.I)]
        if len(facets) > 1:
            errors.append(f'Requirement {req.id} combines independently assessed capabilities ({", ".join(facets)}). Split into separate requirement entries with grounded excerpts; sharing the original sentence is allowed.')
    return errors


def guard_reason(requirement, claim):
    requirement = requirement.casefold()
    text = claim['text'].casefold()
    if re.search(r'\b(?:eval(?:uation)?|benchmark)(?:[- ]\w+)? (?:pipelines?|harness(?:es)?|suites?)\b', requirement):
        if (not re.search(r'\b(?:eval(?:uation)?|benchmark\w*)\b', text)
                or not re.search(r'\b(?:pipeline|harness|suite|workflow)\w*\b', text)
                or re.search(r'\b(?:no|not|without|planned)\b.{0,35}\b(?:eval|evaluation|benchmark)', text)):
            return 'Validation/testing alone does not establish an evaluation pipeline.'
    if re.search(r'\bproduction\b|\breal (?:customers|users)\b', requirement):
        if (not re.search(r'\bproduction\b|\b(?:paying|real|external) (?:customers|users)\b', text)
                or re.search(r'\b(?:prototype|demo|local[- ]only|locally running|internal testing)\b|\b(?:not|no|without)\b.{0,25}\bproduction\b', text)):
            return 'A demo, deployment or internal tool alone does not establish production use.'
        if re.search(r'\bown\w*\b|\bend.to.end\b', requirement) and not re.search(r'\bown(?:ed|ership)?\b|\bled\b|\bend.to.end\b', text):
            return 'Production use alone does not establish ownership.'
    duration = re.search(r'(\d+)(?:\s*[-\u2013\u2014]\s*\d+|\+)?\s*years?', requirement)
    if duration:
        actual = re.search(r'(\d+)(?:\+)?\s*years?', text)
        if not actual or int(actual[1]) < int(duration[1]):
            return 'Selected accomplishment evidence does not establish the requested experience duration.'
        if 'professional' in requirement and not re.search(r'\bprofessional\b|\bemployed\b', text):
            return 'Project duration alone does not establish professional experience duration.'
        if re.search(r'full[- ]stack', requirement) and not re.search(r'full[- ]stack', text):
            return 'General software experience does not establish the requested full-stack duration.'
    return None


def guarded_assessments(requirements, assessments, projection):
    claims = {c['id']: c for c in projection['claims']}
    reqs = {r.id: r for r in requirements}
    result = []
    for original in assessments:
        a = original.model_copy(deep=True)
        reasons = []
        for cid in original.full_claim_ids:
            req, claim = reqs.get(a.requirement_id), claims.get(cid)
            reason = guard_reason(req.description, claim) if req and claim else None
            if reason:
                a.full_claim_ids.remove(cid)
                if cid not in a.partial_claim_ids:
                    a.partial_claim_ids.append(cid)
                reasons.append(reason)
        if reasons:
            # The model's old full-support explanation must not contradict the
            # effective classification. Original wording remains in plan metadata.
            a.explanation = 'Partial support after source checks: ' + ' '.join(dict.fromkeys(reasons))
        result.append(a)
    return result


def apply_guards(draft, projection):
    draft.assessments = guarded_assessments(draft.requirements, draft.assessments, projection)
    for b in draft.bullets:
        b.requirement_ids = [a.requirement_id for a in draft.assessments if set(b.evidence_ids).intersection(a.full_claim_ids + a.partial_claim_ids)]
    return v4.refresh_coverage(draft, projection)


def estimate(draft, projection):
    """Conservative line/heading estimate for the owned 11pt letter layout.

    Count complete words and record overhead; don't treat bullet count as fit.
    Identity/contact reserve includes up to four header lines. Actual glyph widths,
    project URLs and TeX wrapping are verified by the normal render/approval flow.
    """
    def lines(text, width=85):
        return max(1, math.ceil(len(text) / width))
    records = {r['id']: r for r in projection['records']}
    points = 95 + 26 + sum(14 * (2 + max(0, lines(str(e), 160)-2)) for e in projection.get('education', []))
    points += 26 + 14 * max(1, lines(', '.join(s.name for s in draft.skills), 75))
    selected = {b.record_id for b in draft.bullets}
    kinds = {records.get(r, {}).get('kind', 'employment') for r in selected}
    points += 26 * len(kinds)
    for rid in selected:
        record = records.get(rid, {})
        points += 56 if record.get('kind') == 'project' else 32
        heading = ' '.join(str(record.get(k, '')) for k in ('employer', 'title_display', 'name'))
        points += max(0, lines(heading, 85)-1) * 14
    points += sum(lines(b.text, 85) * 14 + 6 for b in draft.bullets)
    return points


def words(text):
    stop = {'a', 'an', 'the', 'and', 'or', 'for', 'with', 'to', 'of', 'in', 'on', 'built', 'developed', 'implemented', 'using'}
    return {w for w in re.findall(r'[a-z0-9]+', text.casefold()) if w not in stop}


def budget(draft, projection):
    """Greedy evidence coverage per space, with repetition and record costs.

    Only selects whole, already-authorized claims. Never adds facts or rewrites
    clauses. Omitted claims remain available in the source coverage assessment.
    """
    result = draft.model_copy(deep=True)
    original = list(result.bullets)
    result.bullets = []
    # Prefer skills explicitly requested; preserve original order for ties.
    requested = ' '.join(r.description for r in result.requirements).casefold()
    result.skills = sorted(result.skills, key=lambda s: s.name.casefold() not in requested)[:POLICY['max_skills']]
    remaining = list(original)
    covered = set()
    while remaining and len(result.bullets) < POLICY['max_bullets']:
        ranked = []
        for index, bullet in enumerate(remaining):
            tokens = words(bullet.text)
            similarity = max((len(tokens & words(b.text)) / max(1, len(tokens | words(b.text)))
                              for b in result.bullets if b.record_id == bullet.record_id), default=0)
            if similarity >= .65:
                continue
            full = {a.requirement_id for a in result.assessments if set(bullet.evidence_ids).intersection(a.full_claim_ids)}
            partial = {a.requirement_id for a in result.assessments if set(bullet.evidence_ids).intersection(a.partial_claim_ids)}
            score = 2 + 5 * len(full - covered) + 2 * len(partial - covered) + len(full)
            score += 1 if re.search(r'\d', bullet.text) else 0
            trial = result.model_copy(deep=True)
            trial.bullets.append(bullet)
            cost = max(1, estimate(trial, projection) - estimate(result, projection))
            ranked.append((score * (1-similarity) / cost, -index, bullet, trial))
        if not ranked:
            break
        ranked.sort(key=lambda item: item[:2], reverse=True)
        chosen = next((item for item in ranked if estimate(item[3], projection) <= POLICY['estimated_page_points']), None)
        if chosen is None:
            break
        bullet = chosen[2]
        result.bullets.append(bullet)
        covered.update(bullet.requirement_ids)
        remaining.remove(bullet)
    if not result.bullets and original:
        # Keep the strongest recoverable claim. A validation finding requires a
        # shorter approved alternative rather than silently producing no resume.
        result.bullets = [min(original, key=lambda b: len(b.text))]
    # Layout order remains the author's selection priority within each record.
    retained = {b.id for b in result.bullets}
    result.bullets = [b for b in original if b.id in retained]
    return v4.refresh_coverage(result, projection)


def budget_report(draft, projection):
    points = estimate(draft, projection)
    return {'policy_version': 1, 'estimated_points': points, 'target_points': POLICY['estimated_page_points'],
            'bullets': len(draft.bullets), 'max_bullets': POLICY['max_bullets'],
            'within_budget': points <= POLICY['estimated_page_points'] and len(draft.bullets) <= POLICY['max_bullets'] and len(draft.skills) <= POLICY['max_skills'],
            'actual_page_fit': 'Requires PDF rendering; this is an estimate.'}


def compile_plan(plan, data):
    from app.services.resume_composition import compile_plan as compile_previous
    legacy_data = {**data, 'contract': {**data['contract'], 'composition_version': 2}}
    output = compile_previous(plan, legacy_data)
    if data['stage'] != 'polish':
        draft = output.draft if hasattr(output, 'draft') else output
        apply_guards(draft, data['approved_evidence'])
        bounded = budget(draft, data['approved_evidence'])
        if hasattr(output, 'draft'):
            output.draft = bounded
            retained = {b.id for b in bounded.bullets}
            output.lineage = [entry for entry in output.lineage if entry.bullet_id in retained]
        else:
            output = bounded
    return output
