#!/usr/bin/env python3
"""
Offline Tamper-Evident Audit Chain Verifier CLI.

Traverses the RecoverIQ audit log stored in SQLite and cryptographically verifies
every SHA-256 link in the chain. Detects:
  - Unauthorized row modification (message, actor, event_type, timestamp)
  - Deleted rows (broken parent hash link)
  - Inserted / injected rows
"""
import sys
import os
import argparse
import sqlite3
import json
import hashlib

# Add parent directory to path if running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def compute_event_hash(prev_hash, payment_id, actor, event_type, message, timestamp_str):
    prev = prev_hash or "GENESIS"
    canonical_payload = json.dumps(
        {
            "actor": actor,
            "event_type": event_type,
            "message": message,
            "payment_id": payment_id,
            "timestamp": timestamp_str,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    raw = f"{prev}||{canonical_payload}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_db(db_path: str, payment_id: str | None = None) -> bool:
    if not os.path.exists(db_path):
        print(f"[ERROR] Database file not found at: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT id, payment_id, timestamp, actor, event_type, message, prev_hash, event_hash FROM audit_logs"
    params = []
    if payment_id:
        query += " WHERE payment_id = ?"
        params.append(payment_id)
    query += " ORDER BY id ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    total = len(rows)
    print(f"\n========================================================")
    print(f" RecoverIQ Cryptographic Audit Chain Verifier")
    print(f" Target Database: {db_path}")
    print(f" Total Log Records to Verify: {total}")
    if payment_id:
        print(f" Filter: payment_id = {payment_id}")
    print(f"========================================================\n")

    if total == 0:
        print("[INFO] Audit log is empty. Nothing to verify.")
        return True

    for i, row in enumerate(rows):
        row_id = row["id"]
        p_id = row["payment_id"]
        ts_str = str(row["timestamp"]).replace(" ", "T")
        actor = row["actor"]
        ev_type = row["event_type"]
        msg = row["message"]
        stored_prev = row["prev_hash"]
        stored_hash = row["event_hash"]

        # 1. Recompute hash
        recomputed = compute_event_hash(stored_prev, p_id, actor, ev_type, msg, ts_str)
        if stored_hash != recomputed:
            print(f"❌ [TAMPER DETECTED] Log Entry #{row_id} (Payment: {p_id}) has been corrupted!")
            print(f"   Stored Hash:     {stored_hash}")
            print(f"   Recomputed Hash: {recomputed}")
            print(f"   Actor: {actor} | Event: {ev_type}")
            print(f"   Message: {msg[:100]}...")
            return False

        # 2. Check chain linkage (for global sequence)
        if payment_id is None and i > 0:
            prev_row = rows[i - 1]
            if stored_prev != prev_row["event_hash"]:
                print(f"❌ [BROKEN CHAIN LINK] Log Entry #{row_id} does not link to preceding Entry #{prev_row['id']}!")
                print(f"   Expected prev_hash: {prev_row['event_hash']}")
                print(f"   Found prev_hash:    {stored_prev}")
                return False

    print(f"✅ [SUCCESS] All {total} audit entries are cryptographically intact and unmodified.")
    print(f"   Genesis Hash: {rows[0]['prev_hash'] or 'GENESIS'}")
    print(f"   Terminal Hash: {rows[-1]['event_hash']}\n")
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify RecoverIQ SHA-256 audit log integrity.")
    parser.add_argument(
        "--db-path",
        default="recoveriq.db",
        help="Path to SQLite database file (default: recoveriq.db)",
    )
    parser.add_argument(
        "--payment-id",
        default=None,
        help="Optional payment_id filter to verify single transaction audit trail",
    )
    args = parser.parse_args()

    success = verify_db(args.db_path, args.payment_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
