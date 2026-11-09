"""Guards for the disaster-recovery note.

These checks read the repository. They do not open a database and they do
not contact Supabase.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "docs" / "production" / "DISASTER_RECOVERY.md"
STEPS = (
    "1. Stop og klassificer hændelsen",
    "2. Bevar spor",
    "3. Stop skrivninger hvis det er nødvendigt",
    "4. Find sidste kendte gode tilstand",
    "5. Skeln kode, database og konfiguration",
    "6. Vælg gendannelseskilde",
    "7. Gendan først til et isoleret mål",
    "8. Validér",
    "9. Skift først over hvis det er nødvendigt",
    "10. Validér efter gendannelse",
    "11. Skriv hændelsen ned",
    "12. Fjern midlertidige ressourcer",
)
MIGRATIONS = (
    "supabase/migrations/20261030160000_accounts.sql",
    "supabase/migrations/20261104110000_identity_catalog.sql",
    "supabase/migrations/20261104140000_legacy_auth_links.sql",
)


class DisasterRecoveryNoteTests(unittest.TestCase):
    def test_runbook_has_the_incident_steps_and_no_secrets(self):
        text = NOTE.read_text(encoding="utf-8")
        for step in STEPS:
            self.assertIn(step, text)
        self.assertNotIn("eyJ", text)
        self.assertNotIn("service_role", text)
        self.assertNotIn("postgresql://", text)
        self.assertNotIn("https://ajbsoudovxstlolojvte.supabase.co", text)
        self.assertIn("må ikke oprettes igen", text)
        for relative in MIGRATIONS:
            self.assertIn(Path(relative).name, text)
            self.assertTrue((ROOT / relative).is_file())

    def test_rehearsal_refuses_a_supabase_host(self):
        source = (ROOT / "scripts" / "local_restore_rehearsal.py").read_text(encoding="utf-8")
        self.assertIn("refusing to rehearse against a Supabase host", source)
        self.assertIn("restore-drill@example.invalid", source)
        self.assertNotIn("theisbjerken@", source)
        self.assertNotIn("wxvobyifckbpnqfbnlxl.supabase.co", source)
