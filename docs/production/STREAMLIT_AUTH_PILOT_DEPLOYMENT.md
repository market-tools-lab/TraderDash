# Streamlit Auth-pilot, deployment

Dato: 4. november 2026.

| Felt | Værdi |
| --- | --- |
| Repository | `market-tools-lab/TraderDash` |
| Branch | `feature/supabase-auth` |
| Entrypoint | `app.py` |
| Python | 3.12. Lokal kørsel er 3.12.10. Community Cloud bruger 3.12 som standard. Vælg 3.12 under Advanced settings |
| Auth-mode | `supabase_auth` via secret, ikke via kode |
| Supabase | Production `wxvobyifckbpnqfbnlxl` / `https://wxvobyifckbpnqfbnlxl.supabase.co` |
| Preview | `ajbsoudovxstlolojvte` må ikke være appens Auth-target |
| Eksisterende app | `https://traderdash-market.streamlit.app` forbliver legacy og må ikke ændres |

Deployet URL: `https://traderdash-next.streamlit.app`.

De først foreslåede navne var `traderdash-auth-pilot`, `traderdash-auth-test`, `traderdash-login-pilot` og `traderdash-market-auth`. Den oprettede app hedder `traderdash-next`.

Der findes ikke en dokumenteret Community Cloud-API til at oprette appen eller indsætte secrets. Oprettelsen er gjort manuelt. Secrets ligger kun i den nye apps Advanced settings og ikke i Git.

`requirements.txt` i roden er runtime-listen. Der er ingen separat test-requirementsfil. `psycopg` bliver importeret af appen, men Auth-vejen kalder den ikke, og `DATABASE_URL` sættes ikke.

Community Cloud kan ikke skifte Python-version efter deploy uden at appen slettes og oprettes igen. Et push til `feature/supabase-auth` redeployer kun den app, der peger på den branch. Legacy-appen skal blive på sin nuværende branch.

Nulstilling og logget-ind skift af adgangskode følger det konfigurerede Production-projekt. Den slettede preview afvises. Login, profil, entitlement og logout følger den samme URL.

Registrering er lukket i Auth-mode. Stripe er ikke aktiv.

## Pilot 4. november 2026

4. november 2026 blev den første app slettet og oprettet igen, fordi Community Cloud ikke kan skifte branch. Den app pegede da på:

| Felt | Værdi |
| --- | --- |
| URL | `https://traderdash-next.streamlit.app` |
| Branch | `feature/auth-email-recovery` |
| Entrypoint | `app.py` |
| Python | 3.14 |
| Legacy | `traderdash-market` er ikke ændret og peger stadig på `master` |

## Nuværende pilot

9. november 2026 blev samme URL oprettet igen på `feature/public-pilot-finalization`, `app.py` og Python 3.14. Legacy er stadig `master`. Registrering er lukket. Den senere test står i `CONTROLLED_SIGNUP.md`.

Nulstillingen er prøvet én gang samme dag. Resend leverede mailen fra `noreply@auth.markettools.app`. Detaljerne står i `AUTH_EMAIL_RECOVERY.md`. Tabellen øverst beskriver den første oprettelse og er ikke den nuværende kilde.

Senere hostingflytning bruger de samme miljønavne. Koden antager ikke, at Community Cloud er den eneste vært, ud over den eksisterende genkendelse af Cloud, som kun bruges af legacy-databasevejen.
