# Staging

Dato: 4. november 2026.

| Miljø | Ref | Brug |
| --- | --- | --- |
| Production | `wxvobyifckbpnqfbnlxl` | Auth-pilot og den ene migrerede testbruger |
| Preview | `ajbsoudovxstlolojvte` | Syntetiske tests. Ikke pilotens Auth-mål |
| Legacy-app | `https://traderdash-market.streamlit.app` | `legacy`. Secrets ændres ikke |
| Pilot | `https://traderdash-next.streamlit.app` | `feature/supabase-auth`, `app.py`, Python 3.12, `supabase_auth` |

Pilotens secret-navne er `TRADERDASH_AUTH_MODE`, `TRADERDASH_SUPABASE_URL` og `TRADERDASH_SUPABASE_ANON_KEY`. `DATABASE_URL`, `service_role`, databasepassword, preview-URL og preview-nøgle bruges ikke.

Læst 2026-11-04 på Production, uden skrivning: 1 legacy-bruger, 1 Auth-bruger, 1 profil, 1 migreret link, 1 aktiv Free-entitlement, legacy-plan `free`, legacy-hash scrypt, 0 stripe-events.

Rollback for piloten er at slette kun den app. Schema, Auth-bruger og legacy-app bliver. Nulstilling er stadig låst til preview, fordi mailleverandør ikke er valgt.

Før en senere merge: kør `python -m unittest discover -s tests`, og sæt ikke Auth-secret på legacy-appen.
