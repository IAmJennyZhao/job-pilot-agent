"""Fictional sources only; never read the owner's private handoff in automated tests."""
from typing import get_args, get_origin, Literal

from pydantic import BaseModel
import yaml

from app.tailoring_preferences import Preferences
from app.tailoring_schemas import GenerationPolicy, ApprovalWorkflow


def example_model(model):
    def example(annotation):
        origin = get_origin(annotation)
        if origin is Literal:
            return get_args(annotation)[0]
        if origin is list:
            return []
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return example_model(annotation)
        if annotation is bool:
            return True
        if annotation is int:
            return 1
        if annotation is str:
            return "Synthetic"
        return None
    return {field.alias or name: example(field.annotation) for name, field in model.model_fields.items()}


def bank_data():
    policy = example_model(GenerationPolicy)
    policy.update(blocked_claim_ids=["C-BLOCKED"], blocked_evidence_statuses=["needs_user_confirmation"])
    return {
        "schema_version": 4, "bank_version": "synthetic.1", "previous_bank_version": None,
        "prepared_at": "2026-10-22",
        "approval": {"status": "approved_with_exclusions", "approved_claim_ids": ["C-ALLOWED"],
                     "excluded_claim_ids": ["C-BLOCKED"], "approved_by": "Synthetic Tester"},
        "sources": [{"id": "S-1", "independently_verified": False, "source_excerpt": "ARCHIVE_ONLY_SECRET"}],
        "identity": {"name": "Synthetic Tester", "email": "private@example.test", "source_id": "S-1"},
        "education": [{"id": "E-1", "institution": "Fictional College", "degree": "B.S.", "gpa": "3.0/4.0", "source_id": "S-1"}],
        "records": [{"id": "R-1", "kind": "employment", "employer": "Fictional Co", "title_display": "Engineer",
                     "start": "2024-01", "source_id": "S-1"}],
        "claims": [
            {"id": "C-ALLOWED", "record_id": "R-1", "source_id": "S-1", "text": "Built an internal Python prototype.",
             "evidence_status": "source_supported", "generation_eligible": True, "technologies": ["Python"],
             "technology_ids": ["T-1"], "constraints": ["Internal prototype, not production."]},
            {"id": "C-BLOCKED", "record_id": "R-1", "source_id": "S-1", "text": "EXCLUDED_CLAIM_SECRET",
             "evidence_status": "needs_user_confirmation", "generation_eligible": False}],
        "accomplishment_groups": [],
        "implementation_profiles": [{"id": "I-1", "record_id": "R-1", "interpretation": "Summary only",
            "data_flow": [{"text": "Eligible implementation", "evidence_claim_ids": ["C-ALLOWED"], "evidence_status": "source_supported", "generation_eligible": True},
                          {"text": "MIXED_DEPENDENCY_SECRET", "evidence_claim_ids": ["C-ALLOWED", "C-BLOCKED"], "evidence_status": "source_supported", "generation_eligible": True}],
            "component_roles": [], "reliability_and_evaluation": [], "outcomes": [], "implementation_choices": [],
            "open_details": [{"question": "OPEN_QUESTION_SECRET", "answer": None, "generation_eligible": False}]}],
        "claim_overlap_groups": [],
        "skill_groups": [{"id": "SK-1", "label": "Languages", "values": ["Python"], "source_id": "S-1"}],
        "protected_metrics": [{"id": "M-1", "claim_id": "E-1", "display": "3.0/4.0", "unit": "GPA"}],
        "unknowns": {"work_authorization": None}, "awards": [],
        "planned_or_unverified_capabilities": [{"record_id": "R-1", "items": ["PLANNED_SECRET"], "status": "planned", "generation_eligible": False}],
        "generation_policy": policy, "reconciliation_notes": [],
        "technology_catalog": [{"id": "T-1", "name": "Python", "aliases": [], "claim_ids": ["C-ALLOWED"],
            "eligible_claim_ids": ["C-ALLOWED"], "listed_skill_group_ids": ["SK-1"], "record_ids": ["R-1"], "relationship": "Listed and used"}],
        "record_metadata": [], "approval_workflow": example_model(ApprovalWorkflow),
    }


def import_payload(bank=None):
    preferences = example_model(Preferences)
    preferences.update(schema_version=2, mode="manual_tailoring_only")
    return {"bank_markdown": "# Synthetic source\n\n```yaml\n" + yaml.safe_dump(bank or bank_data(), sort_keys=False) + "```\n",
            "preferences_yaml": yaml.safe_dump(preferences), "template_tex": "Synthetic inert template", "style_guide": "Synthetic style"}
