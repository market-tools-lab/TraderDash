# Market Tools og TraderDash

Dato: 9. november 2026.

`markettools.app` er platformen. TraderDash er ét produkt. Ny platformkode skal kunne bruges af et senere produkt uden at give det en TraderDash-entitlement.

## Platform

Kontoen er e-mail, adgangskode, bekræftet adresse, CAPTCHA og en kvittering for udkastet til privatlivstekst og vilkår. Det ligger i `captcha.py`, `registration.py` og `supabase_auth.py`. Logningen er generel. Flaget `TRADERDASH_AUTH_REGISTRATION` er stadig pilotens kontakt. Et senere produkt kan få sit eget flag uden at arve TraderDash-planen.

Alderskravet på 18 år hører til TraderDash-piloten. Det er ikke en Market Tools-regel. Et senere undervisningsprodukt kan have et andet publikum. Platformen gemmer ikke fødselsdato.

## Produkt

TraderDash-profilen, 18-årsbekræftelsen og den ene Free-entitlement er produktets eget trin. Triggeren `handle_new_user` opretter kun profilen. Den giver ikke et produkt. `provision_traderdash_free(uuid)` kan stadig kun kaldes af en betroet database-rolle, og den tager et vilkårligt id. Den nye funktion `provision_traderdash_free_self()` tager intet id. Den bruger kun den bekræftede kalder fra `auth.uid()`, og kun TraderDash-bekræftelsen kalder den. Et senere produkt skal have sin egen funktion. Free er 30 papirer. Nordic, International og Stripe kan ikke vælges ved tilmelding.

En bekræftet Auth-bruger er ikke det samme som en bruger med adgang til TraderDash.

## Grænse

Market Tools er kontoen, bekræftet e-mail, nulstilling, registreringsrammen, CAPTCHA-afgrænsningen, kvitteringen for teksterne, kontolivscyklussen og overvågningen. TraderDash er Free-tilmeldingen, de 30 papirer, 18-årsreglen for denne pilot og produktadgangen. Et senere produkt får sin egen funktion og sit eget flag.
