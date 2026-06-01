from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from app.settings import get_settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sites (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  allowed_origins TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS visitors (
  id TEXT PRIMARY KEY,
  site_id TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  first_path TEXT,
  last_path TEXT,
  user_agent_hash TEXT,
  ip_hash TEXT,
  FOREIGN KEY (site_id) REFERENCES sites(id)
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  site_id TEXT NOT NULL,
  visitor_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  landing_path TEXT,
  exit_path TEXT,
  referrer_url TEXT,
  referrer_domain TEXT,
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  pageview_count INTEGER NOT NULL DEFAULT 0,
  heartbeat_count INTEGER NOT NULL DEFAULT 0,
  duration_seconds INTEGER,
  bounced INTEGER,
  FOREIGN KEY (site_id) REFERENCES sites(id),
  FOREIGN KEY (visitor_id) REFERENCES visitors(id)
);

CREATE TABLE IF NOT EXISTS pageviews (
  id TEXT PRIMARY KEY,
  site_id TEXT NOT NULL,
  visitor_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  page_url TEXT NOT NULL,
  page_host TEXT,
  page_path TEXT NOT NULL,
  page_query TEXT,
  page_title TEXT,

  referrer_url TEXT,
  referrer_domain TEXT,

  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  utm_term TEXT,
  utm_content TEXT,

  browser_name TEXT,
  browser_version TEXT,
  os_name TEXT,
  os_version TEXT,
  device_type TEXT,
  user_agent_hash TEXT,

  language TEXT,
  timezone TEXT,
  screen_width INTEGER,
  screen_height INTEGER,
  viewport_width INTEGER,
  viewport_height INTEGER,

  load_time_ms INTEGER,
  navigation_type TEXT,

  ip_hash TEXT,
  country TEXT,
  region TEXT,

  is_bot INTEGER NOT NULL DEFAULT 0,
  bot_reason TEXT,

  raw_payload TEXT,

  FOREIGN KEY (site_id) REFERENCES sites(id),
  FOREIGN KEY (visitor_id) REFERENCES visitors(id),
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  site_id TEXT NOT NULL,
  visitor_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  page_url TEXT,
  page_path TEXT,

  event_name TEXT,
  target_url TEXT,
  target_domain TEXT,
  value_number REAL,
  value_text TEXT,
  props_json TEXT,

  FOREIGN KEY (site_id) REFERENCES sites(id),
  FOREIGN KEY (visitor_id) REFERENCES visitors(id),
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_pageviews_site_time
ON pageviews(site_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_pageviews_site_path_time
ON pageviews(site_id, page_path, occurred_at);

CREATE INDEX IF NOT EXISTS idx_pageviews_site_referrer_time
ON pageviews(site_id, referrer_domain, occurred_at);

CREATE INDEX IF NOT EXISTS idx_pageviews_visitor_time
ON pageviews(site_id, visitor_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_sessions_site_time
ON sessions(site_id, started_at);

CREATE INDEX IF NOT EXISTS idx_sessions_visitor
ON sessions(site_id, visitor_id);
"""


def _connect(path: str) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


@lru_cache
def get_db_path() -> str:
    return get_settings().analytics_db_path


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    init_schema()
    connection = _connect(get_db_path())
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@lru_cache
def init_schema() -> None:
    connection = _connect(get_db_path())
    try:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            """
            INSERT OR IGNORE INTO sites (id, name, allowed_origins)
            VALUES (?, ?, ?)
            """,
            ("junkdrawer", "Hank's Junk Drawer", json.dumps(["https://hmarquardt.github.io"])),
        )
        connection.commit()
    finally:
        connection.close()


def check_db() -> bool:
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


def clear_db_cache() -> None:
    init_schema.cache_clear()
    get_db_path.cache_clear()

