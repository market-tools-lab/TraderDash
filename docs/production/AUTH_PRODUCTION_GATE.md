# Auth Production-gate

Dato: 4. november 2026.

| Gate | Status |
| --- | --- |
| Production-ref | `wxvobyifckbpnqfbnlxl`, Traderdash / `main` |
| Preview holdes ude | `ajbsoudovxstlolojvte` er ikke pilotappens target |
| Schema | De to hashede migrationer er kørt. `accounts` er ikke kørt igen |
| Én pilot | Legacy `7a65eb8c-2776-4447-b45c-f5dc542a5abb`, Auth `e8469788-5089-45f4-8a77-60440aa56fc7` |
| Profile, link, Free-entitlement | Findes. Én aktiv entitlement. Legacy-plan `free`. Hash uændret |
| Andre brugere | Ingen. `public.users` = 1 og `auth.users` = 1 |
| Cloud-flag på den gamle app | Ikke sat |
| Separat pilotapp | DONE. `https://traderdash-next.streamlit.app` på `feature/supabase-auth` |
| Pilot-password | Sat for den ene Auth-bruger. Ikke gemt i Git. Legacy-hashen er uændret |
| Stripe | Ikke aktiv |
| Restore | Ikke udført |

Rollback for pilotappen er at slette kun den nye Community Cloud-app. Production-schema, Auth-brugeren, profilen, linket og entitlement bliver stående. Legacy-appen røres ikke.
