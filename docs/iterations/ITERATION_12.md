# Iteration 12

Dato: 4. november 2026. Branch: `feature/supabase-auth`.

Status: **DONE** som lokal test mode. Stripe er ikke aktiveret i drift.

## Resultat

`stripe_test.py` bygger Checkout på serveren og anvender kun en signeret hændelse, når testen selv sætter opdatering til. Standardflaget er false. Webhook-funktionen i `supabase/functions/stripe-webhook/index.ts` har stadig `ENTITLEMENT_UPDATES_ENABLED = false`.

En Nordic-testbetaling giver 79 papirer. Samme hændelse igen ændrer intet. `past_due` suspenderer. `canceled` med en fremtidig periode beholder adgangen indtil da. En forkert signatur og en e-mail uden bruger-id ændrer intet og opretter ingen bruger.

Der er ingen live-nøgle og intet netværkskald.

## Ikke gjort

- Ingen ændring af Production-entitlement
- Ingen Checkout i de to Cloud-apps
- Ingen rigtig betaling
