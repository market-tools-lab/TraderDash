# Én kontrolleret tilmelding

Dato: 11. november 2026. Branch: `feature/public-pilot-finalization`.

Denne tekst åbner ikke registrering. Adgangskoder, tokens og hemmelige værdier står ikke her. Testkontoen `markettools.pilot@proton.me` beholdes som fixture.

## Gennemført forløb

12. november 2026, på `feature/public-pilot-finalization`, med registrering lukket bagefter.

De første forsøg stoppede sikkert før Auth. Først manglede HTTPS-transporten til Cloudflare. Dernæst nåede tokenet ikke Python. Dernæst manglede serverens Turnstile-konfiguration. Ingen af de forsøg oprettede en bruger.

Den kontrollerede prøve oprettede derefter én Auth-bruger. Turnstile viste Success. Tokenet nåede Python. Serveren godkendte det. Auth accepterede tilmeldingen. Den neutrale tekst blev vist. Bekræftelsesmailen kom frem i Proton Mail fra `noreply@auth.markettools.app`, og linket åbnede `traderdash-next`. E-mailen blev bekræftet. Der var én identitet og én profil med versionen `traderdash-pilot-2026-11-09`. Bekræftelsen efterlod kontoen uden entitlement, fordi linket ikke gav appen `token_hash` og `type=signup`.

Login-genoptagelsen blev tilføjet. Ét normalt login kaldte `provision_traderdash_free_self()` med brugerens egen session. Resultatet er én aktiv TraderDash Free-entitlement, kilde `signup`, 30 papirer. Nordic, International, betalt plan og Stripe-hændelser er nul.

Brugeren kom ind i TraderDash som Free. Betalte områder forblev lukkede. Opgraderingsknapperne viste kun, at betaling ikke er aktiveret. De kaldte ikke Stripe og ændrede ikke entitlement.

Det første skift af adgangskode blev afvist med længdekravet, fordi den gemte session slettede felterne, før formularen læste dem. Rettelsen er `c243a48d933078d52ce28d164a696bc3c49b1553`. Efter den kørte på piloten, blev adgangskoden skiftet én gang. Appen loggede brugeren ud. Login med den nye adgangskode lykkedes. Den nye adgangskode ligger hos Theis i Proton Pass og står ikke her.

Registrering er `disabled`. Legacy, `pilot-i9` og den oprindelige Free-entitlement med kilden `migration` er uændrede. Sletning er slået fra.

## Første forsøg

12. november 2026 blev de tidlige forsøg sendt, mens registrering kortvarigt var åben på `traderdash-next`. De sikre afvisninger kom, før Auth blev kaldt. De er afsluttet i forløbet ovenfor.

Piloten er `https://traderdash-next.streamlit.app`. Legacy er `https://traderdash-market.streamlit.app` og røres ikke. Én testkonto beholdes bagefter. Sletning testes ikke.

## Før testen

1. Åbn piloten. Login viser E-mail, Adgangskode og Log ind. Nulstilling viser Send nulstillingslink. Opret konto er væk.
2. `TRADERDASH_AUTH_REGISTRATION` mangler eller er `disabled` i pilotens secrets.
3. Release-gate er grøn på `feature/public-pilot-finalization`. PR #8 er stadig kladde.
4. Vælg én e-mail, som Theis selv kontrollerer, og som ikke er den eksisterende pilotkonto eller legacy-kontoen.
5. Turnstile-widgettet Market Tools Registration Pilot tillader kun `traderdash-next.streamlit.app`. Managed, uden pre-clearance. Nøglerne ligger allerede i pilotens secrets.
6. Resend, `auth.markettools.app`, Configuration: tracking metrics er ikke slået til. Configure bruges ikke. Forge og TLS ændres ikke.
7. Production `wxvobyifckbpnqfbnlxl` har én Auth-bruger, én profil, `pilot-i9`, én aktiv Free-entitlement med kilden `migration`, ingen betalt plan og nul Stripe-hændelser. Ingen preview-branch.

## Åbn vinduet

Sæt kun på `traderdash-next`: `TRADERDASH_AUTH_REGISTRATION` til `enabled`. Gem. Rør ikke `traderdash-market`.

Genindlæs piloten. Opret konto, 18-årsbekræftelsen, versionen `traderdash-pilot-2026-11-09` og Turnstile-feltet skal være synlige. Kommer de ikke frem, så luk flaget igen og stop.

## Tilmelding

Opret kun den ene konto. Theis vælger selv adgangskoden i formularen. Bekræft 18 år og udkastet til privatlivsnotits og vilkår. Gennemfør Turnstile. Vent på bekræftelsesmailen fra `noreply@auth.markettools.app`. Linket skal lande på `traderdash-next`.

## Kontrol

Efter linket:

- e-mailen er bekræftet
- der er præcis én ny Auth-bruger, én identitet og én profil
- login har kaldt `provision_traderdash_free_self()`, fordi bekræftelseslinket ikke gav appen `token_hash`
- der er præcis én aktiv TraderDash Free-entitlement
- kilden er `signup`
- planen giver 30 papirer
- Nordic, International og Stripe-hændelser er stadig nul
- den nye konto kan logge ind, også efter skift af adgangskode
- den gamle pilotkonto har stadig én Free-entitlement med kilden `migration`

## Skift af adgangskode

Brug kun den nye konto. Log ind, skift adgangskoden én gang, og kontrollér at sessionen ryddes. Log ind med den nye adgangskode. Den gamle adgangskode afvises. Nulstillingen er stadig synlig. Den eksisterende pilots adgangskode ændres ikke. Ingen af adgangskoderne skrives ned her.

## Luk vinduet

Fjern `TRADERDASH_AUTH_REGISTRATION`, eller sæt den til `disabled`, kun på `traderdash-next`. Genindlæs. Opret konto er væk. Den nye konto kan stadig logge ind. Send nulstillingslink er stadig synligt. Legacy er uændret.

## Efter testen

Sammenlign Production med kontrollen ovenfor. `launch_gate` svarer `closed`. Behold testkontoen som fixture. Start ikke slettetesten.

## Stop

Ved et af punkterne nedenfor er den sikre inddæmning at lukke registreringsflaget på `traderdash-next`. Slet ikke rækker, og ret ikke Production med et reparationskald.

| Signal | Inddæmning |
| --- | --- |
| Turnstile vises ikke, eller serveren afviser token | Luk flaget. Gentag ikke med et nyt forsøg i samme vindue |
| Bekræftet konto mangler Free-entitlement | Luk flaget. Opret ikke en anden konto |
| Mere end én aktiv entitlement | Luk flaget. Indsæt ikke en række til |
| Nordic, International eller en anden plan | Luk flaget. Ændr ikke planen manuelt |
| Mail udebliver, kommer fra en anden afsender, eller linket lander et andet sted | Luk flaget. Send ikke en ny mail |
| En Stripe-hændelse | Luk flaget. Stripe forbliver slået fra |
| Legacy-appen er ændret | Luk flaget. Rør ikke `traderdash-market` yderligere |
| Auth-brugere, profiler eller entitlements ændrer sig ud over den ene nye konto | Luk flaget. Kør ingen ny SQL |
| Flaget kan ikke fjernes | Lad være med at oprette flere konti, og fjern flaget, før noget andet arbejde fortsætter |
