# Iteration 10

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE**. Pilotappen er `https://traderdash-next.streamlit.app`. Den kører `feature/supabase-auth` med Supabase Auth mod Production `wxvobyifckbpnqfbnlxl`. Den eksisterende app er uændret.

## Review

Repository er `market-tools-lab/TraderDash`. `master` og `origin/master` står på `4d292dae4a43c114df8818d4d7991d9b37149736`. De syv auditfiler under `docs/` er stadig usporede. Auth-koden siden master er committed.

Manglende `TRADERDASH_AUTH_MODE` bliver `legacy`. `supabase_auth` vælges kun ved den værdi. Registrering vises ikke i Auth-mode. Logout fjerner token, user id, e-mail og plan. Entitlement læses, og authenticated kan ikke skrive den. Free er 30, Nordic 79 og International 159. Auth-fejl bliver kort dansk. Preview-URL er ikke default for login. Den bruges kun som afvisning for nulstilling og passwordskift. Ingen Production-testbruger er hardcodet i appen.

Python er 3.12.10 lokalt. Community Cloud bruger 3.12 som standard. `DATABASE_URL` er ikke nødvendig for Auth-login.

## Production

| Kontrol | Resultat |
| --- | --- |
| URL | `https://wxvobyifckbpnqfbnlxl.supabase.co` |
| Auth-bruger | 1, piloten |
| Profile | 1 |
| Link | 1, `migrated` |
| Aktiv Free-entitlement | 1 |
| Legacy-række | 1, plan `free`, status `free` |
| Legacy-hash | uændret og forskellig fra Auth-hashen |
| Andre brugere | 0 |
| Stripe-events | 0 |

Pilotens Auth-password er sat for den ene bruger. Værdien er ikke gemt i Git, dokumentation eller chatten.

## Tests

`python -m unittest discover -s tests`

98 tests. 89 bestod, 0 fejlede, 9 sprunget over. Varighed 15,9 sekunder. De 18 tests i `tests/test_account_store.py` er med i de 89.

Hostet accepttest på `https://traderdash-next.streamlit.app`:

| Kontrol | Resultat |
| --- | --- |
| Auth-login | vist, registrering skjult |
| Forkert login | "Forkert e-mail eller adgangskode." uden stack trace |
| Nulstilling | "Nulstilling kan ikke sendes." |
| Pilot-login | plan Free, profilens e-mail vist |
| Papirer | 30 |
| Analyse | åbner for en dansk aktie |
| International | låst |
| Selvopgradering | afvist, checkout er ikke aktiveret, planen bliver Free |
| Password i siden eller browser-lager | nej |
| Logout og nyt login | består |
| Privat session | kun Auth-login |

## Streamlit

Der findes ikke en dokumenteret API til at oprette Community Cloud-appen. Appen er oprettet manuelt som `traderdash-next`. Secrets ligger kun i den nye app. `https://traderdash-market.streamlit.app` viser stadig legacy-login med "Opret konto" og blev ikke konfigureret. Den var i dvale og blev kun vækket.

## Ikke gjort

- Legacy-appen er ikke ændret
- Legacy-hashen er ikke ændret
- Andre brugere er ikke migreret
- Stripe er ikke aktiveret
- Ingen merge
- Iteration 11 er ikke startet
