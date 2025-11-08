#!/usr/bin/env python3
"""Utility to inspect the DebGPT vector-service SQLite message store."""

import argparse
import datetime as dt
import json
import pathlib
import sqlite3
import sys
from typing import Iterable, List, Tuple


Row = Tuple[str, str, str, int]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dump chat messages tracked by the vector microservice.")
    parser.add_argument(
        "--sqlite-path",
        default="messages.db",
        help="Path to the SQLite database created by the vector service.")
    parser.add_argument(
        "--conversation-id",
        help="Limit output to a single conversation identifier.")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of rows to emit (0 means no limit).")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a human-readable table.")
    return parser.parse_args()


def _fetch_rows(db_path: pathlib.Path,
                conversation_id: str | None,
                limit: int) -> List[Row]:
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        sql = [
            "SELECT conversation_id, role, text, timestamp FROM messages"
        ]
        params: List[object] = []
        if conversation_id:
            sql.append("WHERE conversation_id = ?")
            params.append(conversation_id)
        sql.append("ORDER BY timestamp ASC")
        if limit and limit > 0:
            sql.append("LIMIT ?")
            params.append(limit)
        query = " ".join(sql)
        cur = conn.execute(query, params)
        rows = [(row["conversation_id"], row["role"], row["text"],
                 row["timestamp"]) for row in cur.fetchall()]
        return rows
    finally:
        conn.close()


def _format_timestamp(epoch: int) -> str:
    try:
        return dt.datetime.fromtimestamp(epoch).isoformat()
    except (TypeError, ValueError, OSError):
        return str(epoch)


def _print_json(rows: Iterable[Row]) -> None:
    payload = []
    for conversation_id, role, text, timestamp in rows:
        payload.append({
            "conversation_id": conversation_id,
            "role": role,
            "text": text,
            "timestamp": timestamp,
        })
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _print_table(rows: Iterable[Row]) -> None:
    def _row_to_lines(item: Row) -> List[str]:
        conv, role, text, epoch = item
        when = _format_timestamp(epoch)
        lines = [
            f"conversation: {conv}",
            f"role        : {role}",
            f"timestamp   : {when}",
            f"text        : {text}",
        ]
        return lines

    for idx, row in enumerate(rows, start=1):
        for line in _row_to_lines(row):
            print(line)
        if idx:
            print("-" * 60)


def main() -> None:
    args = _parse_args()
    db_path = pathlib.Path(args.sqlite_path).expanduser().resolve()
    rows = _fetch_rows(db_path, args.conversation_id, args.limit)
    if args.json:
        _print_json(rows)
    else:
        _print_table(rows)


if __name__ == "__main__":
    main()
