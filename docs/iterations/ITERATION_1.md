# Iteration 1

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **BLOCKED**.

Årsag: der findes ingen lokal container-runtime. Docker blev ikke installeret. Ingen lokal Supabase-stack blev startet, og migrationen blev ikke anvendt. Production blev ikke kontaktet.

## Prerequisites

| Kontrol | Resultat |
| --- | --- |
| Aktiv branch | `feature/supabase-auth` |
| `master` | `4d292dae4a43c114df8818d4d7991d9b37149736`, uændret |
| Iteration 0-commits | `140d7fd`, `e31b856`, `09d8796` |
| Sporbar working tree | Ren. De syv untracked auditfiler under `docs/` blev ikke staged |
| Docker | `docker` findes ikke på PATH og ikke under `C:\Program Files\Docker`. Winget har ingen installeret Docker-pakke |
| Docker-daemon | Ikke tilgængelig |
| WSL | Ikke installeret |
| Node.js | Findes ikke på PATH og ikke under `C:\Program Files\nodejs` |
| npm | Findes ikke |
| Supabase CLI | Findes ikke på PATH. Ingen `package.json`, så der er ingen lokal dev dependency |
| `supabase/config.toml` | Findes allerede med `project_id = "traderdash"`. Der blev ikke kørt `supabase init` |
| `supabase link` | Ikke kørt |
| `supabase start` | Ikke kørt |
| `supabase db reset` | Ikke kørt |
| `supabase db push` | Ikke kørt |

## Lokal stack

Ingen. Der er ingen service-URL'er.

Stacken stoppes ikke, fordi den aldrig blev startet.

## Migration

`supabase/migrations/20261104110000_identity_catalog.sql` er uændret og stadig **PREPARED, NOT APPLIED**.

Den eksisterende `supabase/migrations/20261030160000_accounts.sql` er uændret.

## Tests

Integrationstestene blev ikke kørt, fordi de kræver den lokale stack.

`python -m unittest tests.test_account_store` blev ikke kørt igen i denne iteration. Seneste kendte resultat er fra Iteration 0: 18 bestået, 0 fejlet, 0 sprunget over.

## Rettelser

Ingen. Migrationsfilen er ikke ændret.

## Ikke kontaktet

- Supabase Cloud
- Production-databasen
- Production Auth
- Streamlit og Streamlit Secrets
- GitHub
- Proton Pass

`postgres`-rollen er ikke ændret. Der er ikke oprettet brugere. Der er ikke læst secret-værdier.

## Rollback

Slet branchen `feature/supabase-auth`. `master` er urørt. Der er ingen lokal database at rydde op.

Næste forsøg på Iteration 1 kan starte, når Docker Desktop eller en kompatibel container-runtime er installeret og kører, og når Node.js og npm findes, så Supabase CLI kan installeres som lokal dev dependency. Docker må ikke installeres som en del af dette forsøg.
