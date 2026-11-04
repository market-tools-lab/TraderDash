# Iteration 9

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**. Den ene Production-pilot er migreret. Cloud er stadig `legacy`.

## Target

| Kontrol | Resultat |
| --- | --- |
| Projekt | Traderdash |
| Branch | `main`, default, PRODUCTION |
| Project ref | `wxvobyifckbpnqfbnlxl` |
| URL | `https://wxvobyifckbpnqfbnlxl.supabase.co` |
| Preview | `ajbsoudovxstlolojvte` blev ikke skrevet til |
| Backup | Verified 2026-11-04. Seneste restore-punkt 2026-11-04 02:58:26 UTC, PHYSICAL. Restore tested = NO. Restore executed = NO |
| Checksums | De tre manifest-filer matchede før skrivning |
| Working tree | Sporede filer var rene. De syv auditfiler er stadig u sporede |

`20261030160000_accounts.sql` blev ikke kørt igen.

## Schema

| Rækkefølge | Fil | Production-historik |
| --- | --- | --- |
| 1 | `20261104110000_identity_catalog.sql` | `20261104143544` `identity_catalog` |
| 2 | `20261104140000_legacy_auth_links.sql` | `20261104143902` `legacy_auth_links` |

Efter begge: produkt `traderdash`, planer `free` 0, `nordic` 1 og `international` 2. RLS og FORCE RLS er slået til. Authenticated kan ikke indsætte entitlements og kan ikke opdatere products eller plans. Anon kan ikke læse links. `public.users` var 1 før og 1 efter. `auth.users` var 0, indtil piloten blev oprettet. Ingen entitlement blev oprettet af migrationerne selv. Legacy-hashen var uændret efter begge migrationer.

## Redacted dry-run

| Felt | Værdi |
| --- | --- |
| Legacy user id | `7a65eb8c-2776-4447-b45c-f5dc542a5abb` |
| Plan | `free` |
| `subscription_status` | `free` |
| Forventet entitlement | `traderdash` / `free` / `active` |
| Papirer | 30 |
| Auth-identitet | fandtes ikke |
| Profile | fandtes ikke |
| Link | fandtes ikke |
| Entitlement | fandtes ikke |
| Status | `missing_auth` |
| Skriver | nej |

Præcis én legacy-række matchede. Der var ingen anden Auth-identitet og ingen link-konflikt.

## Pilot

Auth-id: `e8469788-5089-45f4-8a77-60440aa56fc7`.

Profilen kom fra triggeren. Linket er `migrated` med reference `pilot-i9`. Entitlement er `active`, plan `free`, kilde `migration`. Der er én aktiv entitlement.

Legacy-rækken findes stadig. Plan og status er stadig `free`. Hashen er uændret og er ikke den samme som Auth-hashen. Hashen er ikke kopieret og ikke vist. Password er ikke gemt i Git, dokumentation eller en midlertidig fil.

Mailleverandør er ikke valgt. Testpasswordet blev ikke beholdt. Et senere password skal sættes ad en admin-vej, når den findes. Recover blev ikke kaldt.

## Isoleret Auth-test

Lokal AppTest mod Production. Cloud og Streamlit Secrets er ikke ændret.

| Kontrol | Resultat |
| --- | --- |
| Login | ja |
| User id | Auth-id'et ovenfor |
| Profile | egen |
| Plan | `free` |
| Papirer | 30 |
| Ændre entitlement | HTTP 403 |
| Password i sessionen | nej |
| Logout | token og user id væk |

Verifikationen bestod, så piloten blev ikke rullet tilbage.

## Tests

`python -m unittest discover -s tests`

98 tests. 89 bestod, 0 fejlede, 9 sprunget over. Varighed 19,5 sekunder. Den isolerede Production-login indgår ikke i de 98, fordi den ikke bruger en gemt fixture.

Streamlit skrev `missing ScriptRunContext` under AppTest. Biblioteket siger, at advarslen kan ignoreres i bare mode.

## Ikke gjort

- Cloud-flaget er ikke sat
- Secrets er ikke ændret
- Registrering er ikke åbnet
- Ingen andre brugere er migreret
- Stripe er ikke aktiveret
- Ingen restore
- Ingen merge og ingen push
- Sletning og eksport er ikke bygget
