# Iteration 0

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Schemaet er **PREPARED, NOT APPLIED**. Ingen SQL er kørt.

## Baseline

Kørt lokalt før de nye filer, på `master` og igen efter branch-skiftet, før migrationen blev skrevet.

| | |
| --- | --- |
| Python | 3.12.10 |
| Kommando | `python -m unittest tests.test_account_store` |
| Antal | 18 |
| Bestået | 18 |
| Fejlet | 0 |
| Sprunget over | 0 |
| Warnings | Ingen i output |
| Tid | 10,821 s ved gentagelsen |
| Exit | 0 |
| Branch før skift | `master` |
| Commit | `4d292dae4a43c114df8818d4d7991d9b37149736` |

Sporbar working tree var ren. Mappen `docs/` fra den tidligere audit var untracked og er ikke staged. Den er ikke en del af denne iteration.

## Branch

`feature/supabase-auth` er oprettet fra `4d292da`. `master` peger stadig på samme commit. Cloud-appen kører videre fra `master`.

## Nye filer

- `supabase/migrations/20261104110000_identity_catalog.sql`
- `tests/test_identity_schema.py`
- `docs/iterations/ITERATION_0.md`

Den eksisterende `supabase/migrations/20261030160000_accounts.sql` er ikke ændret. `public.users` er ikke ændret. Login er ikke ændret.

## Migration

Filen opretter kun `products`, `plans`, `profiles` og `entitlements`.

`profiles.id` og `entitlements.user_id` peger på `auth.users.id`. Der er ingen credential-kolonne og ingen kopi af Auth-felter ud over bruger-id.

Seed er produktet `traderdash` og planerne `free`, `nordic` og `international`. Papirtallene 30, 79 og 159 bliver i `universes.py`. De er ikke kolonner.

En trigger på `auth.users` opretter kun en profil. Den tildeler ikke en entitlement. En anden trigger afviser en entitlement, hvis planen ikke hører til produktet.

## RLS

RLS og FORCE ROW LEVEL SECURITY er slået til på alle fire tabeller.

`authenticated` må læse egen profil og opdatere kun `display_name`. `id` og `created_at` afvises af triggeren. `authenticated` må læse egne entitlements og må ikke indsætte, opdatere eller slette dem. `authenticated` må læse aktive produkter og planer og må ikke ændre kataloget. `anon` har ingen grants.

Service role og webhook er ikke implementeret. `postgres`-rollen er ikke ændret. Den omgår RLS, så den nuværende database-URI er ikke adgangsvejen til de nye tabeller.

## Tests

`tests/test_identity_schema.py` læser migrationsfilen. Den åbner ikke en database.

Syv integrationstest er sprunget over. De kræver en database, der ikke er Production, med `auth.users`. De er ikke kørt.

## Ikke kørt

- Ingen SQL mod Supabase eller Production.
- Ingen ændring af `database_url`, `postgres`-rollen, Streamlit Secrets eller Supabase Auth.
- Ingen brugere oprettet.
- Ingen ændring af login, `public.users` eller Cloud-appen.
- Ingen Stripe-implementering.
- Intet push. Ingen merge.

B11 er stadig ubesvaret. Derfor er filen ikke anvendt.

## Rollback

Slet branchen `feature/supabase-auth`. `master` er urørt. Der er ingen databaseændring at rulle tilbage.
