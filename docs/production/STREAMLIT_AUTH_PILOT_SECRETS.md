# Streamlit Auth-pilot, secret-navne

Dato: 4. november 2026. Ingen værdier står her.

Pilotappen er en ny Community Cloud-app. Den må ikke genbruge eller ændre secrets på `traderdash-market.streamlit.app`.

| Navn | Formål | Kilde |
| --- | --- | --- |
| `TRADERDASH_AUTH_MODE` | Vælger Auth-vejen. Uden den bliver appen på legacy | Deployment-specifikationen. Det er ikke en Supabase-nøgle |
| `TRADERDASH_SUPABASE_URL` | Production Auth- og API-vært | Supabase Dashboard for Traderdash / `main` / `wxvobyifckbpnqfbnlxl`, Project Settings → API |
| `TRADERDASH_SUPABASE_ANON_KEY` | Publishable klientnøgle til login og læsning | Samme Production API-side. Brug anon- eller publishable-nøglen, som klienten sender som `apikey` |

`DATABASE_URL` skal ikke sættes. Auth-login og entitlement-læsning bruger brugerens session, ikke database-URI'en.

Disse værdier må ikke indsættes:

- `service_role` eller secret key
- databasepassword
- preview-URL `https://ajbsoudovxstlolojvte.supabase.co`
- preview-nøgle
- legacy password eller `password_hash`

Redirect-URL er ikke en secret i denne pilot. Nulstilling og skift af adgangskode er stadig låst til preview og bruges ikke af pilot-login.
