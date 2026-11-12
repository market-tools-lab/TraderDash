# Konfigurationsnavne

Dato: 12. november 2026. Værdier for hemmeligheder står ikke her. De ligger i Streamlit-secrets på den app, der skal bruge dem, og i Theis' sikre opbevaring. Git har kun navnene og placeholders i `.streamlit/secrets.toml.example`.

| Navn | Formål | Lag | Hemmelig | Miljø | Lukket standard | Opbevaring |
| --- | --- | --- | --- | --- | --- | --- |
| `TRADERDASH_ENV` | Skelner production fra en lokal testtilstand | Platform | Nej | Pilot: `production` | En ukendt værdi er ikke i sig selv en manglende Turnstile-konfiguration. Production afviser testnøgler | Streamlit-secrets |
| `TRADERDASH_AUTH_MODE` | Vælger Auth-vejen | Platform | Nej | Pilot: `supabase_auth`. Legacy: mangler | Mangler eller ukendt bliver `legacy` | Streamlit-secrets |
| `TRADERDASH_AUTH_REGISTRATION` | Åbner kun den kontrollerede tilmelding | Platform | Nej | Lukket | Mangler, `disabled` og enhver anden tekst er lukket. Kun `enabled` gør koden klar | Streamlit-secrets |
| `TRADERDASH_PASSWORD_RECOVERY` | Tillader et nulstillingskald | Platform | Nej | Pilot: sat, når nulstilling er i drift | Mangler: intet recover-kald | Streamlit-secrets |
| `TRADERDASH_AUTH_EMAIL_DELIVERY` | Bekræfter, at SMTP er sat bevidst | Platform | Nej | `configured`, når udbyderen er valgt | Mangler: intet mailkald | Streamlit-secrets |
| `TRADERDASH_AUTH_REDIRECT_URL` | Den ene adresse et Auth-link må vende tilbage til | Platform | Nej | `https://traderdash-next.streamlit.app` | Mangler eller uden for allowlisten: kaldet afvises | Streamlit-secrets |
| `TRADERDASH_AUTH_REDIRECT_ALLOWLIST` | Eksakte tilladte adresser | Platform | Nej | Samme pilotadresse | Tom liste: ingen redirect accepteres | Streamlit-secrets |
| `TRADERDASH_TURNSTILE` | Kræver serverkontrol før Auth | Platform | Nej | `required` | Alt andet lukker, før Cloudflare kaldes | Streamlit-secrets |
| `TRADERDASH_TURNSTILE_MODE` | `live` eller `test` | Platform | Nej | Pilot: `live` | En ukendt tilstand er ikke i sig selv `missing_configuration` | Streamlit-secrets |
| `TRADERDASH_TURNSTILE_HOSTNAME` | Værten siteverify skal bekræfte | Platform | Nej | `traderdash-next.streamlit.app` | Tom værdi lukker, før Cloudflare kaldes | Streamlit-secrets |
| `TRADERDASH_TURNSTILE_SITE_KEY` | Offentlig nøgle til widgettet | Platform | Nej | Pilotens widget | Widgettet kan ikke rende uden den. Den kalder ikke siteverify | Streamlit-secrets |
| `TRADERDASH_TURNSTILE_SECRET_KEY` | Serverens siteverify-nøgle | Platform | Ja | Kun serveren | Tom værdi lukker, før Cloudflare kaldes | Streamlit-secrets. Værdien skrives ikke her |
| `TRADERDASH_SUPABASE_URL` | Auth- og API-vært | Platform | Nej | `https://wxvobyifckbpnqfbnlxl.supabase.co` | Mangler: Auth-mode er ikke klar | Streamlit-secrets |
| `TRADERDASH_SUPABASE_ANON_KEY` | Publishable klientnøgle | Platform | Ja | Pilotens Auth-kald | Mangler: Auth-mode er ikke klar | Streamlit-secrets. Værdien skrives ikke her |

`TRADERDASH_REGISTRATION` og `TRADERDASH_STRIPE` er gamle navne. Den nuværende tilmelding læser dem ikke. Sundhedstjekket bliver `not_ready`, hvis et af dem er sandt. De fjernes ikke, så længe en eksisterende secret kan indeholde dem.

Legacy-appen bruger `environment` og `database_url`. De er ikke `TRADERDASH_`-navne og sættes ikke på Auth-piloten.
