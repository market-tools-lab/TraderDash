# Iteration 8

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE som readiness-gate. NO-GO for at udføre Production-piloten.**

Production er ikke læst og ikke skrevet. Ingen migration er kørt der. Ingen Auth-bruger er oprettet der. Streamlit Secrets, Cloud-flaget, `master` og Stripe er urørt. Iteration 9 er ikke startet.

## Target

| Kontrol | Resultat |
| --- | --- |
| Preview-ref | `ajbsoudovxstlolojvte` |
| Preview-URL | `https://ajbsoudovxstlolojvte.supabase.co` |
| Preview-branch | `supabase-auth-test` |
| Production | Ikke kontaktet |
| Rigtige rækker i preview | Ingen. Én stående syntetisk Auth-bruger, ingen legacy-rækker |

Preview før og efter arbejdet: 1 Auth-bruger `63ffe985-0e7e-48bd-b41b-d1741330257a`, 1 profil, 0 entitlements, 0 links, 0 `public.users`, 0 adresser uden for `example.invalid`. Planerne er `free:0`, `nordic:1`, `international:2`. Entitlements har RLS og FORCE RLS og 0 skrive-policies.

## Code review

Gennemgangen dækkede diffen siden `master` `4d292dae4a43c114df8818d4d7991d9b37149736`.

| Kontrol | Resultat |
| --- | --- |
| Credentials i koden | Ingen service role, ingen URI og ingen token |
| Production som default | Auth, reset og migration nægter enhver anden URL end preview |
| Hardcodede testbrugere | Reserverede `example.invalid`-adresser og et sletteværn for den stående preview-bruger |
| Password i sessionen | Auth-mode fjerner password-nøglerne. Legacy-formularen er ikke omlagt |
| Bred `except` | Viser den faste danske tekst og skifter ikke til legacy |
| Ukendt auth-mode | Bliver `legacy`. Det er rollback, ikke et fald tilbage midt i en Auth-session |
| Self-upgrade | Authenticated kan læse egen entitlement og kan ikke skrive den |
| Fail-open plan | `accounts.resolve_plan` bruges ikke i Auth-mode |
| Cache | Nøglen er ticker og periode, ikke bruger eller token |
| Per-user cutover | Findes ikke. Flaget er globalt |
| Idempotens | Et ens andet kald skriver intet. En anden entitlement afvises og skriver intet |

Den ene rettelse er i `pilot_migration.py`. Et link uden entitlement skriver kun linket. En entitlement med en anden plan eller status afvises som `entitlement_drift`.

## Migrationspakke

`docs/production/MIGRATION_MANIFEST.md` har rækkefølge, SHA-256, afhængigheder, objekter, verifikationsquery og preview-status.

`20261030160000_accounts.sql` må ikke køres igen. De to nye filer er kørt på preview og ikke på Production. Iteration 7 har ingen migrationsfil.

`docs/production/ROLLBACK.sql` er ikke kørt. Den sletter ikke `public.users` eller `auth.users`.

## Backup-gate

Verificeret 2026-11-03: Free Plan havde ingen project backups. Theis oplyser, at Pro er aktiveret, og at dashboardet viser daily backups i 7 dage som planfeature. Supabase-dokumentationen siger det samme for Pro: Database → Backups, seneste 7 dages daglige backups. [Database Backups](https://supabase.com/docs/guides/platform/backups).

Denne session kan ikke bekræfte Production-backuppen. Forbindelsen her er preview-projektet, og en management-token er en ny secret. Ingen restore er udført.

Manuel kontrol, før nogen senere migration:

1. Åbn Production-projektet. Ref skal være en anden end `ajbsoudovxstlolojvte`. Er den den samme, stop.
2. Gå til Database → Backups → Scheduled. Stien er `https://supabase.com/dashboard/project/<PRODUCTION_REF>/database/backups/scheduled`.
3. Seneste backup skal være completed, og tidspunktet skal skrives ned. Det skal være nyere end sidste ændring af testkontoen, eller alderen skal accepteres skriftligt.
4. Tryk ikke på restore. Restore gør projektet utilgængeligt, og preview-branchen er ikke restore-målet.
5. Preview `supabase-auth-test` bruges ikke som backupkilde.

## Pilotbruger

Kontoen `traderdashtesttest@example.dk` er ikke migreret. `pilot_readiness.py` kan senere lave et redacted dry-run for præcis én række: legacy-id, plan, status, den entitlement der ville blive oprettet, om Auth-identiteten findes, og om linket findes. Den kræver frasen `CONFIRM-PRODUCTION-PILOT`, kalder ikke queries uden den, og åbner ikke en database. Kommandoen svarer altid med afvisning. Password og hash kan ikke komme med i rapporten. Gentagne kald skriver intet.

Kendte funktionskrav, ikke læst fra Production: plan `free`, 30 papirer. Det giver en aktiv Free-entitlement, hvis status også er `free`.

## Andre manuelle punkter

| Punkt | Resultat |
| --- | --- |
| Cloud `TRADERDASH_AUTH_MODE` | Skal blive væk eller `legacy`. Et skift rammer alle brugere |
| Streamlit Secrets | Ikke ændret. Service role må ikke lægges der |
| Mailleverandør | Ikke valgt. E-mail-reset er ikke klar |
| Lækket-password-beskyttelse | Slået fra på preview. På Pro slås den til under Authentication → Providers → Email, og kun på Production efter ref-kontrollen. [Password security](https://supabase.com/docs/guides/auth/password-security) |
| Stripe | Ikke aktiveret |
| `postgres` | Ikke ændret. Rollen har stadig bypass af RLS for den gamle URI |

## Tests

`python -m unittest discover -s tests`

98 tests. 89 bestod, 0 fejlede, 9 sprunget over. Varighed 16,6 sekunder. De ni overspringelser er de eksisterende placeholders og preview-tests uden miljø.

Streamlit skrev `missing ScriptRunContext` under AppTest. Biblioteket siger, at advarslen kan ignoreres i bare mode.

## Go/no-go

| Gate | Afgørelse |
| --- | --- |
| Pakken er klar og hashet | GO |
| Preview matcher kataloget og har ingen rigtige brugere | GO |
| Rollback er skrevet og ikke kørt | GO |
| Production-backup er set i denne session | NO-GO |
| Production-migration | NO-GO |
| Første rigtige pilot | NO-GO |
| Cloud-flag | NO-GO |
| Samlet | NO-GO for at udføre piloten. GO for at lade pakken ligge, indtil backup-gaten er krydset af |
