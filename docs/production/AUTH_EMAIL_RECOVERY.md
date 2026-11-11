# Auth-mail og nulstilling af adgangskode

Dato: 4. november 2026. Branch: `feature/auth-email-recovery`.

Registrering er lukket. Stripe er slået fra. Legacy forbliver default. Én rigtig nulstillingsmail er sendt og gennemført samme dag. Den er beskrevet under "Gennemført prøve". Suite-testen sender stadig ingen mail.

## Hvad koden allerede gjorde

`supabase_auth.py` kan kalde `POST /auth/v1/recover`. Svaret afslører ikke, om adressen findes. Supabase Auth ejer linket og afsendelsen. Appen sender ikke selv mail og har ingen SMTP-klient.

Før denne branch var kaldet låst til preview-projektet `ajbsoudovxstlolojvte`, og `redirect_to` skulle være selve preview-origin. Det link fører ikke tilbage til Streamlit. Et hash-fragment med access token kan Streamlit-serveren ikke læse. Derfor bruges Supabases `token_hash`-mønster: linket lander på en allowlistet app-URL med `token_hash` og `type=recovery` i query-strengen. Appen bytter hash til en session via `POST /auth/v1/verify`, sætter adgangskoden og logger den session ud. Refresh-token gemmes ikke.

Logget-ind skift af adgangskode bruger det konfigurerede projekt og afviser den slettede preview via `_refuse_deleted_preview`. Det er en anden vej end nulstillingslinket.

## Tiltænkt forløb

1. Brugeren vælger "Send nulstillingslink" og skriver en e-mail.
2. Tom eller ugyldig adresse afvises med "Angiv en gyldig e-mailadresse." uden kald.
3. Når levering er slået til, får både kendt og ukendt adresse det samme neutrale svar: "Hvis der er en konto til e-mailadressen, sender vi en vejledning."
4. Supabase opretter recovery-linket, hvis adressen findes. Ukendt adresse giver samme HTTP-resultat udadtil.
5. Den valgte udbyder leverer mailen, fordi Supabase SMTP peger på udbyderen. Appen gør det ikke.
6. Linket må kun gå til `TRADERDASH_AUTH_REDIRECT_URL`, og den adresse skal stå eksakt i `TRADERDASH_AUTH_REDIRECT_ALLOWLIST`.
7. Appen læser `token_hash` og `type=recovery`, sletter query-parametrene og beder om en ny adgangskode to gange.
8. Politikken er 12 til 128 tegn. Den samme regel bruges ved skift og ved nulstilling.
9. Efter et gyldigt link sættes adgangskoden, sessionen lukkes, og brugeren ser "Adgangskoden er opdateret. Log ind igen."
10. Udløbet, genbrugt, forkert type, forkert projekt-ref eller et PKCE-`code` uden browser-verifier afvises med "Nulstillingen er ikke gyldig." Værdierne logges ikke.
11. Legacy-login kalder ikke recover. Et recovery-parameter på legacy-appen slettes og bruges ikke.

## Kontakter

To kontakter skal begge være sat, før appen kalder Auth:

| Navn | Værdi der tænder | Fravær |
| --- | --- | --- |
| `TRADERDASH_PASSWORD_RECOVERY` | `enabled` | intet recover-kald |
| `TRADERDASH_AUTH_EMAIL_DELIVERY` | `configured` | intet recover-kald |

`configured` betyder, at en operatør har sat Supabase SMTP bevidst. Appen kan ikke se, om dashboardet faktisk har en udbyder. Kontakten er derfor en bevidst lås, ikke en kontrol af udbyderens konto.

Redirect-navne:

| Navn | Hemmelig | Formål |
| --- | --- | --- |
| `TRADERDASH_AUTH_REDIRECT_URL` | Nej | Den ene URL, appen sender som `redirect_to` |
| `TRADERDASH_AUTH_REDIRECT_ALLOWLIST` | Nej | Kommaseparerede eksakte URL'er. Ingen bruger-input tilføjes |

`https://localhost` afvises. `http://localhost:8501` og `http://127.0.0.1:8501` kan stå på listen til lokal kørsel. Alle andre mål skal være `https` uden bruger, query eller fragment.

De eksisterende navne `TRADERDASH_AUTH_MODE`, `TRADERDASH_SUPABASE_URL` og `TRADERDASH_SUPABASE_ANON_KEY` er uændrede. SMTP-værter, SMTP-adgangskoder og provider-nøgler hører til i Supabase-dashboardet, ikke i Streamlit-secrets og ikke i git.

## Rate limits

Appen har en pause på 60 sekunder i den samme Streamlit-session. Det er kun en gentagelsesspærring i den ene browser. Det er ikke en sikkerhedsgrænse for IP eller konto.

Supabase Auth, læst 4. november 2026 på `https://supabase.com/docs/guides/auth/rate-limits` og `https://supabase.com/docs/guides/auth/auth-smtp`:

- Indbygget afsender: 2 mails i timen for projektet, og kun til organisationens team-medlemmer.
- Egen SMTP starter med et lavt loft. Dokumentationen nævner 30 mails i timen, indtil loftet hæves under Authentication, Rate Limits.
- `POST /auth/v1/recover` har som udgangspunkt 60 sekunder pr. bruger og et IP-loft på 30 forespørgsler pr. 5 minutter.

Udbyderen har sit eget loft. Tallene skal læses igen, før recovery tændes for en anden app. Appen opfinder ikke en fælles hukommelses-tæller og kalder den ikke tilstrækkelig.

## Skabeloner

Kladderne ligger i `docs/production/email/`. Reset password-skabelonen i Supabase er den danske kladde. `{{ .RedirectTo }}` er den allowlistede app-URL uden query, og skabelonen tilføjer `?token_hash={{ .TokenHash }}&type=recovery`. Prøven brugte den.

`password-changed.txt` er ikke til udsendelse. Appen bekræfter skiftet på skærmen. En mail om ændret adgangskode tændes ikke i denne omgang.

## Supabase-dashboard

Sat på Production `wxvobyifckbpnqfbnlxl` før prøven. Værdierne ligger kun i dashboardet.

- Redirect URLs: `https://traderdash-next.streamlit.app`. Ikke legacy-appen `https://traderdash-market.streamlit.app`.
- Site URL er ikke flyttet over på legacy-appen.
- SMTP peger på Resend. Afsender er `noreply@auth.markettools.app`. Afsendernavnet vises som TraderDash. Adgangskoden ligger ikke her.
- Reset password-skabelonen er den danske kladde. Emnet er "Nulstil din adgangskode til TraderDash".
- Beskeden "Email address changed" var slået fra, da Auth-adressen blev skiftet med Admin API.

## Gennemført prøve

Dato: 4. november 2026. Én anmodning fra `https://traderdash-next.streamlit.app`.

| Kontrol | Resultat |
| --- | --- |
| Auth-bruger | Samme id `e8469788-5089-45f4-8a77-60440aa56fc7` |
| Auth-mail | `theisbjerken@gmail.com`, bekræftet |
| Profil | Samme id |
| Link | `pilot-i9`, `migrated`, samme Auth-id |
| Entitlement | Én aktiv TraderDash Free, kilde `migration`. Ingen ny række |
| Stripe | Ingen `stripe_events`. Ingen betalt entitlement |
| Legacy-række | `public.users` er stadig `traderdashtesttest@example.dk`, plan `free` |
| Migrationer | `accounts`, `identity_catalog`, `legacy_auth_links`. Ingen ny |
| Pilotens svar | "Hvis der er en konto til e-mailadressen, sender vi en vejledning." |
| Mail | Ankom. Afsender TraderDash, `noreply@auth.markettools.app` |
| Linkvært | `traderdash-next.streamlit.app` |
| Ny adgangskode | Formularen blev brugt. Appen svarede "Adgangskoden er opdateret. Log ind igen." |
| Login bagefter | Samme Free-bruger |
| Anden mail | Ikke sendt |

Token, det fulde link, adgangskoden og SMTP-nøglen er ikke skrevet ned.

## Rollback

Slet eller tøm `TRADERDASH_PASSWORD_RECOVERY` og `TRADERDASH_AUTH_EMAIL_DELIVERY` på den app, der har dem. Appen holder op med at kalde recover og med at indløse links. Supabase-skabelonen og DNS kan blive stående. Slå custom SMTP fra i dashboardet, hvis afsendelsen også skal stoppe der. Der køres ikke SQL.

## Test

Suite køres med `python -m unittest discover -s tests`. Ingen production-nøgle, ingen rigtig SMTP og ingen rigtig mail. Legacy uden `TRADERDASH_AUTH_MODE` forbliver `legacy`.
