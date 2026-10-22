"""Authorize replacement bullets through explicit parents and accepted critique issues."""


def validate_lineage(output, old, new, issues):
    errors, authorized = [], set()
    entries = output.lineage
    ids = [entry.bullet_id for entry in entries]
    if len(ids) != len(set(ids)) or set(ids) != new.keys() - old.keys():
        errors.append("Lineage must contain exactly one entry for each new bullet ID, and none for retained IDs.")
    accepted = {d.issue_id for d in output.decisions if d.action == "accepted"}
    for entry in entries:
        bullet = new.get(entry.bullet_id)
        parents = set(entry.parent_bullet_ids)
        links = set(entry.issue_ids)
        if not bullet or entry.bullet_id in old:
            continue
        if len(parents) != len(entry.parent_bullet_ids) or not parents <= old.keys():
            errors.append(f"Lineage {entry.bullet_id} references duplicate or unknown parents.")
            continue
        if not links or len(links) != len(entry.issue_ids) or not links <= accepted or not links <= issues.keys():
            errors.append(f"Lineage {entry.bullet_id} must cite accepted critique issue IDs.")
            continue
        linked = [issues[i] for i in links]
        if any(i.requires_user_fact_confirmation for i in linked):
            errors.append(f"Lineage {entry.bullet_id} cannot rely on unapproved new facts.")
            continue
        if any(old[p].record_id != bullet.record_id for p in parents):
            errors.append(f"Lineage {entry.bullet_id} cannot cross work records.")
            continue
        if any(p in new for p in parents):
            errors.append(f"Lineage {entry.bullet_id} must retire replaced parents and give every resulting bullet a new ID.")
            continue
        targets = {i.field_path for i in linked}
        if "draft" not in targets:
            if not parents or not all(f"bullets.{p}" in targets for p in parents):
                errors.append(f"Lineage {entry.bullet_id} needs an accepted issue for every parent, or a draft issue.")
                continue
            evidence = {cid for p in parents for cid in old[p].evidence_ids}
            if not set(bullet.evidence_ids) <= evidence:
                errors.append(f"Lineage {entry.bullet_id} adds evidence outside its parents; accept a draft issue for new selection.")
                continue
        authorized.add(entry.bullet_id)
    return authorized, errors
