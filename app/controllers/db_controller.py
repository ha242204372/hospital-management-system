"""Database Studio controller: table inspector, read-only SQL console, backup & reset."""
import os
from app.config import ApiError
import app.models.db as db_mod
from app.models.db import rows, scalar, audit, _exec, USE_POSTGRES
from app.models.seed import seed


def get_db_info(conn, user):
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can access Database Studio")
    tables = []
    if USE_POSTGRES:
        tbls = rows(conn, """SELECT table_name AS name FROM information_schema.tables
            WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name""")
        for t in tbls:
            name = t["name"]
            cnt = scalar(conn, f"SELECT COUNT(*) FROM {name}")
            cols = rows(conn, """SELECT column_name AS name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=? ORDER BY ordinal_position""", (name,))
            tables.append({"name": name, "rows": cnt, "columns": [c["name"] for c in cols], "sql": ""})
        version = scalar(conn, "SELECT version()") or "PostgreSQL"
        path = db_mod.DATABASE_URL.split("@")[-1] if getattr(db_mod, "DATABASE_URL", "") else "postgresql"
        size_bytes = 0
    else:
        for t in rows(conn, "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            cnt = scalar(conn, f"SELECT COUNT(*) FROM {t['name']}")
            cols = rows(conn, f"PRAGMA table_info({t['name']})")
            tables.append({"name": t["name"], "rows": cnt, "columns": [c["name"] for c in cols], "sql": t.get("sql") or ""})
        import sqlite3
        version = sqlite3.sqlite_version
        path = db_mod.ACTIVE_DB
        size_bytes = os.path.getsize(path) if os.path.exists(path) else 0
    return {
        "path": path,
        "size_bytes": size_bytes,
        "size_kb": round(size_bytes / 1024, 1),
        "sqlite_version": version,
        "engine": "PostgreSQL" if USE_POSTGRES else "SQLite",
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
        fetched = rows(conn, sql_q)
        cols = list(fetched[0].keys()) if fetched else []
        audit(conn, user, "sql_query", sql_q[:100])
        return {"columns": cols, "rows": fetched[:250], "count": len(fetched[:250])}
    except Exception as e:
        raise ApiError(400, f"SQL error: {e}")


def reset_demo_db(conn, user):
    if user["role"] != "Admin":
        raise ApiError(403, "Only Admin can reset demo data")
    if USE_POSTGRES:
        tbls = rows(conn, """SELECT table_name AS name FROM information_schema.tables
            WHERE table_schema='public' AND table_type='BASE TABLE'""")
        for t in tbls:
            _exec(conn, f"TRUNCATE TABLE {t['name']} RESTART IDENTITY CASCADE")
    else:
        for t in [r["name"] for r in rows(conn, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]:
            _exec(conn, f"DELETE FROM {t}")
    seed(conn)
    audit(conn, user, "db_reset", "Re-seeded demo database")
