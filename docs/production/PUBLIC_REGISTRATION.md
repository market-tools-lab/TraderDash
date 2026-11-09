# Kontrolleret registrering

Dato: 9. november 2026. Branch: `feature/controlled-registration`. Udgangspunkt: `master` `8c4ced6b9007ba63999bf34fe4fb8c2b32fbeb21`.

Registrering er lukket. Denne tekst åbner den ikke. Ingen mail er sendt, ingen bruger er oprettet, og ingen Auth-indstilling er ændret.

## Flag

`TRADERDASH_AUTH_REGISTRATION=enabled` er den eneste værdi, der gør koden klar. Manglende værdi, `disabled` og enhver anden tekst er lukket. Legacy læser ikke flaget. `traderdash-market` beholder sin egen `Opret konto`.

Koden er ikke nok. Et kald kræver også `supabase_auth`, begge leveringskontakter, en allowlistet redirect og et token, som serveren har godkendt. Uden det token sender formularen ikke et Auth-kald.

Sundhedstjekket bliver `not_ready`, hvis flaget er `enabled` eller en ukendt værdi. Det er et driftssignal.

## Forløb

En ny bruger angiver e-mail, adgangskode og gentagelse og accepterer, at privatlivsteksten er et udkast. Koden beder Supabase Auth oprette brugeren og kræver, at svaret ikke indeholder en session. Adgangen forbliver lukket, indtil adressen er bekræftet, profilen findes, og der er præcis én aktiv Free-entitlement.

Bekræftelsesmailen skal følge den samme vej som nulstilling: Supabase Auth, Resend, `auth.markettools.app`, og et link tilbage til en allowlistet app-adresse med `token_hash` og `type=signup`. Appen bytter hash uden at gemme sessionen. Et `type=recovery`-link bliver ved med at være nulstilling.

Den synlige tekst ved et kald er "Hvis adressen kan bruges, sender vi en bekræftelse." Et dublet-kald bruger den samme tekst.

## Data

Profilen oprettes af den eksisterende trigger `handle_new_user` i samme databasettransaktion som Auth-brugeren. Entitlement oprettes først bagefter, og kun for TraderDash. `provision_traderdash_free_self()` læser den bekræftede bruger fra databasen og kalder den eksisterende funktion for netop den bruger. `anon` kan ikke kalde den. Den brede funktion med et vilkårligt id er stadig lukket for `anon` og `authenticated`. `apply_free_entitlement` er kun en testskriver. Den kan ikke skrive i Production, den slettede preview eller for et beskyttet id. Appen kalder den ikke. Den nye funktion er forberedt og ikke kørt på Production.

Free er den eneste plan. Den giver 30 papirer. Nordic, International og Stripe kan ikke vælges i tilmeldingen.

## Tilstande

| Tilstand | Adgang |
| --- | --- |
| Lukket flag | Ingen Auth-tilmelding |
| `email_unconfirmed` | Ingen |
| Bekræftelse sprunget over | Ingen |
| `reconciliation_required` | Ingen |
| `active` | Free, efter login, når profil og én Free-entitlement findes |
| `deletion_pending` | Ingen, som i kontolivscyklussen |

## Misbrug

Supabase Auth understøtter hCaptcha og Cloudflare Turnstile som CAPTCHA på signup. Anbefalingen er Turnstile, fordi den er en af de to understøttede og den mindst tunge for brugeren. Hemmeligheden hører til i Supabase-dashboardet, ikke i git. Der er ikke oprettet en Cloudflare-konto. Platformens IP-grænser er uændrede og blev ikke aflæst. En hukommelsesgrænse i Streamlit er ikke forsvaret.

## Før åbning

Launch-listen i `registration.launch_gate` bliver ved med at svare `closed`. Den kan ikke åbne registrering. Privatlivstekst, vilkår, databehandler og slettebeskrivelse er forretningsbeslutninger og er ikke skrevet som endelig tekst. CAPTCHA-kontoen, entitlement-funktionen og en bevidst ændring af sundhedstjekket mangler også.

Lukning er at fjerne `TRADERDASH_AUTH_REGISTRATION` eller sætte den til `disabled`. Legacy-appen kræver ingen ændring.

Serverkontrollen af Turnstile er forberedt på `feature/public-pilot-finalization`. Funktionen `provision_traderdash_free` er kørt på Production og ændrer ikke den lukkede registrering. Widgettet er oprettet eksternt. Tokenet kan returneres fra en isoleret komponent, og serveren skal stadig godkende det.
