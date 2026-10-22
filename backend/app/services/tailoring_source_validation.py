"""Pure source validation and allowlisted projection; no provider or filesystem access."""
import hashlib
import json
import re
from datetime import date

import yaml
from pydantic import ValidationError
from yaml.nodes import MappingNode, SequenceNode

from app.tailoring_preferences import Preferences
from app.tailoring_schemas import Bank, Projection, SourceImport, ValidationReport

VALIDATOR_VERSION = "bank4-projection1-v1"
MAX_SOURCE_BYTES = 524288


class SourceError(ValueError):
    """Safe public validation error: never contains imported values."""


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise SourceError("YAML keys must be unique strings; merge keys are not supported.")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def load_yaml(text: str, limit: int = MAX_SOURCE_BYTES):
    if len(text.encode("utf-8")) > limit:
        raise SourceError("Source exceeds the import size limit.")
    loader = UniqueLoader(text)
    try:
        node = loader.get_single_node()
        if node is None:
            raise SourceError("Source is empty.")
        budget = 30000

        def visit(current, stack, depth):
            nonlocal budget
            budget -= 1
            if depth > 32 or budget < 0 or id(current) in stack:
                raise SourceError("YAML nesting or alias expansion exceeds safe limits.")
            children = ([item for pair in current.value for item in pair] if isinstance(current, MappingNode)
                        else current.value if isinstance(current, SequenceNode) else [])
            for child in children:
                visit(child, stack | {id(current)}, depth + 1)

        visit(node, set(), 0)
        return loader.construct_document(node)
    except (yaml.YAMLError, RecursionError, TypeError) as exc:
        raise SourceError("Invalid or unsupported YAML.") from exc
    finally:
        loader.dispose()


def index(items, label):
    result = {item.id: item for item in items}
    if len(result) != len(items) or any(not key.strip() for key in result):
        raise SourceError(f"Duplicate or empty IDs in {label}.")
    return result


def check_refs(values, allowed, label):
    if len(values) != len(set(values)) or not set(values) <= set(allowed):
        raise SourceError(f"Invalid or duplicate references in {label}.")


def validate_bank(markdown: str) -> tuple[Bank, ValidationReport]:
    if len(markdown.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise SourceError("Bank exceeds the import size limit.")
    blocks = re.findall(r"^```yaml[^\S\n]*\r?\n(.*?)^```[^\S\n]*$", markdown, re.M | re.S)
    if len(blocks) != 1:
        raise SourceError("Bank must contain exactly one canonical YAML block.")
    try:
        bank = Bank.model_validate(load_yaml(blocks[0]))
    except ValidationError as exc:
        # Never return Pydantic's input values (which may contain candidate data).
        paths = [".".join(map(str, issue["loc"])) for issue in exc.errors()[:8]]
        raise SourceError("Invalid bank fields: " + ", ".join(paths)) from exc
    sources = index(bank.sources, "sources")
    records = index(bank.records, "records")
    claims = index(bank.claims, "claims")
    education = index(bank.education, "education")
    groups = index(bank.accomplishment_groups, "groups")
    skills = index(bank.skill_groups, "skill groups")
    technologies = index(bank.technology_catalog, "technologies")
    for label in ["implementation_profiles", "claim_overlap_groups", "protected_metrics", "awards", "reconciliation_notes"]:
        index(getattr(bank, label), label)
    all_ids = [*sources, *records, *claims, *education, *groups, *skills, *technologies]
    if len(all_ids) != len(set(all_ids)):
        raise SourceError("IDs must be unambiguous across evidence namespaces.")
    for item in [bank.identity, *bank.education, *bank.records, *bank.claims, *bank.skill_groups, *bank.awards, *bank.record_metadata]:
        check_refs([item.source_id], sources, "source")
    if bank.identity.relocation_preference:
        check_refs([bank.identity.relocation_preference.source_id], sources, "relocation source")
    for record in bank.records:
        if record.kind == "employment" and not (record.employer and record.title_display and record.start):
            raise SourceError("Employment records require employer, title, and start date.")
        if record.kind == "project" and not record.name:
            raise SourceError("Project records require a name.")
    approved = set(bank.approval.approved_claim_ids)
    excluded = set(bank.approval.excluded_claim_ids) | set(bank.generation_policy.blocked_claim_ids)
    for refs in [bank.approval.approved_claim_ids, bank.approval.excluded_claim_ids, bank.generation_policy.blocked_claim_ids]:
        check_refs(refs, claims, "approval")
    if approved & excluded:
        raise SourceError("Approved and excluded claim lists overlap.")
    eligible = {c.id for c in bank.claims if c.id in approved and c.id not in excluded
                and c.evidence_status == "source_supported" and c.generation_eligible
                and c.evidence_status not in bank.generation_policy.blocked_evidence_statuses}
    if approved != eligible:
        raise SourceError("The approval allowlist contains an ineligible claim.")
    for claim in bank.claims:
        check_refs([claim.record_id], records, "claim record")
        check_refs(claim.corroborating_source_ids, sources, "corroborating sources")
        check_refs(claim.technology_ids, technologies, "claim technologies")
        if claim.accomplishment_group_id:
            check_refs([claim.accomplishment_group_id], groups, "claim group")
            if groups[claim.accomplishment_group_id].record_id != claim.record_id:
                raise SourceError("Claim group belongs to a different record.")
    for group in bank.accomplishment_groups:
        check_refs([group.record_id], records, "group record")
        check_refs(group.claim_ids, claims, "group claims")
        if any(claims[c].record_id != group.record_id for c in group.claim_ids):
            raise SourceError("Group claims must belong to its record.")
    for profile in bank.implementation_profiles:
        check_refs([profile.record_id], records, "implementation record")
        if profile.accomplishment_group_id:
            check_refs([profile.accomplishment_group_id], groups, "implementation group")
            if groups[profile.accomplishment_group_id].record_id != profile.record_id:
                raise SourceError("Implementation group belongs to a different record.")
        details = [*profile.data_flow, *profile.component_roles, *profile.reliability_and_evaluation, *profile.outcomes]
        for choice in profile.implementation_choices:
            details.extend(d for d in [choice.observed_choice, choice.confirmed_rationale, choice.alternatives_evaluated] if d)
        for detail in details:
            check_refs(detail.evidence_claim_ids, claims, "implementation evidence")
            if any(claims[c].record_id != profile.record_id for c in detail.evidence_claim_ids):
                raise SourceError("Implementation evidence crosses records.")
    for metric in bank.protected_metrics:
        check_refs([metric.claim_id], set(claims) | set(education), "metric evidence")
    for overlap in bank.claim_overlap_groups:
        check_refs(overlap.claim_ids, claims, "overlap claims")
    for tech in bank.technology_catalog:
        check_refs(tech.claim_ids, claims, "technology claims")
        check_refs(tech.eligible_claim_ids, eligible & set(tech.claim_ids), "technology eligibility")
        check_refs(tech.record_ids, records, "technology records")
        check_refs(tech.listed_skill_group_ids, skills, "technology skill groups")
        if set(tech.record_ids) != {claims[c].record_id for c in tech.claim_ids}:
            raise SourceError("Technology record provenance does not match its claims.")
    seen_metadata = set()
    for metadata in bank.record_metadata:
        check_refs([metadata.record_id], records, "record metadata")
        if metadata.record_id in seen_metadata:
            raise SourceError("Duplicate record metadata.")
        seen_metadata.add(metadata.record_id)
    for item in bank.planned_or_unverified_capabilities:
        check_refs([item.record_id], records, "planned record")
        check_refs(item.source_ids, sources, "planned sources")
        if item.accomplishment_group_id:
            check_refs([item.accomplishment_group_id], groups, "planned group")
    warnings = ["Source support and recorded approval are not independent verification.",
                "Local hashes verify integrity, not an unavailable external manifest.",
                "Template compilation and visual layout are not verified in this phase."]
    if bank.approval.status not in {"approved", "approved_with_exclusions"}:
        warnings.append("Offline source approval is required before activation.")
    for source in bank.sources:
        observation = source.received_at or source.retrieved_at
        if observation:
            try:
                if (date.today() - date.fromisoformat(observation)).days > 90:
                    warnings.append("Some source observations are over 90 days old; review time-sensitive fields.")
                    break
            except ValueError as exc:
                raise SourceError("Invalid source observation date.") from exc
    return bank, ValidationReport(eligible_claim_ids=sorted(eligible),
                                 excluded_claim_ids=sorted(set(claims) - eligible),
                                 warnings=warnings, validator_version=VALIDATOR_VERSION)


def project_bank(bank: Bank, report: ValidationReport) -> Projection:
    eligible = set(report.eligible_claim_ids)
    claims = [c for c in bank.claims if c.id in eligible]
    record_ids = {c.record_id for c in claims}

    def detail(value):
        if value and value.generation_eligible and value.evidence_status == "source_supported" and set(value.evidence_claim_ids) <= eligible:
            return value.model_dump(include={"text", "evidence_claim_ids"})
        return None

    profiles = []
    for profile in bank.implementation_profiles:
        out = {"id": profile.id, "record_id": profile.record_id}
        for key in ["data_flow", "component_roles", "reliability_and_evaluation", "outcomes"]:
            out[key] = [d for v in getattr(profile, key) if (d := detail(v))]
        out["implementation_choices"] = []
        for choice in profile.implementation_choices:
            observed = detail(choice.observed_choice)
            if observed:
                out["implementation_choices"].append({"observed_choice": observed,
                    "confirmed_rationale": detail(choice.confirmed_rationale),
                    "alternatives_evaluated": detail(choice.alternatives_evaluated)})
        if any(out[k] for k in ["data_flow", "component_roles", "reliability_and_evaluation", "outcomes", "implementation_choices"]):
            profiles.append(out)
    technologies = []
    for tech in bank.technology_catalog:
        claim_ids = sorted(set(tech.eligible_claim_ids) & eligible)
        if claim_ids or tech.listed_skill_group_ids:
            technologies.append({"id": tech.id, "name": tech.name, "aliases": tech.aliases,
                "claim_ids": claim_ids, "listed_skill_group_ids": tech.listed_skill_group_ids,
                "record_ids": sorted({c.record_id for c in claims if c.id in claim_ids}),
                "relationship": "Listed skills do not establish use in a work record."})
    return Projection(bank_version=bank.bank_version,
        claims=[c.model_dump(include={"id", "record_id", "text", "technologies", "technology_ids", "constraints", "themes"}) for c in claims],
        records=[r.model_dump(include={"id", "kind", "employer", "title_display", "location", "name", "start", "end", "current_as_of", "dates_display", "status"}) for r in bank.records if r.id in record_ids],
        education=[e.model_dump(exclude={"source_id", "source_lines", "source_locator"}) for e in bank.education],
        skill_groups=[g.model_dump(include={"id", "label", "values", "proficiency"}) for g in bank.skill_groups],
        technology_catalog=technologies, implementation_profiles=profiles,
        protected_metrics=[m.model_dump() for m in bank.protected_metrics if m.claim_id in eligible or m.claim_id in {e.id for e in bank.education}],
        claim_overlap_groups=[{"id": g.id, "claim_ids": sorted(set(g.claim_ids) & eligible), "rule": g.rule}
                              for g in bank.claim_overlap_groups if len(set(g.claim_ids) & eligible) > 1])


def validate_bundle(payload: SourceImport):
    bank, report = validate_bank(payload.bank_markdown)
    try:
        preferences = Preferences.model_validate(load_yaml(payload.preferences_yaml, 65536))
    except ValidationError as exc:
        raise SourceError("Preferences do not match the supported schema.") from exc
    if preferences.schema_version != 2 or preferences.compensation.minimum < 0:
        raise SourceError("Invalid preference schema version or salary minimum.")
    if preferences.mode != "manual_tailoring_only" or not preferences.tailoring.review_before_final_export:
        raise SourceError("Preferences must preserve manual tailoring and final review.")
    for text in [payload.template_tex, payload.style_guide]:
        if len(text.encode("utf-8")) > 65536 or not text.strip():
            raise SourceError("Template/style source is empty or oversized.")
    # These are inert snapshots: never compile uploaded TeX during import/activation.
    projection = project_bank(bank, report)
    hashes = {key: digest(value) for key, value in payload.model_dump().items()}
    hashes["projection"] = digest(canonical(projection.model_dump()))
    hashes["validator"] = VALIDATOR_VERSION
    return bank, preferences, projection, report, hashes, digest(canonical(hashes))
