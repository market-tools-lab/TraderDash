# Iteration 1

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**.

Schemaet er anvendt på preview-branchen `supabase-auth-test`, project ref `ajbsoudovxstlolojvte`. Production er ikke kontaktet. Login og `public.users` er ikke ændret.

To tidligere forsøg samme dag var blokeret: først manglede en lokal container-runtime, derefter afviste MCP-forbindelsen DDL som read-only. Tredje forsøg brugte `apply_migration` mod det verificerede preview-ref.

## Target

| Kontrol | Resultat |
| --- | --- |
| Project ref | `ajbsoudovxstlolojvte` |
| Branch | `supabase-auth-test`, manuelt verificeret som preview |
| URL før skrivning | `https://ajbsoudovxstlolojvte.supabase.co` |
| `supabase link` | Ikke kørt |
| `supabase db push` | Ikke kørt |
| Production | Ikke kontaktet |

## Migration

`apply_migration` anvendte indholdet af `supabase/migrations/20261104110000_identity_catalog.sql`.

Preview-historikken har version `20261104112720` og navnet `identity_catalog`. Filnavnets tidsstempel er uændret. `apply_migration` sætter sit eget versionstidsstempel.

Den eksisterende migration `20261030160000` `accounts` lå der i forvejen og blev ikke ændret. Migrationsfilen i repoet er ikke rettet. Der var ingen schemafejl.

## Preview-tests

Alle punkter bestod. Testdata blev oprettet i en transaktion og rullet tilbage.

| Kontrol | Resultat |
| --- | --- |
| `products`, `plans`, `profiles`, `entitlements` | Findes |
| Produkt `traderdash` | Findes |
| Planer `free`, `nordic`, `international` | Findes |
| RLS og FORCE ROW LEVEL SECURITY | Aktive på alle fire tabeller |
| `anon` læser profiler eller entitlements | Afvist |
| `authenticated` læser profiler | Kun egen række |
| `authenticated` ændrer `display_name` | Tilladt |
| `authenticated` ændrer profil-id | Afvist |
| `authenticated` læser entitlements | Kun egne |
| `authenticated` opretter, ændrer eller sletter entitlements | Afvist |
| `authenticated` ændrer `products` eller `plans` | Afvist |
| Plan fra et andet produkt | Afvist |
| Anden aktiv entitlement for samme bruger og produkt | Afvist |
| Syntetisk Auth-bruger | Profil oprettet af triggeren |
| Automatisk entitlement | Ingen |

Efter rollback: 0 profiler, 0 entitlements, 0 syntetiske Auth-brugere. Kataloget er stadig `traderdash` med `free`, `nordic` og `international`.

Der blev brugt reserverede testadresser på `.invalid`. Ingen rigtige adresser.

## Lokale tests

Python 3.12.10.

`python -m unittest tests.test_account_store tests.test_identity_schema`

| | |
| --- | --- |
| Antal | 37 |
| Bestået | 30 |
| Fejlet | 0 |
| Sprunget over | 7 |
| Warnings | Ingen |
| Tid | 11,756 s |

De 18 kontotests bestod. De 12 statiske schemafiler bestod. De 7 sprunget over er de gamle pladsholdere, som ikke må åbne en database. De samme tilfælde blev kørt direkte på preview-branchen og bestod dér.

## Ikke ændret

- Production-databasen og Production Auth
- `postgres`-rollen
- Streamlit og Streamlit Secrets
- GitHub
- `app.py` og den eksisterende login
- `public.users`

## Rollback

Slet branchen `feature/supabase-auth`, hvis repo-ændringen skal væk. `master` er urørt.

Preview-schemaet bliver liggende. Syntetiske brugere og testdata er allerede fjernet. Et senere rollback af schemaet skal kun droppe de nye objekter og må ikke droppe `public.users`.
