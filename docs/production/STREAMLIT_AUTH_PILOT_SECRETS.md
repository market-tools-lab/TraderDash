# Streamlit Auth-pilot, secret-navne

Dato: 4. november 2026. Ingen værdier står her.

Pilotappen er `https://traderdash-next.streamlit.app`. Den må ikke genbruge eller ændre secrets på `traderdash-market.streamlit.app`. De tre navne nedenfor er sat i den nye app. Værdierne står ikke her.

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

Redirect-URL er ikke en secret i denne pilot. Nulstilling og skift af adgangskode bruger den allowlistede pilotadresse. De er ikke låst til den slettede preview.

## Turnstile

Værdierne står ikke her. `captcha.verify()` lukker, før Cloudflare kaldes, hvis et af de tre første navne mangler eller er tomt.

| Navn | Krav i den kørende kode |
| --- | --- |
| `TRADERDASH_TURNSTILE` | præcis `required` |
| `TRADERDASH_TURNSTILE_HOSTNAME` | `traderdash-next.streamlit.app` |
| `TRADERDASH_TURNSTILE_SECRET_KEY` | serverens siteverify-nøgle. En allerede sat værdi udskiftes ikke herfra |
| `TRADERDASH_TURNSTILE_SITE_KEY` | widgetens offentlige nøgle. Den kalder ikke siteverify |
| `TRADERDASH_TURNSTILE_MODE` | `live` på piloten. En ukendt tilstand er ikke i sig selv `missing_configuration` |
| `TRADERDASH_ENV` | `production` på piloten. Samme afgrænsning som tilstanden |

`TRADERDASH_AUTH_REGISTRATION` forbliver `disabled`, medmindre en kontrolleret prøve åbner den.
