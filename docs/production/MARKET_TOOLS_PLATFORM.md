# Market Tools og TraderDash

Dato: 9. november 2026.

`markettools.app` er platformen. TraderDash er ét produkt. Ny platformkode skal kunne bruges af et senere produkt uden at give det en TraderDash-entitlement.

## Platform

Kontoen er e-mail, adgangskode, bekræftet adresse, CAPTCHA og en kvittering for udkastet til privatlivstekst og vilkår. Det ligger i `captcha.py`, `registration.py` og `supabase_auth.py`. Logningen er generel. Flaget `TRADERDASH_AUTH_REGISTRATION` er stadig pilotens kontakt. Et senere produkt kan få sit eget flag uden at arve TraderDash-planen.

## Produkt

TraderDash-profilen og den ene Free-entitlement er produktets eget trin. Funktionen `provision_traderdash_free` opretter dem kun, når en betroet database-rolle kalder den. Den kører ikke af sig selv for enhver ny Market Tools-konto. Free er 30 papirer. Nordic, International og Stripe kan ikke vælges ved tilmelding.

En bekræftet Auth-bruger er ikke det samme som en bruger med adgang til TraderDash.
