# Iteration 10

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **MANUAL GATE**. Den separate Streamlit-pilotapp er specificeret og ikke oprettet. Den eksisterende app er ikke ændret.

## Review

Repository er `market-tools-lab/TraderDash`. `master` og `origin/master` står på `4d292dae4a43c114df8818d4d7991d9b37149736`. De syv auditfiler under `docs/` er stadig usporede. Auth-koden siden master er committed.

Manglende `TRADERDASH_AUTH_MODE` bliver `legacy`. `supabase_auth` vælges kun ved den værdi. Registrering vises ikke i Auth-mode. Logout fjerner token, user id, e-mail og plan. Entitlement læses, og authenticated kan ikke skrive den. Free er 30, Nordic 79 og International 159. Auth-fejl bliver kort dansk. Preview-URL er ikke default for login. Den bruges kun som afvisning for nulstilling og passwordskift. Ingen Production-testbruger er hardcodet i appen.

Python er 3.12.10 lokalt. Community Cloud bruger 3.12 som standard. `DATABASE_URL` er ikke nødvendig for Auth-login.

## Production, kun læst

| Kontrol | Resultat |
| --- | --- |
| URL | `https://wxvobyifckbpnqfbnlxl.supabase.co` |
| Auth-bruger | 1, piloten |
| Profile | 1 |
| Link | 1, `migrated` |
| Aktiv Free-entitlement | 1 |
| Legacy-række | 1, plan `free`, status `free` |
| Hash | uændret |
| Andre brugere | 0 |

## Tests

`python -m unittest discover -s tests`

98 tests. 89 bestod, 0 fejlede, 9 sprunget over. Varighed 15,9 sekunder. De 18 tests i `tests/test_account_store.py` er med i de 89.

Den isolerede Production-login er ikke kørt. Pilot-passwordet findes ikke i processen og må ikke skrives i chatten.

## Streamlit

Ingen MCP, CLI eller dokumenteret API kan oprette Community Cloud-appen eller lægge secrets ind. Browser-login er ikke brugt. Den gamle app `https://traderdash-market.streamlit.app` er ikke åbnet for ændring.

## Ikke gjort

- Pilotappen er ikke deployet
- Secrets er ikke sat
- Legacy-appen er ikke ændret
- Production-data er ikke skrevet
- Stripe er ikke aktiveret
- Ingen merge
- Iteration 11 er ikke startet
