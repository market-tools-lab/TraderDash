# Hosting

Dato: 4. november 2026.

Community Cloud bliver værten. Der er ikke valgt en ny vært, og ingen DNS er ændret.

| App | URL | Branch | Auth |
| --- | --- | --- | --- |
| Legacy | `https://traderdash-market.streamlit.app` | nuværende | `legacy` |
| Pilot | `https://traderdash-next.streamlit.app` | `feature/supabase-auth` | `supabase_auth` |

`Dockerfile` bruger Python 3.12, lytter på `0.0.0.0` og porten `PORT`. Den er ikke deployet.

En senere vært skal have disse navne og ingen værdier i Git:

| Navn | Brug |
| --- | --- |
| `TRADERDASH_ENV` | `production` |
| `TRADERDASH_AUTH_MODE` | `supabase_auth` på piloten, fraværende på legacy |
| `TRADERDASH_SUPABASE_URL` | Production-URL for `wxvobyifckbpnqfbnlxl` |
| `TRADERDASH_SUPABASE_ANON_KEY` | anon- eller publishable-nøgle |

`DATABASE_URL` hører ikke til Auth-login. `service_role`, databasepassword og preview-nøglen hører ikke til appen.

Rollback er at lade begge Cloud-apps blive. Image og DNS bruges ikke, før login er prøvet på den nye vært.
