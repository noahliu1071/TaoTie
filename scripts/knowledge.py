"""Local, review-gated knowledge store for Taotie. Python 3.11+, stdlib only."""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


LEVELS = ("read", "runnable", "reproduced", "reusable")
SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "taotie-runs"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    record TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
    record TEXT NOT NULL,
    revision INTEGER NOT NULL,
    candidate TEXT UNIQUE REFERENCES candidates(id),
    audit TEXT NOT NULL,
    PRIMARY KEY (record, revision)
);
"""


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def snapshot(raw_path):
    path = Path(raw_path).expanduser().resolve(strict=True)
    if path.is_file():
        return {"path": str(path), "sha256": file_hash(path)}
    if not (path / "SKILL.md").is_file():
        raise ValueError(f"Use a file or a directory containing SKILL.md: {path}")
    manifest = {}
    for base, dirs, names in os.walk(path, followlinks=False, onerror=raise_walk_error):
        dirs[:] = [name for name in dirs if name not in SKIP and not (Path(base) / name).is_symlink()]
        for name in names:
            entry = Path(base) / name
            if not entry.is_symlink() and entry.is_file() and name != ".git":
                manifest[entry.relative_to(path).as_posix()] = file_hash(entry)
    return {"path": str(path), "sha256": digest(manifest), "files": manifest}


def raise_walk_error(error):
    raise error


def changed_paths(payload):
    changed = []
    for saved in payload["sources"] + payload["artifacts"]:
        try:
            if snapshot(saved["path"])["sha256"] == saved["sha256"]:
                continue
        except (OSError, ValueError):
            pass
        changed.append(saved["path"])
    return changed


def required_text(value, key):
    if not isinstance(value.get(key), str) or not value[key].strip():
        raise ValueError(f"Required nonempty text: {key}")


def load_card(path):
    card = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(card, dict):
        raise ValueError("Expected a capability card object")
    for key in ("title", "purpose", "method", "use_when", "avoid_when", "inputs", "outputs", "dependencies", "overlap", "conflicts", "provenance"):
        required_text(card, key)
    if card.get("level") not in LEVELS:
        raise ValueError(f"Expected verification level from {LEVELS}")
    evidence = card.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Include at least one source observation")
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("Expected an evidence object")
        for key in ("locator", "observation"):
            required_text(item, key)
    return card


def latest(db, record=None):
    return db.execute(
        """SELECT r.*, c.payload FROM revisions r
           LEFT JOIN candidates c ON r.candidate = c.id
           WHERE r.revision = (SELECT MAX(revision) FROM revisions WHERE record = r.record)
           AND (? IS NULL OR r.record = ?) ORDER BY r.record""",
        (record, record),
    ).fetchall()


def candidate(db, key):
    row = db.execute("SELECT payload FROM candidates WHERE id = ?", (key,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown candidate: {key}")
    return json.loads(row["payload"])


def dispatch(db, args):
    if args.command == "propose":
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.record):
            raise ValueError("Use a record ID of 1–64 lowercase letters, digits or hyphens")
        card = load_card(args.card)
        if card["level"] != "read" and not args.artifact:
            raise ValueError("Verification above read requires a local evidence artifact")
        sources = [snapshot(path) for path in args.source]
        artifacts = [snapshot(path) for path in args.artifact]
        prior = latest(db, args.record)
        payload = {
            "record": args.record, "base_revision": prior[0]["revision"] if prior else 0,
            "card": card, "sources": sources, "artifacts": artifacts,
        }
        key = digest(payload)
        db.execute("INSERT OR IGNORE INTO candidates VALUES (?, ?, ?)", (key, args.record, encode(payload)))
        return {"candidate": key, **payload}
    if args.command == "pending":
        return [dict(row) for row in db.execute(
            """SELECT id, record FROM candidates c WHERE NOT EXISTS
               (SELECT 1 FROM revisions r WHERE r.candidate = c.id)
               AND json_extract(c.payload, '$.base_revision') = COALESCE(
               (SELECT MAX(revision) FROM revisions r WHERE r.record = c.record), 0)
               ORDER BY record, id"""
        )]
    if args.command in ("review", "approve"):
        payload = candidate(db, args.candidate)
        prior = latest(db, payload["record"])
        previous = prior[0] if prior else None
        current_revision = previous["revision"] if previous else 0
        changed = changed_paths(payload)
        review_digest = digest(payload)
        if args.command == "review":
            old_card = json.loads(previous["payload"])["card"] if previous and previous["payload"] else None
            return {"candidate": args.candidate, "review_digest": review_digest, **payload,
                    "previous_card": old_card, "current_revision": current_revision, "changed_paths": changed}
        if args.digest != review_digest or args.candidate != review_digest:
            raise ValueError("Review digest mismatch")
        if not args.quote.strip() or not args.reference.strip():
            raise ValueError("Provide the user's approval quote and its conversation reference")
        if changed:
            raise ValueError(f"Source or evidence changed: {changed}; review a new proposal")
        if previous and previous["candidate"] == args.candidate:
            return {"record": payload["record"], "revision": current_revision, "status": "already-approved"}
        if current_revision != payload["base_revision"]:
            raise ValueError("Record changed since proposal; create and review a new candidate")
        return append_revision(db, payload["record"], current_revision + 1, args.candidate,
                               {"quote": args.quote, "reference": args.reference})
    if args.command == "history":
        return [dict(row) for row in db.execute(
            "SELECT revision, candidate, audit FROM revisions WHERE record = ? ORDER BY revision", (args.record,)
        )]
    if args.command in ("show", "revoke"):
        rows = latest(db, args.record)
        if not rows:
            raise ValueError(f"Unknown record: {args.record}")
        row = rows[0]
        if args.command == "revoke":
            if not args.reason.strip():
                raise ValueError("Provide a nonempty reason")
            if row["candidate"] is None:
                return {"record": args.record, "revision": row["revision"], "status": "already-revoked"}
            return append_revision(db, args.record, row["revision"] + 1, None, {"reason": args.reason})
        return record_view(row)
    terms = args.query.casefold().split()
    matches = []
    for row in latest(db):
        if row["payload"] is None:
            continue
        card = json.loads(row["payload"])["card"]
        score = sum(term in encode(card).casefold() for term in terms)
        if score or not terms:
            matches.append((score, row))
    return [
        {key: value for key, value in record_view(row).items()
         if key in {"record", "revision", "status", "title", "purpose", "level", "changed_paths"}}
        for _, row in sorted(matches, key=lambda item: -item[0])[:args.limit]
    ]


def append_revision(db, record, revision, key, audit):
    audit["at"] = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO revisions VALUES (?, ?, ?, ?)", (record, revision, key, encode(audit)))
    return {"record": record, "revision": revision, "status": "approved" if key else "revoked"}


def record_view(row):
    result = {"record": row["record"], "revision": row["revision"], "audit": json.loads(row["audit"])}
    if row["candidate"] is None:
        return {**result, "status": "revoked"}
    payload = json.loads(row["payload"])
    changed = changed_paths(payload)
    return {**result, **payload, "title": payload["card"]["title"], "purpose": payload["card"]["purpose"],
            "level": payload["card"]["level"], "status": "stale" if changed else "current", "changed_paths": changed}


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--db", type=Path, default=Path(os.environ.get("TAOTIE_DB", Path.home() / ".taotie" / "knowledge.sqlite3")))
    sub = cli.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot").add_argument("paths", nargs="+")
    propose = sub.add_parser("propose")
    propose.add_argument("record")
    propose.add_argument("--card", required=True)
    propose.add_argument("--source", action="append", required=True)
    propose.add_argument("--artifact", action="append", default=[])
    sub.add_parser("pending")
    sub.add_parser("review").add_argument("candidate")
    approve = sub.add_parser("approve")
    approve.add_argument("candidate")
    for option in ("digest", "quote", "reference"):
        approve.add_argument(f"--{option}", required=True)
    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--limit", type=int, choices=range(1, 21), default=5, metavar="1–20")
    for command in ("show", "history", "revoke"):
        action = sub.add_parser(command)
        action.add_argument("record")
        if command == "revoke":
            action.add_argument("--reason", required=True)
    return cli


def main():
    cli = parser()
    args = cli.parse_args()
    try:
        if args.command == "snapshot":
            result = [snapshot(path) for path in args.paths]
        else:
            path = args.db.expanduser().resolve()
            writes = args.command in {"propose", "approve", "revoke"}
            if writes:
                path.parent.mkdir(parents=True, exist_ok=True)
            target = str(path) if writes else f"{path.as_uri()}?mode=ro" if path.exists() else ":memory:"
            with closing(sqlite3.connect(target, uri=not writes)) as db, db:
                db.row_factory = sqlite3.Row
                if writes or target == ":memory:":
                    db.executescript(SCHEMA)
                if writes:
                    db.execute("BEGIN IMMEDIATE")
                result = dispatch(db, args)
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error) as error:
        cli.exit(1, f"taotie: {error}\n")


if __name__ == "__main__":
    main()
