# Offentlig pilot, stadig lukket

Dato: 9. november 2026. Branch: `feature/public-pilot-finalization`.

Registrering er lukket. `launch_gate` svarer `closed`. Denne tekst åbner den ikke.

## Drift

Pull request #8 er merget til `master`. Release-gate på den merge er grøn. `python -m operations` er `ready`, når `TRADERDASH_AUTH_REGISTRATION` mangler eller er `disabled`. Legacy-appen bliver på `master` og `legacy`. `traderdash-next` er ikke flyttet til `master`. Registreringsflaget forbliver lukket. Stripe og sletning er slået fra. Der oprettes ikke en Supabase-preview.

## Turnstile

Serverkontrollen ligger i `captcha.py`. Den kalder ikke Cloudflare i test. Widgettet Market Tools Registration Pilot er oprettet til `traderdash-next.streamlit.app`, Managed, uden pre-clearance. Nøglerne ligger i pilotens secrets og står ikke her.

Komponenten i `captcha_component/index.html` er en isoleret Streamlit-komponent. Den kan sende tokenet til appen. Serveren skal stadig godkende token, vært og handlingen `registration`. Et manglende, ugyldigt eller genbrugt token stopper tilmeldingen. Hemmeligheden sendes ikke til browseren og skrives ikke i loggen.

Piloten følger stadig `feature/public-pilot-finalization`. Registreringen er lukket. Én kontrolleret tilmelding er gennemført og beholdt. Forløbet står i `CONTROLLED_SIGNUP.md`.

## Provision

`provision_traderdash_free` er kørt på Production som `20261109111918`. Checksummen for filen er `4e32c4e652b6d26b2cc73cc453438fcf0867b37eb84a1d2b25edd26361babbc7`. Authenticated kan ikke kalde den. `provision_traderdash_free_self()` er kørt som `20261109121539`. Checksummen for filen er `83dcb6ede525033ced3ce24c1b81f6d753a27581a5a450ca9c2716f3418cf7cb`. Den betroede selvtilmelding er i drift. Den eksisterende Free-entitlement er uændret. Registrering er stadig lukket.

## Alder og kontakt

18 år er en TraderDash-pilotregel. Den er ikke en Market Tools-regel. `support@markettools.app` er i drift. Detaljerne står i `SUPPORT_MAIL.md`. Auth-afsenderen er uændret.

## Genskabelse

Genskabelsen er allerede udført. Community Cloud kan ikke skifte branch på en eksisterende app. Den kørende app er `traderdash-next`, `app.py` og Python 3.14 på `feature/public-pilot-finalization`. Den skal ikke slettes for den senere test. Testen står i `CONTROLLED_SIGNUP.md`.

Kilden skal være `feature/public-pilot-finalization`, når den commit er godkendt. Efter en senere merge er kilden `master`.

Før sletning skal hemmelighederne kopieres et sikkert sted. Navnene er de eksisterende Auth-navne plus `TRADERDASH_TURNSTILE_SITE_KEY` og `TRADERDASH_TURNSTILE_SECRET_KEY`. Værdierne står ikke her. Efter genskabelsen skal `TRADERDASH_AUTH_REGISTRATION` mangle eller være `disabled`. Den nye kode skal også have `TRADERDASH_TURNSTILE=required`, `TRADERDASH_TURNSTILE_MODE=live`, `TRADERDASH_TURNSTILE_HOSTNAME=traderdash-next.streamlit.app` og `TRADERDASH_ENV=production`. Legacy-appen røres ikke.

Den nye app skal vise, at login og nulstilling virker, og at ny konto stadig ikke oprettes, før registrering må åbnes.

## Lukning

Fjern registreringsflaget. Widget og hemmelighed kan fjernes i Cloudflare og i pilotens secrets uden at røre legacy-appen.
