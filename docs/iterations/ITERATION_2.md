# Iteration 2

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**.

Auth-login er bevist på preview-branchen. `app.py` og det eksisterende login er ikke ændret.

## Target

| Kontrol | Resultat |
| --- | --- |
| Project ref | `ajbsoudovxstlolojvte` |
| Branch | `supabase-auth-test` |
| URL | `https://ajbsoudovxstlolojvte.supabase.co` |
| Production | Ikke kontaktet |

## Bruger og profil

Testbrugeren blev oprettet manuelt i Supabase-dashboardet. Passwordet er ikke skrevet i repoet og står ikke her.

| Kontrol | Resultat |
| --- | --- |
| E-mail | `markettools-auth-test@example.invalid` |
| Auth-id | `32772e00-62a3-4d85-8da6-eeb806cb56c5` |
| Profil | Præcis én. `profiles.id` er det samme UUID |
| Entitlement før tildeling | Ingen |
| `public.users` | 0 rækker, uændret |

Profiltriggeren virkede. Den tildelte ikke selv en entitlement.

## Auth-login

Login blev kørt lokalt mod preview Auth. Nøglen og passwordet lå kun i processens miljø og er slettet igen.

| Test | Resultat |
| --- | --- |
| Korrekt login | Session oprettet |
| Sessionens user.id | Matcher Auth-id |
| Forkert password | Afvist |
| Ukendt bruger | Afvist |
| Egen profil | Læst, og kun den række |
| Oprette entitlement | Afvist, HTTP 403 |
| Ændre entitlement | Afvist, HTTP 403 |
| Slette entitlement | Afvist, HTTP 403 |
| Aktive products og plans | Læst: `traderdash`, `free`, `nordic`, `international` |

## Free-entitlement

En privilegeret preview-operation indsatte én række: produkt `traderdash`, plan `free`, status `active`, kilde `manual`. Brugeren kunne ikke gøre det selv.

Brugerens egen session læste derefter rækken som `traderdash` / `free` / `active`.

`universes.stocks_for("free")` returnerer 30 papirer. `universes.py` er ikke ændret. TraderDash-UI bruger endnu ikke entitlements. Den læser stadig den gamle plan.

## Negative tests

Før tildelingen havde brugeren ingen entitlement. Det er lukket: 0 papirer.

Disse tilstande blev sat på preview-rækken og rullet tilbage:

| Tilstand | Database | Adgang |
| --- | --- | --- |
| Manglende række | 0 rækker | Lukket |
| `revoked` | Rækken kan sættes sådan | Lukket |
| `suspended` | Rækken kan sættes sådan | Lukket |
| `expired` | Rækken kan sættes sådan | Lukket |
| `active` med `ends_at` i fortiden | Vinduet kan ligge i fortiden, når det stadig er efter `starts_at` | Lukket |

Et forsøg på at sætte `ends_at` før `starts_at` blev afvist af `entitlements_window`. Efter rollback er rækken igen `active`, uden slutdato, plan `free`.

Reglen ligger i `tests/test_entitlement_access.py`. Den er ikke koblet på `app.py`.

## Regression

`python -m unittest tests.test_account_store tests.test_identity_schema tests.test_entitlement_access`

41 tests. 34 bestod, 0 fejlede, 7 sprunget over. De 18 kontotests bestod. De 7 sprunget over er de gamle database-pladsholdere.

## Stadig ikke integreret

- `app.py` og legacy-login
- `public.users`
- Streamlit
- Password reset, e-mail-verifikation og Stripe
- UI læser ikke entitlements

## Testdata der bliver stående

- Auth-brugeren ovenfor
- Én aktiv Free-entitlement på `traderdash`

## Rollback

Slet Auth-brugeren på preview-branchen. Profil og entitlement følger med via cascade. `public.users` og Production berøres ikke. `master` er urørt.
