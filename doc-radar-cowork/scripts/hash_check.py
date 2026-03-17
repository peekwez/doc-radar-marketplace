#!/usr/bin/env python3
"""
hash_check.py
-------------
Computes a SHA-256 hash of document content (text or file) and checks it
against the seen-hashes log. Returns JSON to stdout.

Usage:
    python3 hash_check.py --content "raw document text here"
    python3 hash_check.py --file "/path/to/document.pdf"

Output (new document):
    {"status": "new", "hash": "<sha256hex>"}

Output (already seen):
    {"status": "duplicate", "hash": "<sha256hex>",
     "first_seen": "<ISO datetime>", "source_id": "<id>"}
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_DIR   = Path(__file__).parent.parent
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
HASHES_LOG  = TRACKER_DIR / "seen_hashes.jsonl"

TRACKER_DIR.mkdir(parents=True, exist_ok=True)


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_seen_hashes() -> dict:
    """Returns dict of {hash: {first_seen, source_id}}"""
    seen = {}
    if not HASHES_LOG.exists():
        return seen
    with open(HASHES_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                seen[entry["hash"]] = {
                    "first_seen": entry["first_seen"],
                    "source_id":  entry.get("source_id", "unknown"),
                }
            except (json.JSONDecodeError, KeyError):
                continue
    return seen


def record_hash(digest: str, source_id: str = "unknown") -> None:
    """Append a new hash to the seen-hashes log."""
    entry = {
        "hash":       digest,
        "first_seen": datetime.now(timezone.utc).isoformat(),
        "source_id":  source_id,
    }
    with open(HASHES_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--content",   help="Raw text content to hash")
    group.add_argument("--file",      help="Path to file to hash")
    parser.add_argument("--source-id", default="unknown",
                        help="Source identifier (gmail message ID or file path)")
    parser.add_argument("--check-only", action="store_true",
                        help="Check for duplicate without recording to seen-hashes log")
    args = parser.parse_args()

    # Compute hash
    if args.content:
        digest = sha256_of_text(args.content)
    else:
        try:
            digest = sha256_of_file(args.file)
        except FileNotFoundError:
            print(json.dumps({"status": "error", "error": f"File not found: {args.file}"}))
            sys.exit(1)

    # Check against log
    seen = load_seen_hashes()

    if digest in seen:
        result = {
            "status":     "duplicate",
            "hash":       digest,
            "first_seen": seen[digest]["first_seen"],
            "source_id":  seen[digest]["source_id"],
        }
    else:
        if not args.check_only:
            record_hash(digest, source_id=args.source_id or "unknown")
        result = {
            "status": "new",
            "hash":   digest,
        }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
