"""Fictional deterministic provider for workflow tests, not a semantic-quality benchmark."""
import json
from app.letter_schemas import LetterDraft, LetterAssessment
from app.services.letter_validation import ANGLES


def fake_letter(output_model, system, payload, **kwargs):
    data = json.loads(payload)
    if output_model is LetterDraft:
        count, length = data["options"]["count"], data["options"]["length"]
        claim = data["approved_evidence"]["claims"][0]
        variants = []
        for i in range(count):
            texts = [
                [f"I am interested in this opportunity to contribute thoughtful work{' alongside a team' if i == 1 else ' with a practical focus' if i == 2 else ''} and would welcome the chance to discuss the role.",
                 "I created an internal prototype using Python."] ,
                ["I would welcome a conversation about the priorities for this position and how my experience might fit the needs described in the posting.",
                 "Thank you for considering my application and taking the time to review the work presented here, and I would appreciate learning more about the opportunity."],
            ]
            texts[1].append("I would appreciate the chance to hear more about the team's current priorities and consider how the work described here relates to those needs.")
            if length == "standard":
                texts.append(["I would value an opportunity to discuss the practical questions facing the team and learn more about the expectations for someone joining in this role.",
                    "A conversation about the position would help me understand the areas where I could contribute and where further learning would be needed to meet those expectations.",
                    "I would be glad to talk through my experience, answer questions about the work, and consider how it relates to the responsibilities outlined for the position.",
                    "Thank you again for your time and consideration of my application."])
            else:
                texts[1].append("I look forward to the possibility of discussing this opportunity with you.")
            paragraphs = []
            for p, entries in enumerate(texts):
                paragraphs.append({"sentences": [{"id": f"v{i}-p{p}-s{s}", "text": text,
                    "sentence_kind": "candidate_claim" if p == 0 and s == 1 else "motivation",
                    "candidate_evidence_ids": [claim["id"]] if p == 0 and s == 1 else [], "job_evidence_ids": []}
                    for s, text in enumerate(entries)]})
            variants.append({"variant_id": f"variant-{i+1}", "angle": ANGLES[i], "paragraphs": paragraphs})
        return LetterDraft.model_validate({"variants": variants}), {"provider_call": False}
    assert output_model is LetterAssessment
    verdicts = []
    for item in data["sentences"]:
        s = item["sentence"]
        # Explicit fixture oracle: accept the fixture paraphrase; reject adversarial examples.
        bad = any(word in s["text"].lower() for word in ("referred", "production", "years", "kubernetes", "millions", "followed"))
        candidate = s["text"].startswith("I created")
        if candidate and not any("prototype" in c["text"] for c in item["candidate_sources"]):
            bad = True
        verdicts.append({"sentence_id": s["id"], "actual_kind": "candidate_claim" if bad or candidate else s["sentence_kind"],
            "supported": not bad, "explanation": "Unsupported personal history or changed scope." if bad else "Faithful meaning or generic present interest.",
            "supports": [{"source_kind": kind, "source_id": source["id"], "quote": source["text"]}
                for kind, sources in (("candidate", item["candidate_sources"]), ("job", item["job_sources"])) for source in sources]})
    return LetterAssessment.model_validate({"sentences": verdicts}), {"provider_call": False}
