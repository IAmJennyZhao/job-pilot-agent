"""Recheck stored contracts and provenance offline; never call a model during restore."""
from app.letter_schemas import LetterDraft, LetterOptions
from app.letter_prompts import VERSION, system
from app.services import letter_validation as policy
from app.services.cover_letters import draft_input, structural_report
from app.services.intake_preferences import digest


def assessment_for(tables, run, row, baseline_id):
    attempts = sorted((a for a in tables["tailoring_stage_attempts"] if a["run_id"] == run["id"]), key=lambda a: a["attempt"], reverse=True)
    manual = [a for a in attempts if a["stage"] == "letter_check" and a["input_data"]["revision_id"] == row["id"]]
    if manual:
        a = manual[0]
        return a["output_data"] if a["state"] in {"passed", "failed"} and a["input_data"]["content_hash"] == row["content_hash"] else None
    if row["id"] != baseline_id:
        return None
    return next((a["output_data"] for a in attempts if a["stage"] == "letter_assess" and a["state"] == "passed" and a["input_data"]["content_hash"] == row["content_hash"]), None)


def validate_run(tables, run):
    snapshot = run["snapshot"]
    LetterOptions.model_validate(snapshot["letter_options"])
    if snapshot["letter_version"] != 1 or snapshot["letter_prompt_version"] != VERSION or snapshot["letter_prompt_hashes"] != {s: digest(system(s)) for s in ("letter_draft", "letter_assess")}:
        raise ValueError("Unsupported letter policy")
    template = snapshot["letter_template"]
    if bool(template) != bool(snapshot["letter_options"]["template_id"]) or (template and (template["hash"] != digest(template["body"]) or template["id"] != snapshot["letter_options"]["template_id"])):
        raise ValueError("Invalid frozen letter style")
    if run["state"] not in {"pending", "running", "completed", "failed", "interrupted"}:
        raise ValueError("Invalid letter run state")
    key = f"{run['profile_id']}:{run['job_id']}:cover_letter" if run["state"] in {"pending", "running"} else None
    if run["active_key"] != key:
        raise ValueError("Invalid letter active identity")
    attempts = [a for a in tables["tailoring_stage_attempts"] if a["run_id"] == run["id"]]
    drafts, passed = {}, []
    baselines = [r for r in tables["tailored_revisions"] if r["run_id"] == run["id"]]
    if len(baselines) != (1 if run["state"] == "completed" else 0):
        raise ValueError("Letter completion/revision mismatch")
    indexed = {r["id"]: r for r in [*baselines, *[e for e in tables["resume_edit_revisions"] if baselines and e["baseline_id"] == baselines[0]["id"]]]}
    for stage in ("letter_draft", "letter_assess", "letter_check"):
        rows = sorted((a for a in attempts if a["stage"] == stage), key=lambda a: a["attempt"])
        for index, a in enumerate(rows, 1):
            data, output = a["input_data"], a["output_data"]
            if a["prompt_version"] != VERSION or a["state"] not in {"running", "passed", "failed", "interrupted"} or a["input_hash"] != digest(data) or a["output_hash"] != (digest(output) if output is not None else None):
                raise ValueError("Invalid letter checkpoint")
            if stage == "letter_draft":
                if a["attempt"] != index or index > 2 or data != draft_input(snapshot, data.get("repair")):
                    raise ValueError("Invalid writer input")
                if output is not None:
                    content = policy.build_content(LetterDraft.model_validate(output), None, snapshot)
                    report = structural_report(content, snapshot)
                    if a["state"] == "passed":
                        drafts[a["attempt"]] = content
            else:
                if stage == "letter_assess":
                    content = drafts[a["attempt"]]
                    expected = {"input_hash": run["input_hash"], **policy.assessment_payload(content, snapshot)}
                else:
                    if a["attempt"] != index:
                        raise ValueError("Invalid evidence check sequence")
                    row = indexed[data["revision_id"]]
                    content = row["content"]
                    expected = {"input_hash": run["input_hash"], "revision_id": row["id"], "request_key": data["request_key"],
                        "request_hash": digest({"request_key": data["request_key"], "expected_revision_id": row["id"], "content_hash": row["content_hash"]}),
                        **policy.assessment_payload(content, snapshot)}
                if data != expected:
                    raise ValueError("Evidence check is not bound to the saved sentence sources")
                if output is not None:
                    report = policy.validate(content, snapshot, output)
                    if stage == "letter_assess" and a["state"] == "passed":
                        passed.append((content, report))
            if output is not None and (a["validation"] != report or (a["state"] == "passed" and not report["valid"])):
                raise ValueError("Letter evidence report mismatch")
            if output is None and a["state"] == "passed":
                raise ValueError("Passed evidence check has no output")
    if any(a["stage"] not in {"letter_draft", "letter_assess", "letter_check"} for a in attempts):
        raise ValueError("Unknown letter stage")
    if baselines:
        row = baselines[0]
        if len(passed) != 1:
            raise ValueError("Letter lacks a unique validated assessment")
        content, report = passed[0]
        if row["content"] != content or row["validation"] != report or row["content_hash"] != digest(content) or row["plain_text"] != policy.text_for(content, snapshot):
            raise ValueError("Generated letter was altered")


def check_edit(row, baseline, snapshot):
    content = policy.build_content(LetterDraft.model_validate(policy.editable(row["content"])), baseline, snapshot)
    if row["content"] != content or row["content_hash"] != digest(content) or row["plain_text"] != policy.text_for(content, snapshot) or row["validation"] != policy.validate(content, snapshot):
        raise ValueError("Letter edit was altered")
