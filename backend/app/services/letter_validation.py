"""Deterministic boundaries plus an independently recorded semantic sentence audit."""
import re
from pydantic import ValidationError
from app.letter_schemas import LetterDraft, LetterAssessment
from app.letter_prompts import VERSION
from app.services.intake_preferences import digest

ANGLES = ["concise professional", "technical contribution", "product/user impact"]
NUMBER = r"(?<!\w)(?:[-+−$€£]\s*)?\d[\d,.]*(?:%|\+)?"


def is_letter(snapshot):
    return snapshot.get("document_kind") == "cover_letter"


def job_evidence(snapshot):
    # Stable, exact excerpts, constructed by trusted code rather than the writer.
    text = snapshot["job"]["source_content"]
    parts = [p.strip() for p in re.split(r"\n+|(?<=[.!?])\s+", text) if p.strip()]
    evidence = [{"id": f"job-{i+1}", "text": p} for i, p in enumerate(parts)]
    context = snapshot["letter_options"].get("company_context")
    if context:
        evidence.append({"id": "company-1", "text": context["text"], "source_url": context["source_url"]})
    return evidence


def sentences(content):
    return [s for v in content["variants"] for p in v["paragraphs"] for s in p["sentences"]]


def editable(content):
    return {"variants": content["variants"]}


def build_content(edit, baseline, snapshot):
    return {"document_kind": "cover_letter", "schema_version": 1, **edit.model_dump(mode="json")}


def text_for(content, snapshot, variant_index=None):
    variants = content["variants"] if variant_index is None else [content["variants"][variant_index]]
    heading = f"Re: {snapshot['job']['role_title']} — {snapshot['job']['company']}"
    return "\n\n---\n\n".join("\n\n".join([heading, "Dear Hiring Team,",
        *[" ".join(s["text"].strip() for s in p["sentences"]) for p in v["paragraphs"]],
        f"Sincerely,\n{snapshot['identity']['name']}"]) for v in variants)


def markdown(text):
    # Encode every punctuation character as an entity: no raw HTML, links or Markdown execution.
    return "".join(f"&#{ord(c)};" if not (c.isalnum() or c.isspace()) else c for c in text)


def differences(before, after):
    old = {s["id"]: s for s in sentences(before)}
    new = {s["id"]: s for s in sentences(after)}
    return [{"field_path": f"sentences.{key}", "before": old.get(key), "after": new.get(key)}
            for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)]


def assessment_payload(content, snapshot):
    claims = {c["id"]: c for c in snapshot["projection"]["claims"]}
    jobs = {c["id"]: c for c in job_evidence(snapshot)}
    records = {r["id"]: r for r in snapshot["projection"]["records"]}
    return {"content_hash": digest(content), "sentences": [{"sentence": s,
        "candidate_sources": [claims[i] for i in s["candidate_evidence_ids"] if i in claims],
        "protected_metrics": [m for m in snapshot["projection"]["protected_metrics"] if m["claim_id"] in s["candidate_evidence_ids"]],
        "record_constraints": [records[r] for r in sorted({claims[i]["record_id"] for i in s["candidate_evidence_ids"] if i in claims}) if r in records],
        "job_sources": [jobs[i] for i in s["job_evidence_ids"] if i in jobs]}
        for s in sentences(content)]}


def validate(content, snapshot, assessment=None):
    issues = []
    def issue(path, message):
        issues.append({"field_path": path, "message": message})
    try:
        parsed = LetterDraft.model_validate(editable(content))
    except (KeyError, TypeError, ValidationError):
        issue("draft", "Invalid letter structure.")
        parsed = None
    claims = {c["id"]: c for c in snapshot["projection"]["claims"]}
    jobs = {c["id"]: c for c in job_evidence(snapshot)}
    if content.get("document_kind") != "cover_letter" or content.get("schema_version") != 1 or set(content) != {"document_kind", "schema_version", "variants"}:
        issue("draft", "Unsupported letter content version.")
    verdicts = {}
    if assessment is not None:
        try:
            checked = LetterAssessment.model_validate(assessment)
            verdicts = {v.sentence_id: v.model_dump() for v in checked.sentences}
            if len(verdicts) != len(checked.sentences):
                issue("evidence", "Duplicate sentence assessments.")
        except ValidationError:
            issue("evidence", "Invalid sentence assessment contract.")
    else:
        issue("evidence", "Run the independent sentence evidence check before review.")
    if parsed:
        options = snapshot["letter_options"]
        if len(parsed.variants) != options["count"] or [v.angle for v in parsed.variants] != ANGLES[:options["count"]]:
            issue("variants", "Variant count and angles must match the saved generation options.")
        if len({v.variant_id for v in parsed.variants}) != len(parsed.variants):
            issue("variants", "Variant IDs must be unique.")
        openings = [v.paragraphs[0].sentences[0].text.casefold().strip() for v in parsed.variants]
        if len(set(openings)) != len(openings):
            issue("variants", "Use distinct openings for each variant.")
        evidence_sets = {tuple(sorted({i for p in v.paragraphs for s in p.sentences for i in s.candidate_evidence_ids})) for v in parsed.variants}
        if len(evidence_sets) < min(len(claims), len(parsed.variants)):
            issue("variants", "Vary the selected candidate evidence across variants when approved sources permit it.")
        low, high = (100, 150) if options["length"] == "short" else (180, 250)
        for v in parsed.variants:
            words = sum(len(s.text.split()) for p in v.paragraphs for s in p.sentences)
            if not low <= words <= high:
                issue(v.variant_id, f"Body has {words} words; {options['length']} letters require {low}–{high}.")
            if not (2 if options["length"] == "short" else 3) <= len(v.paragraphs) <= (3 if options["length"] == "short" else 4):
                issue(v.variant_id, "Use 2–3 short or 3–4 standard paragraphs.")
            if not any(s.candidate_evidence_ids for p in v.paragraphs for s in p.sentences):
                issue(v.variant_id, "Include specific approved candidate evidence in each variant.")
            if not any(s.job_evidence_ids for p in v.paragraphs for s in p.sentences):
                issue(v.variant_id, "Connect each variant to cited posting or company context.")
        all_sentences = sentences(content)
        ids = [s["id"] for s in all_sentences]
        if len(set(ids)) != len(ids):
            issue("sentences", "Sentence IDs must be globally unique.")
        if assessment is not None and set(verdicts) != set(ids):
            issue("evidence", "The assessment must cover every sentence exactly once.")
        for s in all_sentences:
            path = f"sentences.{s['id']}"
            candidate_ids, job_ids = s["candidate_evidence_ids"], s["job_evidence_ids"]
            if any(i not in claims for i in candidate_ids) or any(i not in jobs for i in job_ids):
                issue(path, "Unknown or excluded evidence reference.")
            if len(set(candidate_ids)) != len(candidate_ids) or len(set(job_ids)) != len(job_ids):
                issue(path, "Duplicate evidence references.")
            if s["sentence_kind"] == "candidate_claim" and not candidate_ids:
                issue(path, "Candidate claims require approved candidate evidence.")
            if s["sentence_kind"] == "job_context" and not job_ids:
                issue(path, "Company and role facts require job evidence.")
            if re.search(r"[\x00-\x1f<>]|https?://|\[[^\]]+\]\(|```", s["text"]):
                issue(path, "Use plain sentence text without markup, links or control characters.")
            protected = [snapshot["identity"]["name"]]
            for record in snapshot["projection"]["records"]:
                protected.extend(record.get(k) for k in ("employer", "title_display", "name", "dates_display") if record.get(k))
            for education in snapshot["projection"]["education"]:
                protected.extend(education.get(k) for k in ("institution", "degree", "graduation_display") if education.get(k))
            if any(re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", s["text"], re.I) for value in protected):
                issue(path, "Keep protected names, titles, education and dates in trusted metadata; describe the supported work in the body.")
            source_text = " ".join(claims[i]["text"] for i in candidate_ids if i in claims) + " " + " ".join(jobs[i]["text"] for i in job_ids if i in jobs)
            for number in re.findall(NUMBER, s["text"]):
                if number not in re.findall(NUMBER, source_text):
                    issue(path, "Numeric claims must preserve a cited source's values and units.")
            for tech in snapshot["projection"]["technology_catalog"]:
                names = [tech["name"], *tech.get("aliases", [])]
                mentioned = any(re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", s["text"], re.I) for n in names)
                if mentioned and s["sentence_kind"] == "candidate_claim" and not set(candidate_ids).intersection(tech["claim_ids"]):
                    issue(path, "Technology experience must be supported by the cited accomplishment.")
            verdict = verdicts.get(s["id"])
            if not verdict:
                continue
            if not verdict["supported"] or verdict["actual_kind"] != s["sentence_kind"]:
                issue(path, verdict["explanation"])
            proven = set()
            for support in verdict["supports"]:
                candidate = support["source_kind"] == "candidate"
                catalog, references = (claims, candidate_ids) if candidate else (jobs, job_ids)
                source = catalog.get(support["source_id"])
                if support["source_id"] not in references or not source or not support["quote"].strip() or support["quote"] not in source["text"]:
                    issue(path, "The semantic check cited text outside this sentence's evidence.")
                else:
                    proven.add(support["source_kind"])
            if (candidate_ids or verdict["actual_kind"] == "candidate_claim") and "candidate" not in proven:
                issue(path, "The semantic check must quote supporting candidate evidence.")
            if (job_ids or verdict["actual_kind"] == "job_context") and "job" not in proven:
                issue(path, "The semantic check must quote supporting job evidence.")
    return {"validator_version": VERSION, "valid": not issues, "issues": issues,
        "validated_content_hash": digest(content), "input_hash": digest(snapshot),
        "assessment_hash": digest(assessment) if assessment is not None else None,
        "human_review_required": True, "unmet_requirement_ids": [],
        "scope": "Sentence evidence checks compare prose with approved sources; human review remains required. Sources are not independently verified."}
