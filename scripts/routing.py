"""Find compatible confirmed capabilities for a domain-neutral task brief."""

import shutil
from datetime import datetime, timezone
from pathlib import Path


def text_list(value, key, default=None):
    items = value.get(key, default)
    if not isinstance(items, list) or any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{key} must be a list of nonempty strings")
    return set(items)


def validate_routing(value):
    if not isinstance(value, dict) or value.get("role", "specialist") not in ("primary", "specialist"):
        raise ValueError("routing must be an object with a primary or specialist role")
    if not text_list(value, "capabilities"):
        raise ValueError("routing.capabilities must not be empty")
    if not text_list(value, "outputs"):
        raise ValueError("routing.outputs must not be empty")
    for key in ("inputs", "conflicts"):
        text_list(value, key, [])
    deps = value.get("dependencies", [])
    if not isinstance(deps, list):
        raise ValueError("routing.dependencies must be a list")
    for dep in deps:
        if (not isinstance(dep, dict) or dep.get("type") not in ("executable", "path", "manual")
                or not isinstance(dep.get("value"), str) or not dep["value"].strip()):
            raise ValueError("Dependency requires type executable/path/manual and a nonempty value")
        if "check" in dep:
            check = dep["check"]
            if dep["type"] != "manual" or not isinstance(check, dict) or any(
                not isinstance(check.get(key), str) or not check[key].strip()
                for key in ("path", "sha256", "checked_at", "expires_at")
            ):
                raise ValueError("Manual dependency evidence needs path, sha256, checked_at and expires_at")


def dependency_status(dep, file_hash):
    kind, value = dep["type"], dep["value"]
    if kind == "executable":
        state = "available" if shutil.which(value) else "missing"
    elif kind == "path":
        state = "available" if Path(value).expanduser().exists() else "missing"
    else:
        state = "unknown"
        check = dep.get("check", {})
        try:
            now = datetime.now(timezone.utc)
            if (datetime.fromisoformat(check["checked_at"]) <= now < datetime.fromisoformat(check["expires_at"])
                    and file_hash(Path(check["path"]).expanduser()) == check["sha256"]):
                state = "available"
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return {"type": kind, "value": value, "state": state}


def pick(candidates, required, limit):
    selected, covered = [], set()
    for item in candidates:
        if len(selected) >= limit or covered >= required:
            break
        if item["role"] == "primary" and any(other["role"] == "primary" for other in selected):
            continue
        if any(other["id"] in item["conflicts"] or item["id"] in other["conflicts"] for other in selected):
            continue
        if set(item["covers"]) - covered:
            selected.append(item)
            covered.update(item["covers"])
    return {"ids": [item["id"] for item in selected], "uncovered": sorted(required - covered)}


def route(brief, records, profile, file_hash, limit, status_of):
    if not isinstance(brief, dict):
        raise ValueError("Expected a brief object")
    required = text_list(brief, "required_capabilities")
    if not required:
        raise ValueError("Map the task to at least one explicit required capability")
    inputs = text_list(brief, "inputs", [])
    output = brief.get("output")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("Specify the required output")
    request = brief.get("request", "")
    if not isinstance(request, str):
        raise ValueError("request must be text")
    terms = request.casefold().split()
    candidates, excluded = [], []
    for key, payload in records:
        card = payload["card"]
        config = card.get("routing")
        if not config:
            continue
        covered = required & set(config["capabilities"])
        if not covered:
            continue
        missing = sorted(set(config.get("inputs", [])) - inputs)
        reasons = []
        if key in profile["reject"]:
            reasons.append("rejected")
        if output not in config["outputs"]:
            reasons.append("output mismatch")
        if missing:
            reasons.append("missing inputs")
        if not reasons:
            state = status_of(payload)
            if state != "current":
                reasons.append(state)
        if reasons:
            excluded.append({"id": key, "reasons": reasons, "missing_inputs": missing})
            continue
        dependencies = [dependency_status(dep, file_hash) for dep in config.get("dependencies", [])]
        level = card["level"]
        ready = level != "read" and all(dep["state"] == "available" for dep in dependencies)
        description = (card["title"] + " " + card["purpose"]).casefold()
        score = (8 * len(covered) + sum(term in description for term in terms)
                 + 2 * (key in profile["favorite"]) + {"reproduced": 2, "reusable": 3}.get(level, 0))
        candidates.append({"id": key, "title": card["title"], "covers": sorted(covered), "score": score,
                           "role": config.get("role", "specialist"), "level": level,
                           "conflicts": config.get("conflicts", []), "dependencies": dependencies,
                           "execution_ready": ready})
    candidates.sort(key=lambda item: (not item["execution_ready"], -item["score"], item["id"]))
    planning = pick(candidates, required, limit)
    execution = pick([item for item in candidates if item["execution_ready"]], required, limit)
    visible = set(planning["ids"]) | {item["id"] for item in candidates[:limit]}
    return {"required": sorted(required), "planning": planning, "execution": execution,
            "candidates": [item for item in candidates if item["id"] in visible], "excluded": excluded,
            "preferences": profile,
            "fallback": "Review gaps manually; any new implementation needs verification." if execution["uncovered"] else None}
