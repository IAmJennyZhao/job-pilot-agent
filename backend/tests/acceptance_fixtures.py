"""Distinct fictional acceptance cases. Deterministic outputs are NOT live AI evaluations."""
import json
import yaml
from app import schemas
from app.generation_schemas import ResumeDraft, CritiqueReport, RevisedResume, PolishedResume
from app.letter_schemas import LetterDraft, LetterAssessment
from app.services.letter_validation import ANGLES
from tailoring_fixtures import bank_data, import_payload
from test_intake_preferences import preferences

CASES = {
    "ai": {"title": "AI Engineer", "company": "Fictional Retrieval Lab", "record": "R-AI", "skills": ["Python"],
        "requirements": ["Build retrieval prototypes in Python.", "Evaluate retrieval quality with synthetic question sets."],
        "gap": "Production model monitoring experience is required.",
        "claims": ["Built a Python retrieval prototype that returned source passages with draft answers.",
                   "Evaluated retrieval relevance on 40 synthetic questions and logged failed matches."],
        "letter_claims": ["I built a retrieval prototype in Python that paired draft answers with their source passages.",
                          "I checked retrieval relevance using forty synthetic questions and recorded the failed matches."],
        "interest": "the relationship between useful generated answers and the evidence available to support them",
        "discussion": "how retrieval quality is assessed and which unanswered questions need further investigation"},
    "backend": {"title": "Backend Engineer", "company": "Fictional Transaction Works", "record": "R-BE", "skills": ["FastAPI", "SQL"],
        "requirements": ["Build reliable FastAPI endpoints.", "Test SQL transactions and concurrent updates."],
        "gap": "Distributed message queue operations experience is required.",
        "claims": ["Implemented FastAPI endpoints with idempotency keys to prevent duplicate fixture requests.",
                   "Added SQL transaction tests for concurrent writes and rollback after failed updates."],
        "letter_claims": ["I used idempotency keys in FastAPI endpoints to keep repeated fixture requests from creating duplicates.",
                          "I tested concurrent SQL writes and checked that failed updates rolled back their transactions."],
        "interest": "the behavior of service boundaries when requests repeat or updates fail partway through",
        "discussion": "how the team defines reliable API behavior and tests the failure paths around it"},
    "fullstack": {"title": "Full-stack Engineer", "company": "Fictional Interface Studio", "record": "R-FS", "skills": ["React", "TypeScript"],
        "requirements": ["Build accessible React forms with TypeScript.", "Connect API submissions and recover unsaved form edits."],
        "gap": "Native iOS development experience is required.",
        "claims": ["Built React forms with TypeScript validation and keyboard-accessible error summaries.",
                   "Connected form submissions to a test API and preserved unsaved edits across reloads."],
        "letter_claims": ["I built forms in React, using TypeScript validation and error summaries that could be reached with a keyboard.",
                          "I connected forms to a test API while keeping unsaved edits available after the page reloaded."],
        "interest": "the details that help people complete a form and recover when their work is interrupted",
        "discussion": "how interface behavior and API contracts are tested together across ordinary and interrupted use"},
}


def posting(key):
    case = CASES[key]
    return "\n".join([f"[acceptance:{key}]", case["title"], *case["requirements"], case["gap"],
        "USD 100000-120000 annual base salary; NYC salary band.", "Remote anywhere including NYC. Minimum 2 years required."])


def case_key(text):
    return next((k for k in CASES if f"[acceptance:{k}]" in text), None)


def bundle():
    bank = bank_data()
    bank["bank_version"] = "fictional-acceptance.1"
    bank["claims"] = [c for c in bank["claims"] if c["id"] == "C-BLOCKED"]
    bank["implementation_profiles"] = []
    bank["technology_catalog"] = []
    bank["skill_groups"] = []
    bank["approval"]["approved_claim_ids"] = []
    for key, case in CASES.items():
        bank["records"].append({"id": case["record"], "kind": "project", "name": f"Fictional {key} project", "source_id": "S-1"})
        ids = [f"C-{key}-{i+1}" for i in range(2)]
        bank["approval"]["approved_claim_ids"].extend(ids)
        for index, text in enumerate(case["claims"]):
            bank["claims"].append({"id": ids[index], "record_id": case["record"], "source_id": "S-1", "text": text,
                "evidence_status": "source_supported", "generation_eligible": True, "technologies": case["skills"],
                "technology_ids": [f"T-{key}-{i}" for i in range(len(case["skills"]))],
                "constraints": ["Fictional test project only; no production deployment or customer impact is established."]})
        bank["skill_groups"].append({"id": f"SK-{key}", "label": "Languages and frameworks", "values": case["skills"], "source_id": "S-1"})
        for index, skill in enumerate(case["skills"]):
            bank["technology_catalog"].append({"id": f"T-{key}-{index}", "name": skill, "aliases": [], "claim_ids": ids,
                "eligible_claim_ids": ids, "listed_skill_group_ids": [f"SK-{key}"], "record_ids": [case["record"]], "relationship": "Used in the fictional project."})
    bank["protected_metrics"].append({"id": "M-AI", "claim_id": "C-ai-2", "display": "40", "unit": "synthetic questions", "constraints": ["Evaluation set size, not accuracy or user count."]})
    result = import_payload(bank)
    result["preferences_yaml"] = yaml.safe_dump(preferences().model_dump(by_alias=True))
    return result


def extraction(key):
    case = CASES[key]
    return schemas.JobExtractionOutput(company=case["company"], role_title=case["title"], summary=case["requirements"][0], confidence=90,
        pay_min=100000, pay_max=120000, pay_currency="USD", pay_period="year",
        preference_facts={field: {"value": value, "origin": "posting", "quote": quote} for field, value, quote in [
            ("salary_component", "base", "USD 100000-120000 annual base salary"), ("salary_band", "applicable", "NYC salary band"),
            ("nyc_compatible", "yes", "Remote anywhere including NYC"), ("required_years", 2, "Minimum 2 years required")]})


def letter(key, count=3, length="standard"):
    case = CASES[key]
    variants = []
    openings = [f"I am interested in this role because it brings attention to {case['interest']}.",
        f"The technical focus of this role interests me, particularly {case['interest']}.",
        f"I would welcome the opportunity to contribute to work concerned with {case['interest']}."]
    excerpts = [p.strip() for p in posting(key).splitlines()]
    # The two facts alone and their combination produce three different evidence selections.
    selections = [[0], [1], [0, 1]]
    for v in range(count):
        entries = [(openings[v], "motivation", [], []),
            (case["requirements"][v % 2], "job_context", [], [f"job-{excerpts.index(case['requirements'][v % 2])+1}"])]
        entries += [(case["letter_claims"][i], "candidate_claim", [f"C-{key}-{i+1}"], []) for i in selections[v]]
        closing = [(f"I would appreciate discussing {case['discussion']}, including the practical expectations for someone joining this position.", "motivation", [], []),
            ("I would be glad to explain the scope of the work described here and answer questions about what was tested, what was learned, and what remains outside that experience.", "motivation", [], []),
            ("Thank you for considering my application; I would welcome a conversation about the team's priorities and where my experience could be useful.", "motivation", [], [])]
        paragraphs = [entries, closing]
        if length == "standard":
            paragraphs.insert(1, [("Before proposing an approach, I would want to understand the existing constraints, the intended users, and the evidence the team uses to decide whether a change has helped.", "motivation", [], []),
                ("I would also welcome discussion of how responsibilities are shared and how a new team member can contribute while learning the parts of the system that are unfamiliar.", "motivation", [], []),
                ("I welcome questions that clarify the limits of those examples.", "motivation", [], [])])
        variants.append({"variant_id": f"{key}-{v+1}", "angle": ANGLES[v], "paragraphs": [
            {"sentences": [{"id": f"{key}-v{v}-p{p}-s{s}", "text": text, "sentence_kind": kind, "candidate_evidence_ids": candidate, "job_evidence_ids": job}
                for s, (text, kind, candidate, job) in enumerate(items)]} for p, items in enumerate(paragraphs)]})
    return LetterDraft.model_validate({"variants": variants})


def provider(output_model, system, payload, *, model, timeout):
    data = json.loads(payload)
    metadata = {"model": "deterministic-acceptance-fixture", "provider_call": False}
    if output_model is LetterAssessment:
        # This fixture checks wiring and exact recorded sources, not natural-language entailment.
        return LetterAssessment(sentences=[{"sentence_id": item["sentence"]["id"], "actual_kind": item["sentence"]["sentence_kind"],
            "supported": True, "explanation": "Fixture oracle for the authored acceptance example; not a live semantic assessment.",
            "supports": [{"source_kind": kind, "source_id": src["id"], "quote": src["text"]}
                for kind, sources in (("candidate", item["candidate_sources"]), ("job", item["job_sources"])) for src in sources]}
            for item in data["sentences"]]), metadata
    text = data.get("job", {}).get("source_content", "") or "\n".join(e["text"] for e in data.get("job_evidence", []))
    key = case_key(text)
    if key is None:
        raise AssertionError("Acceptance provider needs a distinct case marker")
    case = CASES[key]
    if output_model is LetterDraft:
        return letter(key, data["options"]["count"], data["options"]["length"]), metadata
    prior = data["prior_outputs"]
    if output_model is ResumeDraft:
        return ResumeDraft(requirements=[{"id": f"REQ-{i+1}", "quote": quote, "description": quote} for i, quote in enumerate([*case["requirements"], case["gap"]])],
            bullets=[{"id": f"B-{i+1}", "record_id": case["record"], "evidence_ids": [f"C-{key}-{i+1}"], "requirement_ids": [f"REQ-{i+1}"], "text": text} for i, text in enumerate(case["claims"])],
            skills=[{"name": skill, "source_ids": [f"SK-{key}"]} for skill in case["skills"]], unmet_requirement_ids=["REQ-3"], change_summary=["Fictional role-specific evidence selection."]), metadata
    if output_model is CritiqueReport:
        return CritiqueReport(issues=[]), metadata
    if output_model is RevisedResume:
        return RevisedResume(draft=prior["select"], decisions=[]), metadata
    if output_model is PolishedResume:
        return PolishedResume(draft=prior["revise"]["draft"], edits=[]), metadata
    raise AssertionError("Unknown acceptance contract")
