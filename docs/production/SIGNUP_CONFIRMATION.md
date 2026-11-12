# Bekræftelse af tilmelding

Dato: 12. november 2026. Denne fil ændrer ikke Supabase-dashboardet, sender ingen mail og åbner ikke registrering.

## Hvad den kontrollerede prøve viste

Supabase bekræftede e-mailen på sin egen vært og sendte browseren videre til `traderdash-next`. Appen fik ikke `token_hash` og `type=signup`. Profilen fandtes, fordi `handle_new_user` opretter den ved tilmeldingen. Entitlement manglede, indtil et senere login kaldte `provision_traderdash_free_self()`.

Login-genoptagelsen beholdes. En bekræftet bruger med profil og uden entitlement kan stadig få præcis én Free-entitlement ved login, også når registreringen er lukket.

## Tiltænkt link

Samme kontrakt som den prøvede nulstilling. Skabelonerne ligger i `docs/production/email/signup-confirmation.html` og `docs/production/email/signup-confirmation.txt`.

```text
{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=signup
```

`{{ .RedirectTo }}` er `TRADERDASH_AUTH_REDIRECT_URL` uden query. På piloten er den `https://traderdash-next.streamlit.app`, og den skal stå eksakt i allowlisten. Emnet kan være `Bekræft din TraderDash-konto`. Brødteksten er filerne ovenfor.

Appen accepterer kun `type=signup` sammen med `token_hash`. Den kalder `POST /auth/v1/verify`, bruger den midlertidige session til `provision_traderdash_free_self()` med en tom body, læser profil og entitlement igen, lukker sessionen og viser `E-mailen er bekræftet. Log ind.` når der er præcis én aktiv Free-entitlement med kilden `signup`. Det er 30 papirer. Et andet projekt, en udløbet verify, Nordic, International eller en betalt kilde giver ikke adgang. Query-parametrene slettes. Token og hemmelighed logges ikke.

Bekræftelseskaldet kører kun, mens `TRADERDASH_AUTH_REGISTRATION` er `enabled`. Et link, der åbnes efter at vinduet er lukket, starter ikke et nyt Auth-kald. Login-genoptagelsen er vejen for den allerede bekræftede konto.

## SIGNUP CONFIRMATION TEMPLATE OWNER ACTION REQUIRED

Production-skabelonen i Supabase Auth er ikke ændret. Før næste registreringsvindue skal Confirm signup-skabelonen sættes til linket ovenfor. `{{ .ConfirmationURL }}` alene giver ikke appen `token_hash`. Denne fil udfører ikke det dashboard-trin.
