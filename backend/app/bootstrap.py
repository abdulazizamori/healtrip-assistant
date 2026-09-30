"""First-boot database setup for single-service hosting (Render), where there is no init container.

Runs only when ADMIN_DATABASE_URL is set (docker compose initializes the DB itself and never sets it):
  1. empty database -> run db/01_schema.sql and db/02_seed.sql
  2. (re)create the SELECT-only role with a fresh random password on every boot — nothing to store or rotate
  3. return the read-only URL for the app; the admin URL is used for nothing else

If the hosted user may not create roles, the app falls back to the admin URL and logs it loudly:
the tools still only run fixed SELECT queries, but the least-privilege layer is missing.
"""

import logging
import secrets
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

log = logging.getLogger("healtrip.bootstrap")

RO_ROLE = "healtrip_agent_ro"
TABLES = ["cities", "specialties", "hospitals", "doctors", "languages", "doctor_languages", "availability_slots"]


def bootstrap(admin_url: str, sql_dir: str) -> str:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        if conn.execute("SELECT to_regclass('public.doctors')").fetchone()[0] is None:
            for name in ("01_schema.sql", "02_seed.sql"):
                conn.execute(Path(sql_dir, name).read_text(encoding="utf-8"))
            log.info("db_initialized")

        password = secrets.token_urlsafe(24)
        try:
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (RO_ROLE,)).fetchone()
            verb = sql.SQL("ALTER") if exists else sql.SQL("CREATE")
            conn.execute(sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(
                verb, sql.Identifier(RO_ROLE), sql.Literal(password)))
            db = conn.execute("SELECT current_database()").fetchone()[0]
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(db), sql.Identifier(RO_ROLE)))
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(RO_ROLE)))
            conn.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
                sql.SQL(", ").join(map(sql.Identifier, TABLES)), sql.Identifier(RO_ROLE)))
        except psycopg.Error as e:
            log.error("readonly_role_unavailable", extra={"error": type(e).__name__})
            return admin_url

    return _with_credentials(admin_url, RO_ROLE, password)


def _with_credentials(url: str, user: str, password: str) -> str:
    u = urlsplit(url)
    host = u.hostname or ""
    netloc = f"{user}:{password}@{host}" + (f":{u.port}" if u.port else "")
    return urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment))
