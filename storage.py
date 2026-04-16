#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "golium.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshot_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  source_file TEXT NOT NULL,
  league_key TEXT,
  league_name TEXT,
  fixtures_count INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshot_runs_created_at ON snapshot_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_runs_league_key ON snapshot_runs(league_key);
"""

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn

def save_snapshot(payload: dict[str, Any], source_file: str = 'data.json') -> int:
    league_key = payload.get('leagueKey')
    league_name = payload.get('league')
    fixtures_count = len(payload.get('fixtures', []))

    if payload.get('leagues'):
        league_key = 'multi'
        league_name = 'multi'
        fixtures_count = sum(len((v or {}).get('fixtures', [])) for v in payload.get('leagues', {}).values())

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO snapshot_runs(source_file, league_key, league_name, fixtures_count, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_file, league_key, league_name, fixtures_count, json.dumps(payload, ensure_ascii=False)),
        )
        return int(cur.lastrowid)

def latest_snapshot(limit: int = 5) -> list[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT id, created_at, source_file, league_key, league_name, fixtures_count FROM snapshot_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()
