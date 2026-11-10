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

import discovery
import routing


LEVELS = ("read", "runnable", "reproduced", "reusable")
SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "taotie-runs"}
PREFERENCES = ("like", "avoid", "favorite", "reject")
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
CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS discoveries (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dismissals (id TEXT PRIMARY KEY, reason TEXT NOT NULL);
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
    if "routing" in card:
        routing.validate_routing(card["routing"])
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


def has_table(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def config(db):
    row = db.execute("SELECT payload FROM settings WHERE id = 1").fetchone() if has_table(db, "settings") else None
    return json.loads(row["payload"]) if row else {}


def get_discovery(db, key):
    row = db.execute("SELECT payload FROM discoveries WHERE id = ?", (key,)).fetchone() if has_table(db, "discoveries") else None
    if not row:
        raise ValueError(f"Unknown discovery: {key}")
    return json.loads(row["payload"])


def dismissed(db, key):
    return has_table(db, "dismissals") and db.execute("SELECT 1 FROM dismissals WHERE id = ?", (key,)).fetchone() is not None


def current_revision(db, record):
    rows = latest(db, record)
    return rows[0]["revision"] if rows else 0


def save_candidate(db, payload):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", payload["record"]):
        raise ValueError("Use a record ID of 1–64 lowercase letters, digits or hyphens")
    prior = db.execute(
        """SELECT c.payload FROM revisions r JOIN candidates c ON r.candidate = c.id
           WHERE r.record = ? ORDER BY r.revision DESC LIMIT 1""", (payload["record"],)
    ).fetchone()
    if prior:
        old_kind = json.loads(prior["payload"])["card"].get("kind") == "preference"
        if old_kind != (payload["card"].get("kind") == "preference"):
            raise ValueError("Use a different record ID for a different record type")
    key = digest(payload)
    db.execute("INSERT OR IGNORE INTO candidates VALUES (?, ?, ?)", (key, payload["record"], encode(payload)))
    return {"candidate": key, **payload}


def active_records(db):
    return [(row["record"], json.loads(row["payload"])) for row in latest(db) if row["payload"] is not None]


def preference_profile(records):
    profile = {action: [] for action in PREFERENCES}
    for key, payload in records:
        card = payload["card"]
        if card.get("kind") == "preference":
            if card["action"] in ("like", "avoid"):
                profile[card["action"]].append({"id": key, "value": card["value"], "scope": card["scope"]})
            else:
                profile[card["action"]].append(card["value"])
    return profile


def payload_status(payload, excluded, changed=None):
    if any(discovery.is_excluded(source["path"], excluded)
           or (source.get("files") is not None and discovery.is_excluded(Path(source["path"]) / "SKILL.md", excluded))
           for source in payload["sources"]):
        return "disabled"
    return "stale" if (changed_paths(payload) if changed is None else changed) else "current"


def discoveries_pending(db):
    if not has_table(db, "discoveries"):
        return []
    done = set()
    for row in db.execute("SELECT payload FROM candidates"):
        item = json.loads(row["payload"]).get("discovery")
        if item:
            done.add((item["id"], item["sha256"]))
    excluded = discovery.exclusions(config(db))
    results = []
    for row in db.execute("SELECT id, payload FROM discoveries ORDER BY id"):
        item = json.loads(row["payload"])
        if ((row["id"], item["sha256"]) not in done and not dismissed(db, discovery_version(row["id"], item))
                and (Path(item["path"]) / "SKILL.md").is_file()
                and not discovery.is_excluded(Path(item["path"]) / "SKILL.md", excluded)):
            results.append({"id": row["id"], **{key: item[key] for key in ("name", "description", "path", "sha256")}})
    return results


def discovery_version(key, item):
    return f"{key}:{item['sha256']}"


def reviewed_pending(db):
    rows = db.execute(
        """SELECT id, record, payload FROM candidates c WHERE NOT EXISTS
           (SELECT 1 FROM revisions r WHERE r.candidate = c.id)
           AND json_extract(c.payload, '$.base_revision') = COALESCE(
           (SELECT MAX(revision) FROM revisions r WHERE r.record = c.record), 0)
           ORDER BY record, id"""
    )
    return [row for row in rows if not dismissed(db, row["id"])]


def manage_discovery(db, args):
    settings = config(db)
    if args.command == "configure":
        for key in ("roots", "exclude"):
            values = getattr(args, key)
            if values is not None:
                settings[key] = [str(Path(path).expanduser().resolve()) for path in values]
        if args.clear_excludes:
            settings["exclude"] = []
        db.execute("INSERT OR REPLACE INTO settings VALUES (1, ?)", (encode(settings),))
        return {"roots": discovery.roots_for(settings), "exclude": settings.get("exclude", [])}
    excluded = discovery.exclusions(settings)
    if args.command == "inspect":
        item = get_discovery(db, args.id)
        status = payload_status({"sources": [item], "artifacts": []}, excluded)
        return {"id": args.id, "status": status, "entry": str(Path(item["path"]) / "SKILL.md"), **item}
    seen, errors = discovery.scan(discovery.roots_for(settings) + args.root, excluded, SKIP, snapshot,
                                  Path(__file__).resolve().parents[1])
    prior = {row["id"]: json.loads(row["payload"])["sha256"] for row in db.execute("SELECT * FROM discoveries")}
    changes = []
    for key, item in seen.items():
        if prior.get(key) == item["sha256"]:
            continue
        db.execute("INSERT OR REPLACE INTO discoveries VALUES (?, ?)", (key, encode(item)))
        changes.append({"id": key, "name": item["name"], "path": item["path"], "change": "updated" if key in prior else "new"})
    return {"scanned": len(seen), "changes": changes, "errors": errors}


def dispatch(db, args):
    if args.command == "rebuild-index":
        db.execute("REINDEX")
        return {"integrity": [row[0] for row in db.execute("PRAGMA quick_check")]}
    if args.command in ("configure", "scan", "inspect"):
        return manage_discovery(db, args)
    if args.command == "discoveries":
        return discoveries_pending(db)
    if args.command == "preference":
        if not args.value.strip() or not args.scope.strip():
            raise ValueError("Preference value and scope must not be empty")
        validate_preference_target(db, args.action, args.value)
        if args.action in ("favorite", "reject") and args.scope != "global":
            raise ValueError("Use like/avoid to record a scoped preference")
        return save_candidate(db, {
            "record": args.record, "base_revision": current_revision(db, args.record),
            "card": {"kind": "preference", "title": f"{args.action}: {args.value}",
                     "purpose": args.scope, "scope": args.scope, "action": args.action, "value": args.value},
            "sources": [], "artifacts": [],
        })
    if args.command in ("dismiss", "reopen"):
        key = args.id
        if key.startswith("skill-"):
            key = discovery_version(key, get_discovery(db, key))
        else:
            candidate(db, key)
            if db.execute("SELECT 1 FROM revisions WHERE candidate = ?", (key,)).fetchone():
                raise ValueError("Use revoke for a confirmed record")
        if args.command == "reopen":
            db.execute("DELETE FROM dismissals WHERE id = ?", (key,))
        else:
            if not args.reason.strip():
                raise ValueError("Provide a nonempty reason")
            db.execute("INSERT OR IGNORE INTO dismissals VALUES (?, ?)", (key, args.reason))
        return {"id": args.id, "status": "reopened" if args.command == "reopen" else "dismissed"}
    if args.command == "restore-proposal":
        row = db.execute("SELECT candidate FROM revisions WHERE record = ? AND revision = ?",
                         (args.record, args.revision)).fetchone()
        if not row or not row["candidate"]:
            raise ValueError("Choose a previously approved revision")
        payload = candidate(db, row["candidate"])
        require_current(db, payload)
        payload["base_revision"] = current_revision(db, args.record)
        payload["restored_from"] = args.revision
        return save_candidate(db, payload)
    if args.command in ("profile", "route"):
        records = active_records(db)
        profile = preference_profile(records)
        if args.command == "profile":
            return profile
        brief = json.loads(Path(args.brief).read_text(encoding="utf-8-sig"))
        excluded = discovery.exclusions(config(db))
        return routing.route(brief, records, profile, file_hash, args.limit,
                             lambda payload: payload_status(payload, excluded))
    if args.command in ("status", "report"):
        return summary(db, args)
    if args.command == "propose":
        card = load_card(args.card)
        if card.get("kind") == "preference":
            raise ValueError("Use the preference command for a preference")
        if card["level"] != "read" and not args.artifact:
            raise ValueError("Verification above read requires a local evidence artifact")
        sources = [snapshot(path) for path in args.source]
        artifacts = [snapshot(path) for path in args.artifact]
        if not sources and not args.discovery:
            raise ValueError("Provide --source or --discovery")
        payload = {
            "record": args.record, "base_revision": current_revision(db, args.record),
            "card": card, "sources": sources, "artifacts": artifacts,
        }
        if args.discovery:
            item = get_discovery(db, args.discovery)
            if dismissed(db, discovery_version(args.discovery, item)):
                raise ValueError("Reopen the dismissed discovery before proposing it")
            payload["discovery"] = {"id": args.discovery, "sha256": item["sha256"]}
            sources.insert(0, item)
        require_current(db, payload)
        return save_candidate(db, payload)
    if args.command == "pending":
        return [{"id": row["id"], "record": row["record"]} for row in reviewed_pending(db)]
    if args.command in ("review", "approve"):
        payload = candidate(db, args.candidate)
        prior = latest(db, payload["record"])
        previous = prior[0] if prior else None
        revision = previous["revision"] if previous else 0
        changed = changed_paths(payload)
        review_digest = digest(payload)
        if args.command == "review":
            old_card = json.loads(previous["payload"])["card"] if previous and previous["payload"] else None
            return {"candidate": args.candidate, "review_digest": review_digest, **payload,
                    "previous_card": old_card, "current_revision": revision, "changed_paths": changed,
                    "source_state": payload_status(payload, discovery.exclusions(config(db)), changed),
                    "dismissed": dismissed(db, args.candidate)}
        if args.digest != review_digest or args.candidate != review_digest:
            raise ValueError("Review digest mismatch")
        if not args.quote.strip() or not args.reference.strip():
            raise ValueError("Provide the user's approval quote and its conversation reference")
        if dismissed(db, args.candidate):
            raise ValueError("Candidate is dismissed; reopen it before approval")
        require_current(db, payload, changed)
        if previous and previous["candidate"] == args.candidate:
            return {"record": payload["record"], "revision": revision, "status": "already-approved"}
        if revision != payload["base_revision"]:
            raise ValueError("Record changed since proposal; create and review a new candidate")
        if payload["card"].get("kind") == "preference":
            validate_preference_target(db, payload["card"]["action"], payload["card"]["value"])
        return append_revision(db, payload["record"], revision + 1, args.candidate,
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
        return record_view(row, discovery.exclusions(config(db)))
    terms = args.query.casefold().split()
    matches = []
    excluded = discovery.exclusions(config(db))
    for row in latest(db):
        if row["payload"] is None:
            continue
        card = json.loads(row["payload"])["card"]
        score = sum(term in encode(card).casefold() for term in terms)
        if score or not terms:
            matches.append((score, row))
    return [
        {key: value for key, value in record_view(row, excluded).items()
         if key in {"record", "revision", "status", "title", "purpose", "level", "changed_paths"}}
        for _, row in sorted(matches, key=lambda item: -item[0])[:args.limit]
    ]


def append_revision(db, record, revision, key, audit):
    audit["at"] = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO revisions VALUES (?, ?, ?, ?)", (record, revision, key, encode(audit)))
    return {"record": record, "revision": revision, "status": "approved" if key else "revoked"}


def record_view(row, excluded):
    result = {"record": row["record"], "revision": row["revision"], "audit": json.loads(row["audit"])}
    if row["candidate"] is None:
        return {**result, "status": "revoked"}
    payload = json.loads(row["payload"])
    changed = changed_paths(payload)
    return {**result, **payload, "title": payload["card"]["title"], "purpose": payload["card"]["purpose"],
            "level": payload["card"].get("level"), "status": payload_status(payload, excluded, changed), "changed_paths": changed}


def require_current(db, payload, changed=None):
    state = payload_status(payload, discovery.exclusions(config(db)), changed)
    if state != "current":
        raise ValueError(f"Source or evidence changed or is disabled ({state}); review current material before proposing or approving")


def validate_preference_target(db, action, value):
    if action in ("favorite", "reject"):
        rows = latest(db, value)
        if not rows or not rows[0]["payload"] or json.loads(rows[0]["payload"])["card"].get("kind") == "preference":
            raise ValueError("Favorite/reject needs an active confirmed capability record")


def summary(db, args):
    settings = config(db)
    pending = reviewed_pending(db)
    found = discoveries_pending(db)
    records = active_records(db)
    if args.command == "status":
        return {"roots": discovery.roots_for(settings), "confirmed": len(records),
                "pending_review": len(pending), "pending_discovery": len(found)}
    reviews = [{"id": row["id"], **json.loads(row["payload"])} for row in pending]
    if args.reviewed_only:
        return {"pending_review": reviews}
    return {"confirmed": [{"id": key, "title": payload["card"]["title"], "level": payload["card"].get("level")}
                          for key, payload in records],
            "discovered": found, "pending_review": reviews}


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--db", type=Path, default=Path(os.environ.get("TAOTIE_DB", Path.home() / ".taotie" / "knowledge.sqlite3")))
    sub = cli.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot").add_argument("paths", nargs="+")
    settings = sub.add_parser("configure")
    settings.add_argument("--root", dest="roots", action="append")
    settings.add_argument("--exclude", action="append")
    settings.add_argument("--clear-excludes", action="store_true")
    sub.add_parser("scan").add_argument("--root", action="append", default=[])
    sub.add_parser("discoveries")
    sub.add_parser("inspect").add_argument("id")
    propose = sub.add_parser("propose")
    propose.add_argument("record")
    propose.add_argument("--card", required=True)
    propose.add_argument("--source", action="append", default=[])
    propose.add_argument("--discovery")
    propose.add_argument("--artifact", action="append", default=[])
    sub.add_parser("pending")
    sub.add_parser("status")
    sub.add_parser("report").add_argument("--reviewed-only", action="store_true")
    sub.add_parser("rebuild-index")
    pref = sub.add_parser("preference")
    pref.add_argument("record")
    pref.add_argument("action", choices=PREFERENCES)
    pref.add_argument("value")
    pref.add_argument("--scope", default="global")
    sub.add_parser("profile")
    for command in ("dismiss", "reopen"):
        action = sub.add_parser(command)
        action.add_argument("id")
        if command == "dismiss":
            action.add_argument("--reason", required=True)
    restore = sub.add_parser("restore-proposal")
    restore.add_argument("record")
    restore.add_argument("--revision", type=int, required=True)
    sub.add_parser("review").add_argument("candidate")
    approve = sub.add_parser("approve")
    approve.add_argument("candidate")
    for option in ("digest", "quote", "reference"):
        approve.add_argument(f"--{option}", required=True)
    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--limit", type=int, choices=range(1, 21), default=5, metavar="1–20")
    route = sub.add_parser("route")
    route.add_argument("--brief", required=True)
    route.add_argument("--limit", type=int, choices=range(1, 21), default=5, metavar="1–20")
    for command in ("show", "history", "revoke"):
        action = sub.add_parser(command)
        action.add_argument("record")
        if command == "revoke":
            action.add_argument("--reason", required=True)
    return cli


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    cli = parser()
    args = cli.parse_args()
    try:
        if args.command == "snapshot":
            result = [snapshot(path) for path in args.paths]
        else:
            path = args.db.expanduser().resolve()
            writes = args.command in {"propose", "approve", "revoke", "configure", "scan", "preference",
                                      "dismiss", "reopen", "restore-proposal", "rebuild-index"}
            if writes:
                path.parent.mkdir(parents=True, exist_ok=True)
            target = str(path) if writes else f"{path.as_uri()}?mode=ro" if path.exists() else ":memory:"
            with closing(sqlite3.connect(target, uri=not writes)) as db, db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA foreign_keys = ON")
                if writes or target == ":memory:":
                    db.executescript(SCHEMA)
                if writes:
                    db.execute("BEGIN IMMEDIATE")
                result = dispatch(db, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error) as error:
        cli.exit(1, f"taotie: {error}\n")


if __name__ == "__main__":
    main()
