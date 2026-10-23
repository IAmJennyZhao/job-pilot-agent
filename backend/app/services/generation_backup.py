"""Verify persisted generation checkpoints before any destructive restore."""
from app.services.intake_preferences import digest
from app.services.resume_validation import STAGES, validate_stage, assemble_content, plain_text, accuracy_report, generation_version, output_models, prompt_versions
from app.resume_prompts import system_for


def validate_generation_tables(tables):
    runs = {row["id"]: row for row in tables["tailoring_runs"]}
    sources = {row["id"]: row for row in tables["tailoring_source_versions"]}
    ordered, visiting = [], set()
    def visit(run):
        if run in ordered:
            return
        if run["id"] in visiting:
            raise ValueError("Cyclic retry history")
        visiting.add(run["id"])
        if run["parent_run_id"]:
            parent = runs[run["parent_run_id"]]
            if (parent["profile_id"], parent["job_id"], parent["input_hash"]) != (run["profile_id"], run["job_id"], run["input_hash"]):
                raise ValueError("Invalid retry parent")
            visit(parent)
        visiting.remove(run["id"])
        ordered.append(run)
    for run in runs.values():
        visit(run)
        snapshot = run["snapshot"]
        source = sources[run["source_id"]]
        if run["input_hash"] != digest(snapshot) or snapshot["projection_hash"] != digest(snapshot["projection"]):
            raise ValueError("Invalid generation input hash")
        if snapshot["source_id"] != source["id"] or snapshot["source_hash"] != source["bundle_hash"] or snapshot["profile_id"] != run["profile_id"] or snapshot["job"]["id"] != run["job_id"] or source["profile_id"] != run["profile_id"]:
            raise ValueError("Invalid generation source reference")
        for key in ("projection", "preferences", "template_tex", "style_guide"):
            if snapshot[key] != source[key]:
                raise ValueError("Generation source snapshot differs from approved source")
        if snapshot["identity"] != source["bank"]["identity"] or snapshot["source_hashes"] != source["hashes"]:
            raise ValueError("Invalid protected identity or source hashes")
        from app.services.letter_validation import is_letter
        if is_letter(snapshot):
            from app.services.letter_backup import validate_run
            validate_run(tables, run)
            continue
        if snapshot.get("document_kind", "resume") != "resume":
            raise ValueError("Unknown generated document kind")
        if snapshot["prompt_versions"] != prompt_versions(snapshot) or snapshot["prompt_hashes"] != {stage: digest(system_for(stage, generation_version(snapshot))) for stage in STAGES}:
            raise ValueError("Unsupported generation prompt version")
        if run["state"] not in {"pending", "running", "completed", "failed", "interrupted"}:
            raise ValueError("Invalid run state")
        expected_key = f"{run['profile_id']}:{run['job_id']}:resume" if run["state"] in {"pending", "running"} else None
        if run["active_key"] != expected_key:
            raise ValueError("Invalid active run identity")
        accepted = {}
        attempts = [a for a in tables["tailoring_stage_attempts"] if a["run_id"] == run["id"]]
        for stage in STAGES:
            rows = sorted((a for a in attempts if a["stage"] == stage), key=lambda a: a["attempt"])
            for index, attempt in enumerate(rows, 1):
                if not set(STAGES[:STAGES.index(stage)]) <= set(accepted):
                    raise ValueError("Stage has missing predecessors")
                if index > 2 or attempt["attempt"] != index or attempt["prompt_version"] != prompt_versions(snapshot)[stage]:
                    raise ValueError("Invalid stage attempt identity")
                if attempt["input_hash"] != digest(attempt["input_data"]) or attempt["input_data"]["dependencies_hash"] != digest({"input": run["input_hash"], "stage": stage, "prior": accepted}):
                    raise ValueError("Invalid stage dependencies")
                data = attempt["input_data"]
                if data["job"] != snapshot["job"] or data["approved_evidence"] != snapshot["projection"] or data["prior_outputs"] != accepted or data["stage"] != stage:
                    raise ValueError("Invalid stage input snapshot")
                if generation_version(snapshot) >= 2:
                    from app.services.resume_generation import stage_input
                    if data != stage_input(snapshot, stage, accepted, data.get("repair")):
                        raise ValueError("Invalid composition contract snapshot")
                if attempt["state"] not in {"running", "passed", "failed", "interrupted"}:
                    raise ValueError("Invalid stage state")
                output = attempt["output_data"]
                if attempt["output_hash"] != (digest(output) if output is not None else None):
                    raise ValueError("Invalid stage output hash")
                if output is not None:
                    parsed = output_models(snapshot)[stage].model_validate(output)
                    metadata = attempt["provider_metadata"]
                    if "composition_plan" in metadata:
                        from app.services.resume_composition import plan_model, compile_plan
                        allowed = {"select", "revise", "polish"} if generation_version(snapshot) >= 4 else {"select", "revise"}
                        version = 3 if generation_version(snapshot) >= 5 else 2 if generation_version(snapshot) >= 4 else 1
                        if stage not in allowed or generation_version(snapshot) < 2 or metadata.get("composition_version") != version:
                            raise ValueError("Unsupported composition plan")
                        plan = plan_model(output_models(snapshot)[stage], data).model_validate(metadata["composition_plan"])
                        if compile_plan(plan, data).model_dump(mode="json") != output:
                            raise ValueError("Composition plan differs from saved output")
                    report = validate_stage(stage, parsed, snapshot, accepted)
                    if report != attempt["validation"] or (attempt["state"] == "passed" and not report["valid"]):
                        raise ValueError("Invalid stage validation report")
                elif attempt["state"] == "passed":
                    raise ValueError("Passed stage has no output")
                if attempt["state"] == "passed":
                    accepted[stage] = output
            if rows and stage not in accepted and any(a["stage"] in STAGES[STAGES.index(stage)+1:] for a in attempts):
                raise ValueError("Stages advanced past a failure")
        if any(a["stage"] not in STAGES for a in attempts):
            raise ValueError("Unknown generation stage")
        revisions = [r for r in tables["tailored_revisions"] if r["run_id"] == run["id"]]
        if bool(revisions) != (run["state"] == "completed") or len(revisions) > 1:
            raise ValueError("Completed run/revision mismatch")
        for revision in revisions:
            if set(accepted) != set(STAGES):
                raise ValueError("Revision lacks all four validated stages")
            draft = output_models(snapshot)["polish"].model_validate(accepted["polish"]).draft
            content = assemble_content(draft, snapshot)
            if revision["content"] != content or revision["content_hash"] != digest(content) or revision["plain_text"] != plain_text(content, snapshot) or revision["validation"] != accuracy_report(draft, snapshot, accepted):
                raise ValueError("Generated revision was altered")
    tables["tailoring_runs"] = ordered
