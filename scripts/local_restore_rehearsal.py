"""Rebuild the TraderDash schema on a local Postgres and check the relationships.

This is a rehearsal, not a restore of the production backup. It refuses any
Supabase host. It uses one synthetic identity and does not read production.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.errors import InsufficientPrivilege

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "supabase" / "migrations" / "20261030160000_accounts.sql",
    ROOT / "supabase" / "migrations" / "20261104110000_identity_catalog.sql",
    ROOT / "supabase" / "migrations" / "20261104140000_legacy_auth_links.sql",
)
AUTH_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ID = "22222222-2222-4222-8222-222222222222"

STUB = """
create schema if not exists auth;
create table if not exists auth.users (
    id uuid primary key,
    email text unique
);
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
    select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'anon') then
        create role anon nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'authenticated') then
        create role authenticated nologin;
    end if;
end $$;
grant authenticated to current_user;
"""

SYNTHETIC = f"""
insert into auth.users (id, email) values
    ('{AUTH_ID}', 'restore-drill@example.invalid'),
    ('{OTHER_ID}', 'restore-other@example.invalid');
insert into public.users (
    user_id, email, password_hash, plan, subscription_status, created_at, updated_at
) values (
    'legacy-drill',
    'restore-drill-legacy@example.invalid',
    'synthetic-not-a-password',
    'free',
    'free',
    '2026-11-09T00:00:00Z',
    '2026-11-09T00:00:00Z'
);
insert into public.legacy_auth_links (
    legacy_user_id, auth_user_id, migration_status, migration_reference
) values (
    'legacy-drill', '{AUTH_ID}', 'migrated', 'restore-drill'
);
insert into public.entitlements (user_id, product_id, plan_id, status, source)
select '{AUTH_ID}', products.id, plans.id, 'active', 'migration'
from public.products
join public.plans on plans.product_id = products.id
where products.code = 'traderdash' and plans.code = 'free';
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (
    version text primary key,
    name text not null
);
insert into supabase_migrations.schema_migrations (version, name) values
    ('20261030160000', 'accounts'),
    ('20261104110000', 'identity_catalog'),
    ('20261104140000', 'legacy_auth_links');
"""


def refuse_remote(host: str) -> None:
    lowered = host.lower()
    if lowered.endswith(".supabase.co") or "wxvobyifckbpnqfbnlxl" in lowered or "ajbsoudovxstlolojvte" in lowered:
        raise SystemExit("refusing to rehearse against a Supabase host")
    if lowered not in {"127.0.0.1", "localhost"}:
        raise SystemExit("rehearsal host must be local")


def connect(database: str) -> psycopg.Connection:
    host = os.environ.get("PGHOST", "127.0.0.1")
    refuse_remote(host)
    return psycopg.connect(
        host=host,
        port=int(os.environ.get("PGPORT", "55432")),
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        dbname=database,
        autocommit=True,
    )


def run_script(conn: psycopg.Connection, sql: str) -> None:
    path = None
    try:
        handle = tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8")
        path = handle.name
        handle.write(sql)
        handle.close()
        psql = os.environ["TRADERDASH_PSQL"]
        env = os.environ.copy()
        completed = __import__("subprocess").run(
            [psql, "-v", "ON_ERROR_STOP=1", "-f", path],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr)
            raise SystemExit(completed.returncode)
    finally:
        if path and os.path.exists(path):
            os.remove(path)


def expect_failure(conn: psycopg.Connection, sql: str) -> None:
    try:
        conn.execute(sql)
    except psycopg.Error:
        return
    raise SystemExit("expected a constraint failure")


def main() -> None:
    os.environ["PGDATABASE"] = "postgres"
    admin = connect("postgres")
    admin.execute("drop database if exists traderdash_restore")
    admin.execute("create database traderdash_restore")
    admin.close()

    os.environ["PGDATABASE"] = "traderdash_restore"
    conn = connect("traderdash_restore")
    try:
        run_script(conn, STUB)
        for migration in MIGRATIONS:
            run_script(conn, migration.read_text(encoding="utf-8"))
        run_script(conn, SYNTHETIC)
        check(conn)
    finally:
        conn.close()
        os.environ["PGDATABASE"] = "postgres"
        admin = connect("postgres")
        admin.execute("drop database if exists traderdash_restore")
        admin.close()
    print("LOCAL RESTORE REHEARSAL PASSED")


def check(conn: psycopg.Connection) -> None:

    profile_count = conn.execute("select count(*) from public.profiles").fetchone()[0]
    link = conn.execute(
        "select legacy_user_id, migration_reference from public.legacy_auth_links where auth_user_id = %s",
        (AUTH_ID,),
    ).fetchone()
    entitlement = conn.execute(
        """
        select entitlements.status, plans.code, products.code
        from public.entitlements
        join public.plans on plans.id = entitlements.plan_id
        join public.products on products.id = entitlements.product_id
        where entitlements.user_id = %s
        """,
        (AUTH_ID,),
    ).fetchone()
    flags = conn.execute(
        """
        select c.relname, c.relrowsecurity, c.relforcerowsecurity
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relname in ('products', 'plans', 'profiles', 'entitlements', 'legacy_auth_links')
        order by c.relname
        """
    ).fetchall()
    versions = conn.execute(
        "select version from supabase_migrations.schema_migrations order by version"
    ).fetchall()
    if profile_count != 2 or link != ("legacy-drill", "restore-drill") or entitlement != ("active", "free", "traderdash"):
        raise SystemExit("relationship check failed")
    if [tuple(row) for row in flags] != [
        ("entitlements", True, True),
        ("legacy_auth_links", True, True),
        ("plans", True, True),
        ("products", True, True),
        ("profiles", True, True),
    ]:
        raise SystemExit("row security check failed")
    if [row[0] for row in versions] != [
        "20261030160000",
        "20261104110000",
        "20261104140000",
    ]:
        raise SystemExit("migration record check failed")

    expect_failure(
        conn,
        f"""
        insert into public.entitlements (user_id, product_id, plan_id, status, source)
        select '{AUTH_ID}', products.id, plans.id, 'active', 'manual'
        from public.products
        join public.plans on plans.product_id = products.id
        where products.code = 'traderdash' and plans.code = 'nordic'
        """,
    )
    expect_failure(
        conn,
        f"""
        update public.legacy_auth_links
        set auth_user_id = '{OTHER_ID}'
        where auth_user_id = '{AUTH_ID}'
        """,
    )

    with conn.transaction():
        conn.execute("set local role authenticated")
        conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (AUTH_ID,))
        visible_profiles = conn.execute("select count(*) from public.profiles").fetchone()[0]
        visible_entitlements = conn.execute("select count(*) from public.entitlements").fetchone()[0]
        try:
            with conn.transaction():
                conn.execute("select count(*) from public.legacy_auth_links")
        except InsufficientPrivilege:
            links_closed = True
        else:
            links_closed = False
    if (visible_profiles, visible_entitlements, links_closed) != (1, 1, True):
        raise SystemExit("rls visibility check failed")

if __name__ == "__main__":
    main()
