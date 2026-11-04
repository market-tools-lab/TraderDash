# Iteration 11

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE** som lokal hostingpakke. Ingen ny vært er valgt, og ingen DNS er ændret.

## Resultat

`Dockerfile` bruger Python 3.12 og lytter på `0.0.0.0` og `PORT`. `.dockerignore` holder `.env` ude af et image. `docs/production/HOSTING.md` nævner secret-navnene og ikke værdierne.

Community Cloud bliver værten for begge apps. Legacy bliver på `legacy`. Piloten bliver på `supabase_auth`.

## Tests

Produktion uden `DATABASE_URL` opretter ikke SQLite, hverken i `legacy` eller `supabase_auth`. Auth uden URL stopper med "Supabase Auth er ikke konfigureret."

## Ikke gjort

- Ingen deploy af imaget
- Ingen ændring af `traderdash-market.streamlit.app` eller `traderdash-next.streamlit.app`
- Ingen Stripe
- Iteration 12 er en separat lokal testtilstand
