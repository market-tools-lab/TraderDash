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

Foreslået URL, i rækkefølge hvis navnet er optaget:

1. `https://traderdash-auth-pilot.streamlit.app`
2. `https://traderdash-auth-test.streamlit.app`
3. `https://traderdash-login-pilot.streamlit.app`
4. `https://traderdash-market-auth.streamlit.app`

Der findes ikke en dokumenteret Community Cloud-API til at oprette appen eller indsætte secrets. Oprettelsen er derfor en manuel gate. Secrets sættes kun i den nye apps Advanced settings og ikke i Git.

`requirements.txt` i roden er runtime-listen. Der er ingen separat test-requirementsfil. `psycopg` bliver importeret af appen, men Auth-vejen kalder den ikke, og `DATABASE_URL` sættes ikke.

Community Cloud kan ikke skifte Python-version efter deploy uden at appen slettes og oprettes igen. Et push til `feature/supabase-auth` redeployer kun den app, der peger på den branch. Legacy-appen skal blive på sin nuværende branch.

Nulstilling og skift af adgangskode i UI afviser enhver anden vært end preview. Login, profil, entitlement og logout følger den konfigurerede Production-URL.

Registrering er lukket i Auth-mode. Stripe er ikke aktiv. Mailleverandør er ikke valgt.

Senere hostingflytning bruger de samme miljønavne. Koden antager ikke, at Community Cloud er den eneste vært, ud over den eksisterende genkendelse af Cloud, som kun bruges af legacy-databasevejen.
