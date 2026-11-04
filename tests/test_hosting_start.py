"""Production start must not create SQLite, and the image stays portable."""

from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import supabase_auth
from account_store import SAFE_DB_MESSAGE, AccountConfigError, storage_backend

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def scoped_env(**values):
    previous = {key: os.environ.get(key) for key in values}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class HostingStartTests(unittest.TestCase):
    def test_legacy_production_without_database_url_does_not_create_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / "local.db"
            with scoped_env(
                TRADERDASH_ENV="production",
                TRADERDASH_AUTH_MODE=None,
                DATABASE_URL=None,
                TRADERDASH_DATABASE=str(sentinel),
            ):
                self.assertEqual(supabase_auth.auth_mode(), "legacy")
                with self.assertRaises(AccountConfigError) as caught:
                    storage_backend()
            self.assertEqual(str(caught.exception), SAFE_DB_MESSAGE)
            self.assertFalse(sentinel.exists())

    def test_supabase_production_without_database_url_does_not_create_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / "local.db"
            with scoped_env(
                TRADERDASH_ENV="production",
                TRADERDASH_AUTH_MODE="supabase_auth",
                TRADERDASH_SUPABASE_URL=None,
                TRADERDASH_SUPABASE_ANON_KEY=None,
                DATABASE_URL=None,
                TRADERDASH_DATABASE=str(sentinel),
            ):
                self.assertEqual(supabase_auth.auth_mode(), "supabase_auth")
                with self.assertRaises(supabase_auth.AuthError) as caught:
                    supabase_auth.sign_in("person@example.invalid", "not-used")
            self.assertEqual(str(caught.exception), "Supabase Auth er ikke konfigureret.")
            self.assertFalse(sentinel.exists())

    def test_image_listens_on_the_platform_port_without_a_secret(self):
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("python:3.12-slim", docker)
        self.assertIn("0.0.0.0", docker)
        self.assertIn("${PORT:-8501}", docker)
        self.assertNotIn("wxvobyifckbpnqfbnlxl", docker)
        self.assertNotIn("service_role", docker)
        self.assertIn(".env", ignored)
