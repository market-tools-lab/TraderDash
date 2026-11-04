# Repository-inventar

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Repositoriet er den versionerede tekniske dokumentation. Hemmelige værdier ligger ikke her. `.streamlit/secrets.toml`, `.env` og `data/` er ignoreret.

## Kørsel

| Fil | Rolle |
| --- | --- |
| `app.py` | Entrypoint. Legacy er default. Auth kun ved `supabase_auth` |
| `supabase_auth.py` | Login, profil og entitlement-læsning |
| `accounts.py`, `account_store.py` | Legacy-konti. Production uden URL opretter ikke SQLite |
| `access.py`, `universes.py`, `plans.py` | 30, 79 og 159 papirer. Checkout er en tekst |
| `account_privacy.py` | Lokal eksport og sletning. Production og preview afvises |
| `stripe_test.py` | Lokal Stripe-test. Flaget er false |
| `Dockerfile` | Python 3.12, `0.0.0.0`, `PORT`. Ikke deployet |

## Data og drift

| Fil | Rolle |
| --- | --- |
| `supabase/migrations/20261030160000_accounts.sql` | Legacy-konti. Ikke kørt igen |
| `supabase/migrations/20261104110000_identity_catalog.sql` | Katalog. Kørt på preview og Production |
| `supabase/migrations/20261104140000_legacy_auth_links.sql` | Link. Kørt på preview og Production |
| `supabase/functions/stripe-webhook/index.ts` | Flag false |
| `docs/production/AUTH_PRODUCTION_GATE.md` | Ikke-hemmelige id'er og gaten |
| `docs/production/STAGING.md` | Miljøer |
| `docs/production/HOSTING.md` | Senere vært, uden DNS-skift |
| `docs/production/ROLLBACK.sql` | Ikke til kørsel |

## Uden for mergen

Syv filer under `docs/TRADERDASH_*` er en audit fra 2. november 2026 mod en ældre `master`. De står i `.gitignore`. De er ikke den nuværende kilde.
