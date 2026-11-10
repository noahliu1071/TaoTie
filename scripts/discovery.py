"""Discover local skill packages without loading their instructions as code."""

import hashlib
import os
import re
import tomllib
from pathlib import Path


def roots_for(config):
    if "roots" in config:
        return config["roots"]
    codex = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return [str(codex / "skills"), str(Path.home() / ".agents" / "skills")]


def path_key(path):
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def exclusions(config):
    excluded = {path_key(path) for path in config.get("exclude", [])}
    host = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    if host.is_file():
        with host.open("rb") as stream:
            items = tomllib.load(stream).get("skills", {}).get("config", [])
        excluded.update(path_key(item["path"]) for item in items
                        if item.get("enabled") is False and isinstance(item.get("path"), str))
    return excluded


def is_excluded(path, excluded):
    resolved = Path(path_key(path))
    return any(str(parent) in excluded for parent in (resolved, *resolved.parents))


def metadata(entry):
    with entry.open(encoding="utf-8-sig") as stream:
        lines = []
        if stream.readline().strip() == "---":
            for line in stream:
                if line.strip() == "---" or len(lines) >= 100:
                    break
                lines.append(line.rstrip())
    fields = {}
    for key in ("name", "description"):
        match = re.search(rf"^{key}:[ \t]*([^\n]*)(\n(?:[ \t]+[^\n]*\n?)*)",
                          "\n".join(lines), re.M)
        if match:
            value = match[1].strip()
            if not value or value.startswith((">", "|")):
                value = " ".join(match[2].split())
            fields[key] = value.strip("\"'")
    return {"name": fields.get("name") or entry.parent.name, "description": fields.get("description", "")}


def scan(roots, excluded, skip, snapshot, self_root):
    seen, errors = {}, []
    for raw in roots:
        try:
            root = Path(raw).expanduser().resolve(strict=True)
            if root.is_file():
                if root.name != "SKILL.md":
                    raise ValueError("Expected a skill directory or SKILL.md")
                root = root.parent
            for base, dirs, names in os.walk(root, followlinks=False, onerror=lambda error: errors.append(str(error))):
                folder = Path(base)
                if folder == self_root or is_excluded(folder, excluded):
                    dirs.clear()
                    continue
                dirs[:] = sorted(name for name in dirs if name not in skip and not (folder / name).is_symlink())
                entry = folder / "SKILL.md"
                if "SKILL.md" not in names or entry.is_symlink() or is_excluded(entry, excluded):
                    continue
                dirs.clear()
                key = "skill-" + hashlib.sha256(path_key(folder).encode()).hexdigest()[:20]
                if key not in seen:
                    try:
                        seen[key] = {**snapshot(folder), **metadata(entry)}
                    except (OSError, ValueError) as error:
                        errors.append(str(error))
        except (OSError, ValueError) as error:
            errors.append(str(error))
    return seen, errors
