# Iteration 2

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **BLOCKED**.

Auth-login er ikke bevist. Der er ikke oprettet en testbruger, og der er ikke kørt et login-script.

## Target

| Kontrol | Resultat |
| --- | --- |
| Project ref | `ajbsoudovxstlolojvte` |
| Branch | `supabase-auth-test`, manuelt verificeret som preview |
| URL | `https://ajbsoudovxstlolojvte.supabase.co` |
| `products`, `plans`, `profiles`, `entitlements` | Findes |
| Auth-brugere | 0 |
| Ikke-syntetiske Auth-brugere | 0 |
| Rækker i `public.users` | 0 |
| Profiler | 0 |
| Entitlements | 0 |

Miljøet indeholder ikke Production-brugerdata.

## Blokering

MCP-forbindelsen har ikke et værktøj til at oprette en Auth-bruger. De tilgængelige databaseværktøjer kan køre SQL og migrationer, men ikke Auth Admin API.

`auth.users` er ikke ændret med SQL. Der er ikke oprettet et password, og der er ikke kaldt en signup-endpoint.

## Ikke udført

- Syntetisk bruger `markettools-auth-test@example.invalid`
- Login med rigtigt og forkert password
- Profiltrigger på en blivende bruger
- Privilegeret Free-entitlement
- Negative adgangstests
- Ændring af `app.py`, legacy-login, `public.users`, Streamlit eller Production

## Regression

Ikke kørt i dette forsøg, fordi iterationen stoppede før ny testkode.

## Rollback

Ingen Auth-bruger er oprettet. Preview-schemaet fra Iteration 1 er uændret. `master` er urørt.

Næste forsøg kan starte, når preview-miljøet kan oprette en Auth-bruger gennem Auth Admin API uden at skrive direkte i `auth.users`, og uden at password eller nøgler lægges i Git.
