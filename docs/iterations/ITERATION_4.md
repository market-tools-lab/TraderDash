# Iteration 4

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**.

Pilotmigreringen er bygget og kørt med syntetiske rækker på preview. Ingen rigtig bruger er migreret. Iteration 5 er ikke startet.

## Target

| Kontrol | Resultat |
| --- | --- |
| Project ref | `ajbsoudovxstlolojvte` |
| Branch | `supabase-auth-test` |
| URL | `https://ajbsoudovxstlolojvte.supabase.co` |
| Production | Ikke kontaktet |
| Streamlit Cloud | Ikke ændret |
| `master` | Står på `4d292dae4a43c114df8818d4d7991d9b37149736` |

Før arbejdet var preview: én Auth-bruger `markettools-auth-test@example.invalid`, id `63ffe985-0e7e-48bd-b41b-d1741330257a`, én profil, ingen entitlement, `public.users` = 0. Den bruger er ikke ændret.

## Beslutninger

Linktabellen `public.legacy_auth_links` er nødvendig. Den gør kørslen idempotent, spærrer for at samme legacy-bruger eller samme Auth-bruger migreres to gange, og kan slettes uden at slette legacy-rækken. Den har ingen e-mail, credential eller token.

Trialing giver ikke adgang. Der er ikke en godkendt arkitektur, der udtrykkeligt tillader det. En fremtidig `ends_at` på en opsagt række giver heller ikke fortsat adgang.

Legacy-tabellen staver status `cancelled`. Mapperen accepterer også `canceled`. `unpaid`, `revoked` og `suspended` findes ikke i legacy-checket. De kan ikke indsættes, og mapperen giver dem ingen aktiv adgang.

GoTrue Admin HTTP findes ikke i det tilgængelige MCP-værktøj, og public signup afviser det reserverede testdomæne. Fixtures oprettes derfor med den privilegerede Auth-insert, der virkede i iteration 3. Den ligger i `pilot_fixture.py`. `pilot_migration.py` importerer den ikke og skriver ikke i `auth.users`.

Der er ingen migrationsknap i appen. Default er stadig `legacy`.

## Kontrakt

Input er legacy user id, Auth user id, produktkode, en valgfri reference og valgfri datoer. Plan og status læses fra legacy-rækken. E-mail bruges kun til match og kopieres ikke. Password-hash læses ikke og skrives ikke.

| Legacy | Resultat |
| --- | --- |
| Plan `free` og status `free` | Aktiv `traderdash` / `free` |
| Status `active` og kendt plan | Aktiv entitlement for den plan |
| `past_due` eller `suspended` | Entitlement `suspended`, ingen adgang |
| `trialing` | Entitlement `suspended`, ingen adgang |
| `cancelled` / `canceled`, også med fremtidig slutdato | Entitlement `expired`, ingen adgang |
| `unpaid` eller `revoked` | Entitlement `revoked`, ingen adgang |
| `incomplete` eller `expired` | Entitlement `expired`, ingen adgang |
| Ukendt plan, ukendt status eller `free` på en betalt plan | Afvises, intet skrives |
| E-mail matcher ikke | Afvises, intet skrives |
| Legacy- eller Auth-bruger mangler | Afvises, intet skrives |

Dry-run returnerer den planlagte handling og skriver intet. Anden kørsel med samme par er `already_migrated` og skriver ikke en ny række.

Manglende target, forkert project ref og enhver anden URL afvises før et gateway-kald. Der er ingen fallback til Production.

## Preview

Syntetiske brugere på `markettools-mig-…@example.invalid` blev oprettet, migreret og slettet i samme kørsel.

| Scenarie | Resultat |
| --- | --- |
| Free / free | Aktiv free, 30 papirer |
| Nordic / active | Aktiv nordic, 79 papirer |
| International / active | Aktiv international, 159 papirer |
| Past due | `suspended` |
| Cancelled uden og med fremtidig slutdato | `expired` |
| Trialing | `suspended` |
| Incomplete og expired | `expired` |
| Dry-run | Ingen link og ingen entitlement |
| Forkert e-mail, manglende Auth, manglende legacy | Ingen skrivning |
| Anden kørsel og ekstra link-insert | Én linkrække. Dublet blev afvist |
| Ukendt plan `gold` og status `revoked` | Legacy-insert afvist. Ingen række |

Free-brugeren loggede ind bagefter. Sessionens user id matchede, profilen matchede, planen var `free`, universet var 30, password-nøglerne var væk efter login, ændring af entitlement gav HTTP 403, og logout fjernede token og user id.

Legacy-rækkerne stod stadig med deres hash under testen. De blev slettet bagefter sammen med Auth-bruger, profil, entitlement og link.

## Tilbage på preview

| Kontrol | Resultat |
| --- | --- |
| Syntetiske migrationsbrugere | 0 |
| Links | 0 |
| Entitlements | 0 |
| `public.users` | 0 |
| Stående Auth-bruger | `63ffe985-0e7e-48bd-b41b-d1741330257a` |
| Profiler | 1 |

Tabellen `legacy_auth_links` bliver stående. Den er tom.

## Tests

`python -m unittest tests.test_pilot_migration tests.test_supabase_auth tests.test_supabase_auth_preview tests.test_account_store tests.test_identity_schema tests.test_entitlement_access`

68 tests. 60 bestod, 0 fejlede, 8 sprunget over. De 18 legacy-kontotests bestod. Preview-login-testen sprang over, fordi dens miljø ikke var sat. Den live kørsel ovenfor brugte de samme moduler.

## Rollback

Sæt `TRADERDASH_AUTH_MODE=legacy`, eller fjern variablen. Appen bruger da den nuværende login.

På preview kan linktabellen fjernes med `drop table public.legacy_auth_links`. Entitlements med `source = migration` kan slettes uden at slette legacy-brugeren. Migrationen sletter ikke legacy-rækker og ændrer ikke deres hash.

## Ikke gjort

- Ingen rigtig bruger er migreret
- Ingen åben registrering
- Ingen Stripe
- Ingen nulstilling af password
- Cloud-flaget er ikke sat
- Roadmap-filen på `D:\Market Tools` kunne ikke findes i denne session og er derfor ikke opdateret

## Næste skridt

Iteration 5 startes ikke. Den bør først være en preview-only nulstilling af password for en navngiven syntetisk pilot, stadig med default `legacy` og uden åben registrering.
