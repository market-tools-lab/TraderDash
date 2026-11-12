"""Exercise TraderDash Free provisioning on a local database.

The script refuses every Supabase host. It uses synthetic users and drops
the database before it exits. It does not read or write production.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_restore_rehearsal import MIGRATIONS, STUB, connect, run_script

PROVISION = MIGRATIONS[0].parents[0] / "20261109110000_provision_traderdash_free.sql"
EXISTING = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
FRESH = "ffffffff-ffff-4fff-8fff-ffffffffffff"
PAID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

def main() -> None:
    os.environ["PGDATABASE"] = "postgres"
    admin = connect("postgres")
    admin.execute("drop database if exists traderdash_provision")
    admin.execute("create database traderdash_provision")
    admin.close()
    os.environ["PGDATABASE"] = "traderdash_provision"
    conn = connect("traderdash_provision")
    try:
        run_script(conn, STUB)
        for migration in MIGRATIONS:
            run_script(conn, migration.read_text(encoding="utf-8"))
        run_script(conn, PROVISION.read_text(encoding="utf-8"))
        conn.execute(
            "insert into auth.users (id, email) values (%s, %s), (%s, %s), (%s, %s)",
            (EXISTING, "existing@example.invalid", FRESH, "fresh@example.invalid", PAID, "paid@example.invalid"),
        )
        conn.execute(
            """
            insert into public.entitlements (user_id, product_id, plan_id, status, source)
            select %s, products.id, plans.id, 'active', 'migration'
            from public.products
            join public.plans on plans.product_id = products.id
            where products.code = 'traderdash' and plans.code = 'free'
            """,
            (EXISTING,),
        )
        conn.execute("select public.provision_traderdash_free(%s)", (EXISTING,))
        conn.execute("select public.provision_traderdash_free(%s)", (EXISTING,))
        existing = conn.execute(
            """
            select count(*), min(entitlements.source)
            from public.entitlements
            join public.plans on plans.id = entitlements.plan_id
            where user_id = %s and plans.code = 'free' and status = 'active'
            """,
            (EXISTING,),
        ).fetchone()
        if tuple(existing) != (1, "migration"):
            raise SystemExit("existing free entitlement changed")
        conn.execute("select public.provision_traderdash_free(%s)", (FRESH,))
        conn.execute("select public.provision_traderdash_free(%s)", (FRESH,))
        fresh = conn.execute(
            """
            select count(profiles.id), count(entitlements.id), min(plans.code), min(entitlements.source)
            from public.profiles
            join public.entitlements on entitlements.user_id = profiles.id
            join public.plans on plans.id = entitlements.plan_id
            where profiles.id = %s and entitlements.status = 'active'
            """,
            (FRESH,),
        ).fetchone()
        if tuple(fresh) != (1, 1, "free", "signup"):
            raise SystemExit("fresh provisioning was not exactly one free entitlement")
        conn.execute(
            """
            insert into public.entitlements (user_id, product_id, plan_id, status, source)
            select %s, products.id, plans.id, 'active', 'subscription'
            from public.products
            join public.plans on plans.product_id = products.id
            where products.code = 'traderdash' and plans.code = 'nordic'
            """,
            (PAID,),
        )
        try:
            conn.execute("select public.provision_traderdash_free(%s)", (PAID,))
        except psycopg.Error:
            pass
        else:
            raise SystemExit("paid account was provisioned")
        paid_free = conn.execute(
            """
            select count(*) from public.entitlements
            join public.plans on plans.id = entitlements.plan_id
            where user_id = %s and plans.code = 'free'
            """,
            (PAID,),
        ).fetchone()[0]
        if paid_free != 0:
            raise SystemExit("paid account received free")
        try:
            conn.execute("set role authenticated")
            conn.execute("select public.provision_traderdash_free(%s)", (FRESH,))
        except psycopg.Error:
            conn.execute("reset role")
        else:
            conn.execute("reset role")
            raise SystemExit("authenticated could execute provisioning")
    finally:
        conn.close()
        os.environ["PGDATABASE"] = "postgres"
        admin = connect("postgres")
        admin.execute("drop database if exists traderdash_provision")
        admin.close()
    print("LOCAL PROVISION REHEARSAL PASSED")


if __name__ == "__main__":
    main()
