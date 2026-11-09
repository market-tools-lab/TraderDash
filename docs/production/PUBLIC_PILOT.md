# Offentlig pilot, stadig lukket

Dato: 9. november 2026. Branch: `feature/public-pilot-finalization`.

Registrering er lukket. `launch_gate` svarer `closed`. Denne tekst åbner den ikke.

## Drift

Efter en senere merge skal release-gate være grøn på master. `python -m operations` skal være `ready`, hvilket kræver at `TRADERDASH_AUTH_REGISTRATION` mangler eller er `disabled`. Legacy-appen bliver på `master` og `legacy`. Piloten `traderdash-next` må ikke få registreringsflaget. Stripe og sletning bliver slået fra. Der oprettes ikke en Supabase-preview.

## Turnstile

Serverkontrollen ligger i `captcha.py`. Den kalder ikke Cloudflare i test. Widgettet Market Tools Registration Pilot er oprettet til `traderdash-next.streamlit.app`, Managed, uden pre-clearance. Nøglerne ligger i pilotens secrets og står ikke her.

Komponenten i `captcha_component/index.html` er en isoleret Streamlit-komponent. Den kan sende tokenet til appen. Serveren skal stadig godkende token, vært og handlingen `registration`. Et manglende, ugyldigt eller genbrugt token stopper tilmeldingen. Hemmeligheden sendes ikke til browseren og skrives ikke i loggen.

Den kørende pilot peger stadig på `feature/auth-email-recovery` og har ikke denne kode.

## Provision

`provision_traderdash_free` er skrevet, prøvet lokalt og ikke ændret af token-arbejdet. Den er ikke kørt på Production. Authenticated kan ikke kalde den. En eksisterende Free-entitlement ændres ikke.

## Alder og kontakt

18 år er en TraderDash-pilotregel. Den er ikke en Market Tools-regel. `support@markettools.app` er beskrevet i `SUPPORT_MAIL.md` og er ikke i drift.

## Genskabelse

Gør det ikke i denne omgang. Community Cloud kan ikke skifte branch. En senere app skal hedde `traderdash-next`, bruge samme URL, `app.py` og Python 3.14.

Kilden skal være `feature/public-pilot-finalization`, når den commit er godkendt. Efter en senere merge er kilden `master`.

Før sletning skal hemmelighederne kopieres et sikkert sted. Navnene er de eksisterende Auth-navne plus `TRADERDASH_TURNSTILE_SITE_KEY` og `TRADERDASH_TURNSTILE_SECRET_KEY`. Værdierne står ikke her. Efter genskabelsen skal `TRADERDASH_AUTH_REGISTRATION` mangle eller være `disabled`. Den nye kode skal også have `TRADERDASH_TURNSTILE=required`, `TRADERDASH_TURNSTILE_MODE=live`, `TRADERDASH_TURNSTILE_HOSTNAME=traderdash-next.streamlit.app` og `TRADERDASH_ENV=production`. Legacy-appen røres ikke.

Den nye app skal vise, at login og nulstilling virker, og at ny konto stadig ikke oprettes, før registrering må åbnes.

## Lukning

Fjern registreringsflaget. Widget og hemmelighed kan fjernes i Cloudflare og i pilotens secrets uden at røre legacy-appen.
