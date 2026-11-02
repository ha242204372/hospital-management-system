"""Database Studio controller: SQLite table inspector, read-only SQL console, backup & reset."""
import os
import sqlite3
from app.config import ApiError
import app.models.db as db_mod
from app.models.db import rows, scalar, audit
from app.models.seed import seed


def get_db_info(conn, user):
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can access Database Studio")
    tables = []
    for t in rows(conn, "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        cnt = scalar(conn, f"SELECT COUNT(*) FROM {t['name']}")
        cols = rows(conn, f"PRAGMA table_info({t['name']})")
        tables.append({"name": t["name"], "rows": cnt, "columns": [c["name"] for c in cols], "sql": t["sql"]})
    active_path = db_mod.ACTIVE_DB
    size_bytes = os.path.getsize(active_path) if os.path.exists(active_path) else 0
    return {
        "path": active_path,
        "size_bytes": size_bytes,
        "size_kb": round(size_bytes / 1024, 1),
        "sqlite_version": sqlite3.sqlite_version,
        "tables": tables,
        "total_rows": sum(t["rows"] for t in tables),
    }


def run_sql_query(conn, user, body):
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can run SQL queries")
    sql_q = (body.get("sql") or "").strip()
    if not sql_q:
        raise ApiError(400, "SQL query is required")
    first = sql_q.split()[0].upper()
    if first not in ("SELECT", "PRAGMA", "EXPLAIN", "WITH"):
        raise ApiError(400, "Only read-only SELECT / PRAGMA / WITH queries are permitted in the SQL console")
    try:
        cur = conn.execute(sql_q)
        cols = [d[0] for d in (cur.description or [])]
        fetched = [dict(r) for r in cur.fetchmany(250)]
        audit(conn, user, "sql_query", sql_q[:100])
        return {"columns": cols, "rows": fetched, "count": len(fetched)}
    except sqlite3.Error as e:
        raise ApiError(400, f"SQLite error: {e}")


def reset_demo_db(conn, user):
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can reset demo data")
    for t in [r["name"] for r in rows(conn, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]:
        conn.execute(f"DELETE FROM {t}")
    seed(conn)
    audit(conn, user, "db_reset", "Re-seeded demo database")
    return {"ok": True}
