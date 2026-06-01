from __future__ import annotations

from datetime import UTC, date, datetime, time

from app.analytics.db import get_connection


def parse_date_range(from_date: date, to_date: date) -> tuple[str, str]:
    start = datetime.combine(from_date, time.min, tzinfo=UTC)
    end = datetime.combine(to_date, time.max, tzinfo=UTC)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def summary(site_id: str, from_date: date, to_date: date) -> dict:
    start, end = parse_date_range(from_date, to_date)
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
              COUNT(*) AS pageviews,
              COUNT(DISTINCT visitor_id) AS visitors,
              COUNT(DISTINCT session_id) AS sessions
            FROM pageviews
            WHERE site_id = ? AND occurred_at BETWEEN ? AND ? AND is_bot = 0
            """,
            (site_id, start, end),
        ).fetchone()
        bounce_row = connection.execute(
            """
            SELECT AVG(CASE WHEN pageview_count <= 1 THEN 1.0 ELSE 0.0 END) AS bounce_rate
            FROM sessions
            WHERE site_id = ? AND started_at BETWEEN ? AND ?
            """,
            (site_id, start, end),
        ).fetchone()
    pageviews = int(row["pageviews"] or 0)
    sessions = int(row["sessions"] or 0)
    return {
        "site_id": site_id,
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "pageviews": pageviews,
        "visitors": int(row["visitors"] or 0),
        "sessions": sessions,
        "avg_pageviews_per_session": round(pageviews / sessions, 2) if sessions else 0,
        "bounce_rate": round(float(bounce_row["bounce_rate"] or 0), 2),
    }


def timeseries(site_id: str, from_date: date, to_date: date, bucket: str) -> dict:
    start, end = parse_date_range(from_date, to_date)
    expression = "strftime('%Y-%m-%dT%H:00:00Z', occurred_at)" if bucket == "hour" else "date(occurred_at)"
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT {expression} AS bucket_date,
              COUNT(*) AS pageviews,
              COUNT(DISTINCT visitor_id) AS visitors,
              COUNT(DISTINCT session_id) AS sessions
            FROM pageviews
            WHERE site_id = ? AND occurred_at BETWEEN ? AND ? AND is_bot = 0
            GROUP BY bucket_date
            ORDER BY bucket_date
            """,
            (site_id, start, end),
        ).fetchall()
    return {
        "bucket": bucket,
        "points": [
            {
                "date": row["bucket_date"],
                "pageviews": row["pageviews"],
                "visitors": row["visitors"],
                "sessions": row["sessions"],
            }
            for row in rows
        ],
    }


def pages(site_id: str, from_date: date, to_date: date, limit: int) -> dict:
    start, end = parse_date_range(from_date, to_date)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
              pv.page_path,
              MAX(pv.page_title) AS page_title,
              COUNT(*) AS pageviews,
              COUNT(DISTINCT pv.visitor_id) AS visitors,
              COUNT(DISTINCT pv.session_id) AS sessions,
              AVG(CASE WHEN s.pageview_count <= 1 THEN 1.0 ELSE 0.0 END) AS bounce_rate
            FROM pageviews pv
            LEFT JOIN sessions s ON s.id = pv.session_id
            WHERE pv.site_id = ? AND pv.occurred_at BETWEEN ? AND ? AND pv.is_bot = 0
            GROUP BY pv.page_path
            ORDER BY pageviews DESC, pv.page_path
            LIMIT ?
            """,
            (site_id, start, end, limit),
        ).fetchall()
    return {
        "pages": [
            {
                "path": row["page_path"],
                "title": row["page_title"],
                "pageviews": row["pageviews"],
                "visitors": row["visitors"],
                "sessions": row["sessions"],
                "bounce_rate": round(float(row["bounce_rate"] or 0), 2),
            }
            for row in rows
        ]
    }


def referrers(site_id: str, from_date: date, to_date: date, limit: int) -> dict:
    start, end = parse_date_range(from_date, to_date)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
              COALESCE(NULLIF(referrer_domain, ''), 'direct') AS domain,
              COUNT(*) AS pageviews,
              COUNT(DISTINCT visitor_id) AS visitors
            FROM pageviews
            WHERE site_id = ? AND occurred_at BETWEEN ? AND ? AND is_bot = 0
            GROUP BY domain
            ORDER BY pageviews DESC, domain
            LIMIT ?
            """,
            (site_id, start, end, limit),
        ).fetchall()
    return {
        "referrers": [
            {"domain": row["domain"], "pageviews": row["pageviews"], "visitors": row["visitors"]}
            for row in rows
        ]
    }


def recent(site_id: str, limit: int) -> dict:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT occurred_at, page_path, page_title, referrer_domain,
              browser_name, os_name, device_type, is_bot
            FROM pageviews
            WHERE site_id = ?
            ORDER BY occurred_at DESC, received_at DESC
            LIMIT ?
            """,
            (site_id, limit),
        ).fetchall()
    return {
        "visits": [
            {
                "occurred_at": row["occurred_at"],
                "page_path": row["page_path"],
                "page_title": row["page_title"],
                "referrer_domain": row["referrer_domain"],
                "browser_name": row["browser_name"],
                "os_name": row["os_name"],
                "device_type": row["device_type"],
                "is_bot": bool(row["is_bot"]),
            }
            for row in rows
        ]
    }

