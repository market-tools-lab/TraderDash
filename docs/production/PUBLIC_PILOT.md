# Offentlig pilot, stadig lukket

Dato: 9. november 2026. Branch: `feature/public-pilot-finalization`.

Registrering er lukket. `launch_gate` svarer `closed`. Denne tekst åbner den ikke.

## Drift

Efter en senere merge skal release-gate være grøn på master. `python -m operations` skal være `ready`, hvilket kræver at `TRADERDASH_AUTH_REGISTRATION` mangler eller er `disabled`. Legacy-appen bliver på `master` og `legacy`. Piloten `traderdash-next` må ikke få registreringsflaget. Stripe og sletning bliver slået fra. Der oprettes ikke en Supabase-preview.

## Turnstile

Serverkontrollen ligger i `captcha.py`. Den kalder ikke Cloudflare i test. Et rigtigt widget er ikke oprettet.

## Provision

`provision_traderdash_free` er skrevet og må kun prøves lokalt. Den er ikke kørt på Production. Authenticated kan ikke kalde den. En eksisterende Free-entitlement ændres ikke.

## Lukning

Fjern registreringsflaget. Widget og hemmelighed kan fjernes i Cloudflare og Supabase uden at røre legacy-appen.
