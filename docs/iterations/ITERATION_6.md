# Iteration 6

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**.

TraderDash kan starte lokalt i `supabase_auth` mod preview og give adgang ud fra entitlement. Legacy er stadig default. Iteration 7 er ikke startet.

## Target

| Kontrol | Resultat |
| --- | --- |
| Project ref | `ajbsoudovxstlolojvte` |
| Branch | `supabase-auth-test` |
| URL | `https://ajbsoudovxstlolojvte.supabase.co` |
| Production | Ikke kontaktet |
| Streamlit Cloud | Ikke ændret |
| `master` | Står på `4d292dae4a43c114df8818d4d7991d9b37149736` |

Før arbejdet var preview: én Auth-bruger `markettools-auth-test@example.invalid`, id `63ffe985-0e7e-48bd-b41b-d1741330257a`, én profil, ingen entitlement, `public.users` = 0 og `legacy_auth_links` = 0. Den bruger er ikke ændret og er ikke slettet.

## Flow

```text
TraderDash
→ Supabase Auth
→ Auth-session
→ profile
→ entitlement
→ plan
→ aktieunivers
→ logout
```

`TRADERDASH_AUTH_MODE=supabase_auth` vælger Auth. Manglende eller ukendt værdi bliver ved med at være `legacy`. En session, der allerede har et Auth-token, bliver ikke lydløst til en legacy-bruger, hvis mode skifter. Appen viser da "Login-måden er ændret. Log ind igen." og bruger ikke Auth-id'et som legacy-id.

Supabase-mode læser ikke legacy-databasen. Lokal start krævede ikke `DATABASE_URL`. Legacy-mode bruger fortsat lokal SQLite, når den variabel mangler.

## Lokal start

Begge processer bandt kun til `127.0.0.1` og blev stoppet bagefter.

| Mode | Port | Health | Traceback |
| --- | --- | --- | --- |
| `supabase_auth` | 8766 | ja | nej |
| `legacy` | 8767 | ja | nej |

## UI

I Auth-mode vises login, nulstillingslink, ny adgangskode, bekræftelse, skift adgangskode og logout. Åben registrering vises ikke. Teksten er "Ny konto oprettes ikke i denne loginvej."

Forkert login siger "Forkert e-mail eller adgangskode." Ukendte Auth-fejl erstattes af "Supabase Auth er ikke tilgængelig." Projekt-ref, API-URL, token og UUID vises ikke. En manglende profil stopper med "Kontoen er ikke klar."

Legacy-visningen har stadig "Log ind" og "Opret konto" og kalder `accounts.authenticate`, `accounts.create_user` og `accounts.get_user`.

## Preview

Ni syntetiske brugere på `markettools-mig-i6…@example.invalid` blev oprettet, testet og slettet. Dry-run skrev intet. Den faktiske migration skrev fire links. Auth-hash og legacy-hash var ikke ens.

| Scenarie | Resultat |
| --- | --- |
| Free | Plan `free`, 30 papirer, analyse åbnet |
| Nordic | Plan `nordic`, 79 papirer |
| International | Plan `international`, 159 papirer |
| Ingen entitlement | Login, ingen adgang |
| Suspended, revoked, expired | Ingen adgang |
| Past due | Migreret til `suspended`, ingen adgang |
| Manglende profil | "Kontoen er ikke klar." |
| Free-aktie | Novo Nordisk kunne vælges |
| Låst marked | "Available with TraderDash International" |
| Logout | Token, user id, e-mail og plan væk |
| Nyt login | Samme Free-bruger kom ind igen |

Password lå ikke i sessionen efter afvist login, efter login eller efter logout.

## Isolation

Free og Nordic kørte i hver sin app-session. Logout i den ene ændrede ikke den andens plan eller user id. Hver bruger læste kun sin egen profil og sin egen entitlement. Markedscachen er nølet på ticker og periode, ikke på token eller session.

## Fejl

Manglende URL, ugyldig nøgle, timeout og HTTP 503 gav den korte danske tekst og ingen stack trace. Appen skiftede ikke til legacy midt i Auth-sessionen.

## Tests

`python -m unittest discover -s tests`

87 tests. 78 bestod, 0 fejlede, 9 sprunget over. Varighed 15,9 sekunder. De 18 legacy-kontotests bestod. De ni overspringelser er de eksisterende placeholders og preview-tests uden miljø.

Streamlit skrev `missing ScriptRunContext` under AppTest. Biblioteket siger, at advarslen kan ignoreres i bare mode. Der var ingen andre testadvarsler.

Den live kørsel mod preview brugte samme AppTest og bestod for planer, lukkede tilstande, logout, nyt login og isolation. Den indgår ikke i de 87, fordi den kun kører, når en midlertidig fixture er sat.

## Tilbage på preview

| Kontrol | Resultat |
| --- | --- |
| Syntetiske migrationsbrugere | 0 |
| Links | 0 |
| Entitlements | 0 |
| `public.users` | 0 |
| Stående Auth-bruger | `63ffe985-0e7e-48bd-b41b-d1741330257a` |
| Profiler | 1 |

## Rollback

Sæt `TRADERDASH_AUTH_MODE=legacy`, eller fjern variablen. Ingen Cloud-secret er ændret.

## Ikke gjort

- Ingen rigtig bruger er migreret
- Ingen åben registrering
- Ingen mailleverandør
- Cloud-flaget er ikke sat
- Roadmap og migrationsplan på `D:\Market Tools` kunne ikke findes og er derfor ikke opdateret

## Næste skridt

Iteration 7 startes ikke. Cloud skal blive på `legacy`. Næste skridt bør først være en eksplicit cutover for én bruger, som Theis navngiver. Registrering skal blive ved med at være lukket, og mailleverandør er stadig ikke valgt.
