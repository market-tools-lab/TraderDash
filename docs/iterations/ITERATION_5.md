# Iteration 5

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**.

En syntetisk migreret bruger kan sætte et nyt Auth-password, logge ind, læse egen profil og entitlement, skifte password igen og logge ud. Legacy-hashen blev ikke flyttet. Registrering er stadig lukket, og default er stadig `legacy`. Iteration 6 er ikke startet.

## Target

| Kontrol | Resultat |
| --- | --- |
| Project ref | `ajbsoudovxstlolojvte` |
| Branch | `supabase-auth-test` |
| URL | `https://ajbsoudovxstlolojvte.supabase.co` |
| Production | Ikke kontaktet |
| Streamlit Cloud | Ikke ændret |
| `master` | Står på `4d292dae4a43c114df8818d4d7991d9b37149736` |

Før arbejdet var preview: én Auth-bruger `markettools-auth-test@example.invalid`, id `63ffe985-0e7e-48bd-b41b-d1741330257a`, én profil, ingen entitlement, `public.users` = 0 og `legacy_auth_links` = 0. Den bruger er ikke ændret.

## Aktivering

```text
legacy account
→ migration dry-run
→ Auth identity
→ profile
→ legacy_auth_link
→ entitlement
→ password setup/reset
→ verified Auth login
→ senere pilot cutover
```

| Trin | Regel |
| --- | --- |
| A | Legacy-brugeren migreres uden password-hash |
| B | Auth-brugeren oprettes eller findes |
| C | De to kobles i `legacy_auth_links` |
| D | Entitlement oprettes af den eksisterende migration |
| E | Brugeren vælger et nyt password gennem Supabase Auth |
| F | Legacy-rækken bevares i pilotperioden |
| G | Den gamle hash kopieres ikke til Auth |
| H | Legacy-login bliver ved med at virke, indtil den konkrete bruger senere skiftes |

`pilot_migration.py` læser stadig kun user id, e-mail, plan og status. Den skriver ikke i `auth.users` og sletter ikke legacy-rækken. Der er ingen migrationsknap i appen.

## Password

Politikken ligger i `password_policy.py`. Den kræver 12 til 128 tegn, tillader en lang passphrase og har ingen udløb. Enkelttegn, rene tal og en kort liste af åbenlyst svage værdier afvises. Fejlteksten gentager ikke passwordet. Bekræftelsen skal være identisk. Legacy-scrypt-reglen i `accounts.py` er uændret.

Auth-funktionerne ligger i `supabase_auth.py`, ikke i `app.py`. `app.py` viser kun formularerne, når `TRADERDASH_AUTH_MODE=supabase_auth`.

| Funktion | Adfærd |
| --- | --- |
| `request_password_reset` | Samme neutrale svar. Adressen afsløres ikke |
| `verify_recovery_session` | Tomt eller ugyldigt token giver ingen session |
| `update_password` | Kræver gyldig session og politikken |
| `change_password` | Sammenligner bekræftelsen og bruger den aktuelle session |
| `sign_out_all_supported_sessions` | `POST /auth/v1/logout?scope=global`, derefter lokal oprydning |

Redirect accepteres kun for `https://ajbsoudovxstlolojvte.supabase.co` uden brugerinfo, query, fragment eller andet portnummer. En anden URL afvises før kaldet. Der er ingen Production-fallback. E-mail, password og token logges ikke. `remember`, logout og passwordskift fjerner password og bekræftelse fra sessionen. Den synlige tekst ved en anmodning er: "Hvis adressen kan bruges, er et nulstillingslink sendt."

Et svar under HTTP 500, herunder 429, giver samme neutrale tekst. Først fra 500 vises en generel fejl. Det afslører ikke, om adressen findes.

## Mail

Der er ikke valgt Resend, Postmark eller Amazon SES. Preview returnerer ikke et brugbart reset-link, og recovery-tokenet i `auth.users` kan ikke læses som et link. Derfor er selve e-mail-linket ikke gennemført.

Det manglende led er en mailkanal, der kan aflevere GoTrue-linket til brugeren. Passwordopdatering og login er bevist uden den kanal, så iterationen er ikke blokeret af det.

## Preview

Syntetisk bruger `markettools-mig-reset5@example.invalid`, Auth-id `f30d51fe-4359-4f9a-b478-1e752d1c10f6`, legacy-id `legacy-mig-reset5`, plan `free`.

| Trin | Resultat |
| --- | --- |
| Før skrivning | Profil fandtes. Link 0. Entitlement 0. Legacy-hash fandtes |
| Migration | Ét link `pilot-reset` og én aktiv `traderdash` / `free` |
| Første login | User id og profil matchede. Plan `free`. 30 papirer |
| Passwordskift | Nyt password blev sat via `PUT /auth/v1/user` |
| Globalt logout | Lokal token og password-nøgler blev fjernet |
| Gammelt password | Afvist |
| Nyt password | Login, plan `free` |
| Session | Password og bekræftelse var væk efter login |
| Nulstillingsanmodning | Neutralt ja for både den syntetiske adresse og en ukendt adresse |
| Logout | Token og user id fjernet |
| Entitlement-skrivning | HTTP 403 |
| Hash | Auth-hashen adskilte sig fra legacy-hashen. Legacy-hashen stod stadig |

Recovery-tokenets længde var 0, og `recovery_sent_at` var tom. Et efterfølgende recover-kald fik HTTP 429. Der blev ikke gemt et link eller et token i repo, dokumentation eller log.

Brugeren, profilen, linket, entitlementen og legacy-rækken blev slettet bagefter.

## Tilbage på preview

| Kontrol | Resultat |
| --- | --- |
| Syntetiske migrationsbrugere | 0 |
| Links | 0 |
| Entitlements | 0 |
| `public.users` | 0 |
| Stående Auth-bruger | `63ffe985-0e7e-48bd-b41b-d1741330257a` |
| Profiler | 1 |

## Tests

`python -m unittest tests.test_password_reset tests.test_supabase_auth tests.test_supabase_auth_preview tests.test_account_store tests.test_identity_schema tests.test_entitlement_access tests.test_pilot_migration`

73 tests. 65 bestod, 0 fejlede, 8 sprunget over. De 18 legacy-kontotests bestod. Preview-login-testen sprang over, fordi dens miljø ikke var sat. Den live kørsel ovenfor brugte de samme moduler.

## Rollback

Sæt `TRADERDASH_AUTH_MODE=legacy`, eller fjern variablen. Appen bruger da den nuværende login, og reset-formularen vises ikke.

Et gennemført passwordskift ændrer kun Auth-brugeren. Det ændrer ikke legacy-hashen. Linktabellen kan fjernes med `drop table public.legacy_auth_links`, som beskrevet i iteration 4. Det sletter ikke `public.users`.

## Ikke gjort

- Ingen rigtig bruger er migreret
- Ingen åben registrering
- Ingen mailleverandør
- Ingen e-mail med et reset-link
- Ingen per-bruger cutover
- Cloud-flaget er ikke sat
- Roadmap-filen på `D:\Market Tools` kunne ikke findes og er derfor ikke opdateret

## Næste skridt

Iteration 6 startes ikke. Den bør først vælge, hvornår en konkret linked bruger skal bruge Auth i stedet for legacy-login. Registrering skal blive ved med at være lukket, og Cloud skal blive på `legacy`, indtil det er testet bevidst. Mailleverandør vælges først, når reset-linket skal kunne sendes.
