import copy

import pytest

from app.tailoring_schemas import SourceImport
from app.services.tailoring_source_validation import SourceError, canonical, load_yaml, validate_bundle
from tailoring_fixtures import bank_data, import_payload


def validate(bank=None):
    return validate_bundle(SourceImport(**import_payload(bank)))


def test_projection_excludes_archive_and_transitive_ineligible_details():
    bank, _, projection, report, hashes, bundle_hash = validate()
    content = canonical(projection.model_dump())
    for secret in ["ARCHIVE_ONLY_SECRET", "EXCLUDED_CLAIM_SECRET", "MIXED_DEPENDENCY_SECRET", "OPEN_QUESTION_SECRET", "PLANNED_SECRET", "private@example.test", "C-BLOCKED"]:
        assert secret not in content
    assert "Internal prototype, not production." in content
    assert "Eligible implementation" in content
    assert projection.protected_metrics[0]["claim_id"] == "E-1"
    assert report.eligible_claim_ids == ["C-ALLOWED"]
    assert report.excluded_claim_ids == ["C-BLOCKED"]
    assert validate()[-1] == bundle_hash
    assert len(hashes["bank_markdown"]) == 64


@pytest.mark.parametrize("yaml_text", ["x: 1\nx: 2", "x: &x [*x]", "!!python/object/apply:os.system ['bad']", "x: .nan", "[" * 40 + "0" + "]" * 40])
def test_yaml_rejects_unsafe_or_invalid_shapes(yaml_text):
    if yaml_text == "x: .nan":
        # YAML can parse this; typed bank/preferences never permit it in numeric policy fields.
        bank = bank_data(); bank["schema_version"] = float("nan")
        with pytest.raises(SourceError): validate(bank)
    else:
        with pytest.raises(SourceError): load_yaml(yaml_text)


def test_benign_alias_supported_and_expansion_bounded():
    assert load_yaml("a: &a [one]\nb: *a") == {"a": ["one"], "b": ["one"]}
    text = "a: &a [x,x,x,x,x,x,x,x,x,x]\n"
    previous = "a"
    for current in "bcdef":
        text += f"{current}: &{current} [" + ",".join([f"*{previous}"] * 10) + "]\n"
        previous = current
    with pytest.raises(SourceError): load_yaml(text)


@pytest.mark.parametrize("change", [
    lambda b: b.update(schema_version=99),
    lambda b: b.update(unexpected="secret"),
    lambda b: b["claims"].append(copy.deepcopy(b["claims"][0])),
    lambda b: b["claims"][0].update(source_id="missing"),
    lambda b: b["claims"][0].update(record_id="missing"),
    lambda b: b["approval"]["approved_claim_ids"].append("C-BLOCKED"),
    lambda b: b["claims"][0].update(generation_eligible=False),
    lambda b: b["protected_metrics"][0].update(claim_id="missing"),
    lambda b: b["technology_catalog"][0].update(eligible_claim_ids=["C-BLOCKED"]),
    lambda b: b["implementation_profiles"][0]["data_flow"][0].update(evidence_claim_ids=["missing"]),
])
def test_invalid_references_and_contracts_fail_closed(change):
    bank = bank_data(); change(bank)
    with pytest.raises(SourceError): validate(bank)


def test_exactly_one_yaml_block_and_byte_limits():
    payload = import_payload()
    payload["bank_markdown"] += "\n```yaml\nx: y\n```\n"
    with pytest.raises(SourceError): validate_bundle(SourceImport(**payload))
    with pytest.raises(SourceError): load_yaml("x" * 524289)


def test_source_changes_change_bundle_hash_and_preserve_input():
    bank = bank_data(); original = copy.deepcopy(bank)
    before = validate(bank)[-1]
    assert bank == original
    bank["claims"][0]["text"] = "Updated supported prototype wording."
    assert validate(bank)[-1] != before
